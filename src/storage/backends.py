# src/storage/backends.py
"""
src/storage/backends.py

Defines abstract and concrete storage backend implementations for
processed articles (JSONL, Elasticsearch, PostgreSQL),
and a factory to retrieve them based on configuration.

FIXES APPLIED:
- Fix #2: PostgreSQL connection pooling (5-20 connections)
- Fix #3: Elasticsearch bulk insert with 500-item batching
- Fix #6: Retry logic with exponential backoff for all backends
"""

import atexit
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import date, datetime
from pathlib import Path

# Tenacity for retry logic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

# Conditional imports for database clients - they are only imported when the class is instantiated
try:
    from elasticsearch import Elasticsearch, helpers as es_helpers
except ImportError:
    Elasticsearch = None
    es_helpers = None

try:
    import psycopg2
    from psycopg2 import pool as psycopg2_pool
    from psycopg2 import sql as pg_sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    psycopg2 = None
    psycopg2_pool = None
    pg_sql = None
    ISOLATION_LEVEL_AUTOCOMMIT = None

from src.schemas.data_models import PreprocessSingleResponse
from src.utils.config_manager import (
    ConfigManager,
    JsonlStorageConfig,
    ElasticsearchStorageConfig,
    PostgreSQLStorageConfig
)

logger = logging.getLogger("ingestion_service")

# Constants for retry and batching
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # seconds
RETRY_MAX_WAIT = 10  # seconds
ES_BATCH_SIZE = 500  # Elasticsearch recommendation


class StorageBackend(ABC):
    """Abstract Base Class for storage backends."""
    @abstractmethod
    def initialize(self):
        """Initializes the storage backend (e.g., establish connection, create directories/tables)."""
        pass

    @abstractmethod
    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """Saves a single processed article."""
        pass

    @abstractmethod
    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """Saves a batch of processed articles."""
        pass

    @abstractmethod
    def close(self):
        """Closes any open connections or resources."""
        pass


class JSONLStorageBackend(StorageBackend):
    """
    Storage backend that saves processed articles to a daily-created JSONL (JSON Lines) file.
    Each line in the file is a JSON object.
    
    IMPROVEMENTS:
    - Retry logic with exponential backoff for file write failures
    - Better error handling and logging
    """

    def __init__(self, config: JsonlStorageConfig):
        self.output_directory = Path(config.output_path).parent
        self.current_file_path: Optional[Path] = None
        self._file_handle = None
        self._current_date: Optional[date] = None
        logger.info(
            f"Initialized JSONLStorageBackend with output directory: {self.output_directory}")

    def initialize(self):
        """
        Ensures the output directory exists and is writable.
        """
        try:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            # Verify directory is writable
            if not os.access(self.output_directory, os.W_OK):
                raise PermissionError(
                    f"Output directory {self.output_directory} is not writable.")
            logger.info(
                f"JSONL storage directory ensured: {self.output_directory}")
        except Exception as e:
            logger.critical(
                f"Failed to create or verify JSONL output directory {self.output_directory}: {e}")
            raise

    def _get_daily_file_path(self) -> Path:
        """Generates the file path for today's JSONL file."""
        today_str = date.today().strftime("%Y-%m-%d")
        return self.output_directory / f"processed_articles_{today_str}.jsonl"

    def _open_file(self):
        """Opens or re-opens the daily file for appending."""
        new_file_path = self._get_daily_file_path()
        today = date.today()

        if self._file_handle is None or new_file_path != self.current_file_path or today != self._current_date:
            self.close()  # Close existing handle if file path or date changed

            self.current_file_path = new_file_path
            self._current_date = today
            try:
                self._file_handle = open(
                    self.current_file_path, 'a', encoding='utf-8')
                logger.info(
                    f"Opened JSONL file for appending: {self.current_file_path}")
            except Exception as e:
                logger.critical(
                    f"Failed to open JSONL file {self.current_file_path}: {e}", exc_info=True)
                raise

    def _serialize_data(self, data: PreprocessSingleResponse) -> Dict[str, Any]:
        """
        Serializes PreprocessSingleResponse to a dictionary, handling Pydantic models
        and datetime/date objects.
        """
        return data.model_dump(mode='json')

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((IOError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """
        Saves a single processed article to the JSONL file.
        
        IMPROVEMENT: Retry logic handles transient file system errors.
        """
        try:
            self._open_file()
            serialized_data = self._serialize_data(data)
            json_line = json.dumps(serialized_data, ensure_ascii=False)
            self._file_handle.write(json_line + '\n')
            self._file_handle.flush()  # Ensure data is written to disk
            os.fsync(self._file_handle.fileno())  # Force disk sync
            logger.debug(
                f"Saved single document {data.document_id} to JSONL file: {self.current_file_path}")
        except Exception as e:
            logger.error(
                f"Failed to write record {data.document_id} to JSONL file {self.current_file_path}: {e}",
                exc_info=True)
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((IOError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """
        Saves a batch of processed articles to the JSONL file.
        
        IMPROVEMENT: Retry logic handles transient file system errors.
        """
        if not data_list:
            logger.debug(
                "Attempted to save an empty batch to JSONL. Skipping.")
            return

        try:
            self._open_file()
            for data in data_list:
                serialized_data = self._serialize_data(data)
                json_line = json.dumps(serialized_data, ensure_ascii=False)
                self._file_handle.write(json_line + '\n')
            self._file_handle.flush()  # Ensure data is written to disk
            os.fsync(self._file_handle.fileno())  # Force disk sync
            logger.info(
                f"Saved batch of {len(data_list)} documents to JSONL file: {self.current_file_path}")
        except Exception as e:
            logger.error(
                f"Failed to save batch to JSONL file {self.current_file_path}: {e}",
                exc_info=True)
            raise

    def close(self):
        """Closes the current file handle if open."""
        if self._file_handle:
            try:
                self._file_handle.flush()  # Ensure any buffered data is written
                os.fsync(self._file_handle.fileno())  # Force disk sync
                self._file_handle.close()
                logger.info(
                    f"Closed JSONL file handle: {self.current_file_path}")
            except Exception as e:
                logger.error(
                    f"Error closing JSONL file {self.current_file_path}: {e}",
                    exc_info=True)
            finally:
                self._file_handle = None
                self.current_file_path = None
                self._current_date = None


class ElasticsearchStorageBackend(StorageBackend):
    """
    Storage backend that saves processed articles to Elasticsearch.
    Requires Elasticsearch client to be installed and connection details.
    
    IMPROVEMENTS:
    - Fix #3: Bulk insert with 500-item batching to prevent OOM
    - Fix #6: Retry logic with exponential backoff for network failures
    """

    def __init__(self, config: ElasticsearchStorageConfig):
        if Elasticsearch is None:
            raise ImportError(
                "Elasticsearch client is not installed. Please install it with 'pip install elasticsearch'.")

        self.config = config
        self.es: Optional[Elasticsearch] = None
        self.index_name = config.index_name
        logger.info(
            f"Initialized ElasticsearchStorageBackend for index: {self.index_name} at {config.host}:{config.port}")

    def initialize(self):
        """Initializes the Elasticsearch client and ensures the index exists."""
        if self.es:
            return

        try:
            connection_params = {
                "hosts": [{"host": self.config.host, "port": self.config.port, "scheme": self.config.scheme}]
            }
            if self.config.api_key:
                connection_params["api_key"] = self.config.api_key
            self.es = Elasticsearch(**connection_params)
            if not self.es.ping():
                raise ConnectionError("Could not connect to Elasticsearch.")
            logger.info("Successfully connected to Elasticsearch.")
            self._ensure_index()
        except Exception as e:
            logger.critical(
                f"Failed to initialize Elasticsearch connection or ensure index '{self.index_name}': {e}",
                exc_info=True)
            self.es = None
            raise

    def _ensure_index(self):
        """Ensures the Elasticsearch index exists."""
        if not self.es:
            logger.error(
                "Elasticsearch client not initialized. Cannot ensure index.")
            return

        try:
            if not self.es.indices.exists(index=self.index_name):
                self.es.indices.create(index=self.index_name)
                logger.info(
                    f"Elasticsearch index '{self.index_name}' created.")
            else:
                logger.debug(
                    f"Elasticsearch index '{self.index_name}' already exists.")
        except Exception as e:
            logger.error(
                f"Failed to check/create Elasticsearch index '{self.index_name}': {e}",
                exc_info=True)
            raise

    def _prepare_doc(self, data: PreprocessSingleResponse) -> Dict[str, Any]:
        """
        Prepares a single PreprocessSingleResponse for Elasticsearch indexing.
        Converts Pydantic model to a dictionary suitable for ES,
        handling dates and HttpUrls for JSON serialization.
        """
        doc = data.model_dump(mode='json')
        return doc

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """
        Saves a single processed article to Elasticsearch.
        
        IMPROVEMENT: Retry logic handles transient network failures.
        """
        if not self.es:
            logger.error(
                f"Elasticsearch client not initialized. Skipping save for document {data.document_id}.")
            return

        doc = self._prepare_doc(data)
        try:
            response = self.es.index(
                index=self.index_name, id=data.document_id, document=doc)
            logger.debug(
                f"Saved document {data.document_id} to Elasticsearch. Response: {response['result']}")
        except Exception as e:
            logger.error(
                f"Failed to save document {data.document_id} to Elasticsearch: {e}",
                exc_info=True)
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """
        Saves a batch of processed articles to Elasticsearch using bulk API.
        
        IMPROVEMENTS:
        - Fix #3: Batches into 500-item chunks to prevent OOM and ES rejection
        - Fix #6: Retry logic for network failures
        """
        if not self.es:
            logger.error(
                "Elasticsearch client not initialized. Skipping batch save.")
            return
        if not data_list:
            logger.debug(
                "Attempted to save an empty batch to Elasticsearch. Skipping.")
            return
        if es_helpers is None:
            logger.error(
                "Elasticsearch helpers not imported. Cannot perform bulk save.")
            raise ImportError(
                "Elasticsearch helpers module is required for bulk operations.")

        # Process in batches of ES_BATCH_SIZE (500)
        total_success = 0
        total_errors = []

        for i in range(0, len(data_list), ES_BATCH_SIZE):
            batch = data_list[i:i+ES_BATCH_SIZE]
            actions = [
                {
                    "_index": self.index_name,
                    "_id": data.document_id,
                    "_source": self._prepare_doc(data)
                }
                for data in batch
            ]
            try:
                success_count, errors = es_helpers.bulk(
                    self.es, actions, chunk_size=ES_BATCH_SIZE, stats_only=False)
                total_success += success_count
                if errors:
                    total_errors.extend(errors)
                    for error in errors:
                        logger.error(f"Elasticsearch bulk save error: {error}")
                logger.debug(
                    f"Processed ES batch {i//ES_BATCH_SIZE + 1}: {success_count} successes, "
                    f"{len(errors)} errors")
            except Exception as e:
                logger.error(
                    f"Failed to save batch chunk to Elasticsearch (items {i}-{i+len(batch)}): {e}",
                    exc_info=True)
                raise

        logger.info(
            f"Successfully saved {total_success} of {len(data_list)} documents to Elasticsearch "
            f"(with {len(total_errors)} errors).")

    def close(self):
        """Closes the Elasticsearch client connection."""
        if self.es:
            logger.debug(
                "Elasticsearch client does not require explicit close for HTTP connections.")
            self.es = None


class PostgreSQLStorageBackend(StorageBackend):
    """
    Storage backend that saves processed articles to PostgreSQL.
    Requires psycopg2-binary client to be installed.
    
    IMPROVEMENTS:
    - Fix #2: Connection pooling (5-20 connections) for high concurrency
    - Fix #6: Retry logic with exponential backoff for network failures
    """

    # Class-level connection pool (shared across instances)
    _connection_pool: Optional[Any] = None
    _pool_lock = None  # Will be initialized with threading.Lock()

    def __init__(self, config: PostgreSQLStorageConfig):
        if psycopg2 is None:
            raise ImportError(
                "psycopg2-binary is not installed. Please install it with 'pip install psycopg2-binary'.")

        self.config = config
        self.conn_params = {
            "host": config.host,
            "port": config.port,
            "dbname": config.dbname,
            "user": config.user,
            "password": config.password
        }
        self.table_name = config.table_name
        self._connection: Optional[psycopg2.extensions.connection] = None

        # Initialize lock for thread-safe pool access
        if PostgreSQLStorageBackend._pool_lock is None:
            import threading
            PostgreSQLStorageBackend._pool_lock = threading.Lock()

        logger.info(
            f"Initialized PostgreSQLStorageBackend for table: {self.table_name} on "
            f"{config.host}:{config.port}/{config.dbname}")

    def _get_or_create_pool(self):
        """
        Creates or returns the connection pool.
        Thread-safe initialization of the class-level pool.
        """
        with PostgreSQLStorageBackend._pool_lock:
            if PostgreSQLStorageBackend._connection_pool is None:
                try:
                    PostgreSQLStorageBackend._connection_pool = psycopg2_pool.ThreadedConnectionPool(
                        minconn=5,
                        maxconn=20,
                        **self.conn_params
                    )
                    logger.info(
                        "PostgreSQL connection pool created (5-20 connections)")
                except Exception as e:
                    logger.critical(
                        f"Failed to create PostgreSQL connection pool: {e}", exc_info=True)
                    raise
            return PostgreSQLStorageBackend._connection_pool

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Gets a connection from the pool."""
        pool = self._get_or_create_pool()
        try:
            conn = pool.getconn()
            conn.autocommit = False
            logger.debug("Retrieved connection from PostgreSQL pool")
            return conn
        except Exception as e:
            logger.critical(
                f"Failed to get connection from PostgreSQL pool: {e}", exc_info=True)
            raise

    def _return_connection(self, conn: psycopg2.extensions.connection):
        """Returns a connection to the pool."""
        if conn and PostgreSQLStorageBackend._connection_pool:
            PostgreSQLStorageBackend._connection_pool.putconn(conn)
            logger.debug("Returned connection to PostgreSQL pool")

    def initialize(self):
        """
        Connects to the database and ensures the table exists.
        Handles database creation if it doesn't exist, by connecting to default 'postgres' db.
        """
        temp_conn_params = self.conn_params.copy()
        temp_db_name = temp_conn_params.pop("dbname")
        temp_conn_params["dbname"] = "postgres"

        temp_conn = None
        try:
            temp_conn = psycopg2.connect(**temp_conn_params)
            temp_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = temp_conn.cursor()
            cur.execute(pg_sql.SQL(
                "SELECT 1 FROM pg_database WHERE datname = %s;"), [temp_db_name])
            if cur.fetchone() is None:
                cur.execute(pg_sql.SQL("CREATE DATABASE {};").format(
                    pg_sql.Identifier(temp_db_name)))
                logger.info(f"PostgreSQL database '{temp_db_name}' created.")
            else:
                logger.debug(
                    f"PostgreSQL database '{temp_db_name}' already exists.")
            cur.close()
        except Exception as e:
            logger.warning(
                f"Could not create PostgreSQL database '{temp_db_name}' "
                f"(might already exist or permissions issue): {e}")
        finally:
            if temp_conn:
                temp_conn.close()

        # Initialize the connection pool
        self._get_or_create_pool()

        # Create table using a connection from the pool
        conn = self._get_connection()
        try:
            self._create_table_if_not_exists(conn)
            logger.info(f"PostgreSQL backend initialized and connected.")
        except Exception as e:
            logger.critical(
                f"Failed to initialize PostgreSQL backend: {e}", exc_info=True)
            raise
        finally:
            self._return_connection(conn)

    def _create_table_if_not_exists(self, conn: psycopg2.extensions.connection):
        """Creates the PostgreSQL table if it doesn't exist."""
        cur = None
        try:
            cur = conn.cursor()
            create_table_query = pg_sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                document_id VARCHAR(255) PRIMARY KEY,
                version VARCHAR(50),
                original_text TEXT,
                cleaned_text TEXT,
                cleaned_title TEXT,
                cleaned_excerpt TEXT,
                cleaned_author TEXT,
                cleaned_publication_date DATE,
                cleaned_revision_date DATE,
                cleaned_source_url TEXT,
                cleaned_categories JSONB,
                cleaned_tags JSONB,
                cleaned_media_asset_urls JSONB,
                cleaned_geographical_data JSONB,
                cleaned_embargo_date DATE,
                cleaned_sentiment TEXT,
                cleaned_word_count INTEGER,
                cleaned_publisher TEXT,
                temporal_metadata DATE,
                entities JSONB,
                cleaned_additional_metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """).format(pg_sql.Identifier(self.table_name))
            cur.execute(create_table_query)
            conn.commit()
            logger.info(
                f"PostgreSQL table '{self.table_name}' ensured to exist.")
        except Exception as e:
            logger.critical(
                f"Failed to create PostgreSQL table '{self.table_name}': {e}",
                exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if cur:
                cur.close()

    def _prepare_sql_data(self, data: PreprocessSingleResponse) -> Dict[str, Any]:
        """
        Prepares a single PreprocessSingleResponse for SQL insertion.
        Converts Pydantic models/types to suitable SQL types.
        """
        temporal_metadata_date = None
        if data.temporal_metadata:
            try:
                temporal_metadata_date = datetime.strptime(
                    data.temporal_metadata, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(
                    f"Invalid temporal_metadata date format for document {data.document_id}: "
                    f"{data.temporal_metadata}. Storing as NULL.")

        return {
            "document_id": data.document_id,
            "version": data.version,
            "original_text": data.original_text,
            "cleaned_text": data.cleaned_text,
            "cleaned_title": data.cleaned_title,
            "cleaned_excerpt": data.cleaned_excerpt,
            "cleaned_author": data.cleaned_author,
            "cleaned_publication_date": data.cleaned_publication_date,
            "cleaned_revision_date": data.cleaned_revision_date,
            "cleaned_source_url": str(data.cleaned_source_url) if data.cleaned_source_url else None,
            "cleaned_categories": json.dumps(data.cleaned_categories) if data.cleaned_categories is not None else None,
            "cleaned_tags": json.dumps(data.cleaned_tags) if data.cleaned_tags is not None else None,
            "cleaned_media_asset_urls": json.dumps([str(url) for url in data.cleaned_media_asset_urls]) if data.cleaned_media_asset_urls is not None else None,
            "cleaned_geographical_data": json.dumps(data.cleaned_geographical_data) if data.cleaned_geographical_data is not None else None,
            "cleaned_embargo_date": data.cleaned_embargo_date,
            "cleaned_sentiment": data.cleaned_sentiment,
            "cleaned_word_count": data.cleaned_word_count,
            "cleaned_publisher": data.cleaned_publisher,
            "temporal_metadata": temporal_metadata_date,
            "entities": json.dumps([entity.model_dump(mode='json') for entity in data.entities]),
            "cleaned_additional_metadata": json.dumps(data.cleaned_additional_metadata) if data.cleaned_additional_metadata is not None else None
        }

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(
            (psycopg2.OperationalError, psycopg2.InterfaceError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """
        Saves a single processed article to PostgreSQL.
        
        IMPROVEMENT: Uses connection pool and retry logic for resilience.
        """
        conn = self._get_connection()
        prepared_data = self._prepare_sql_data(data)
        cur = None
        try:
            cur = conn.cursor()
            columns = pg_sql.SQL(', ').join(
                map(pg_sql.Identifier, prepared_data.keys()))
            placeholders = pg_sql.SQL(', ').join(
                pg_sql.Placeholder() * len(prepared_data))
            update_columns = pg_sql.SQL(', ').join(
                pg_sql.SQL('{} = EXCLUDED.{}').format(
                    pg_sql.Identifier(col), pg_sql.Identifier(col))
                for col in prepared_data.keys() if col != 'document_id'
            )

            insert_query = pg_sql.SQL(
                "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (document_id) DO UPDATE SET {};"
            ).format(
                pg_sql.Identifier(self.table_name),
                columns,
                placeholders,
                update_columns
            )

            cur.execute(insert_query, tuple(prepared_data.values()))
            conn.commit()
            logger.debug(
                f"Saved single document {data.document_id} to PostgreSQL.")
        except Exception as e:
            logger.error(
                f"Failed to save document {data.document_id} to PostgreSQL: {e}",
                exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if cur:
                cur.close()
            self._return_connection(conn)

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(
            (psycopg2.OperationalError, psycopg2.InterfaceError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """
        Saves a batch of processed articles to PostgreSQL using executemany.
        
        IMPROVEMENT: Uses connection pool and retry logic for resilience.
        """
        if not data_list:
            logger.debug(
                "Attempted to save an empty batch to PostgreSQL. Skipping.")
            return

        conn = self._get_connection()
        cur = None
        try:
            cur = conn.cursor()
            first_data = self._prepare_sql_data(data_list[0])
            columns = pg_sql.SQL(', ').join(
                map(pg_sql.Identifier, first_data.keys()))
            placeholders = pg_sql.SQL(', ').join(
                pg_sql.Placeholder() * len(first_data))
            update_columns = pg_sql.SQL(', ').join(
                pg_sql.SQL('{} = EXCLUDED.{}').format(
                    pg_sql.Identifier(col), pg_sql.Identifier(col))
                for col in first_data.keys() if col != 'document_id'
            )

            insert_query = pg_sql.SQL(
                "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (document_id) DO UPDATE SET {};"
            ).format(
                pg_sql.Identifier(self.table_name),
                columns,
                placeholders,
                update_columns
            )

            batch_values = [tuple(self._prepare_sql_data(
                data).values()) for data in data_list]
            cur.executemany(insert_query, batch_values)
            conn.commit()
            logger.info(
                f"Saved batch of {len(data_list)} documents to PostgreSQL.")
        except Exception as e:
            logger.error(
                f"Failed to save batch to PostgreSQL: {e}",
                exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if cur:
                cur.close()
            self._return_connection(conn)

    def close(self):
        """Closes the PostgreSQL connection."""
        if self._connection:
            try:
                self._return_connection(self._connection)
                logger.info("PostgreSQL connection returned to pool.")
            except Exception as e:
                logger.error(
                    f"Error returning PostgreSQL connection to pool: {e}",
                    exc_info=True)
            finally:
                self._connection = None


class StorageBackendFactory:
    """
    Factory to create and provide appropriate storage backend instances based on configuration.
    Manages the lifecycle of backends to ensure proper initialization and closing.
    """
    _initialized_backends: Dict[str, StorageBackend] = {}

    @classmethod
    def get_backends(cls, requested_backends: Optional[List[str]] = None) -> List[StorageBackend]:
        """
        Returns a list of initialized StorageBackend instances.

        Args:
            requested_backends: Optional list of backend names to activate for a specific request.
                                If None or empty, uses the 'enabled_backends' from settings.
                                These must be a subset of the configured 'enabled_backends'.

        Returns:
            A list of initialized StorageBackend instances.

        Raises:
            ValueError: If a requested or enabled backend is not configured or supported.
            ImportError: If a required library for a backend is not installed.
            ConnectionError: If a backend fails to initialize its connection.
        """
        settings = ConfigManager.get_settings()
        storage_config = settings.storage

        backends_to_use = []
        if requested_backends:
            for backend_name in requested_backends:
                if backend_name in storage_config.enabled_backends:
                    backends_to_use.append(backend_name)
                else:
                    logger.warning(
                        f"Requested backend '{backend_name}' is not enabled in settings. Skipping.")
        else:
            backends_to_use = storage_config.enabled_backends

        if not backends_to_use:
            logger.info(
                "No storage backends enabled or requested. Defaulting to 'jsonl'.")
            backends_to_use = ["jsonl"]

        active_backends: List[StorageBackend] = []

        for backend_name in backends_to_use:
            backend_name_lower = backend_name.lower()

            if backend_name_lower not in cls._initialized_backends:
                try:
                    if backend_name_lower == "jsonl":
                        if not storage_config.jsonl:
                            raise ValueError(
                                f"JSONL backend specified but not configured in settings.yaml")
                        backend = JSONLStorageBackend(
                            config=storage_config.jsonl)
                    elif backend_name_lower == "elasticsearch":
                        if not storage_config.elasticsearch:
                            raise ValueError(
                                f"Elasticsearch backend specified but not configured in settings.yaml")
                        backend = ElasticsearchStorageBackend(
                            config=storage_config.elasticsearch)
                    elif backend_name_lower == "postgresql":
                        if not storage_config.postgresql:
                            raise ValueError(
                                f"PostgreSQL backend specified but not configured in settings.yaml")
                        backend = PostgreSQLStorageBackend(
                            config=storage_config.postgresql)
                    else:
                        raise ValueError(
                            f"Unsupported or unconfigured storage backend type: '{backend_name}'.")

                    backend.initialize()
                    cls._initialized_backends[backend_name_lower] = backend
                    logger.info(
                        f"Storage backend '{backend_name}' successfully initialized.")
                    active_backends.append(backend)

                except (ValueError, ImportError, ConnectionError) as e:
                    logger.critical(
                        f"Failed to initialize storage backend '{backend_name}': {e}. "
                        f"This backend will be skipped.", exc_info=True)
                except Exception as e:
                    logger.critical(
                        f"An unexpected error occurred during initialization of backend '{backend_name}': {e}. "
                        f"Skipping.", exc_info=True)
            else:
                backend = cls._initialized_backends[backend_name_lower]
                active_backends.append(backend)
                logger.debug(
                    f"Reusing already initialized storage backend: {backend_name}.")

        return active_backends

    @classmethod
    def close_all_backends(cls):
        """Closes all initialized storage backend connections/resources."""
        logger.info("Attempting to close all initialized storage backends.")
        for name, backend in list(cls._initialized_backends.items()):
            try:
                backend.close()
                logger.info(f"Storage backend '{name}' successfully closed.")
            except Exception as e:
                logger.error(
                    f"Error closing storage backend '{name}': {e}", exc_info=True)
            finally:
                del cls._initialized_backends[name]

        # Close PostgreSQL connection pool
        if PostgreSQLStorageBackend._connection_pool:
            try:
                PostgreSQLStorageBackend._connection_pool.closeall()
                logger.info("PostgreSQL connection pool closed.")
            except Exception as e:
                logger.error(
                    f"Error closing PostgreSQL connection pool: {e}", exc_info=True)
            finally:
                PostgreSQLStorageBackend._connection_pool = None


atexit.register(StorageBackendFactory.close_all_backends)

# src/storage/backends.py
