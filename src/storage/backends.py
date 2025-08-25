# src/storage/backends.py
"""
src/storage/backends.py

Defines abstract and concrete storage backend implementations for
processed articles (JSONL, Elasticsearch, PostgreSQL),
and a factory to retrieve them based on configuration.
"""

import atexit
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import date, datetime
from pathlib import Path

# Conditional imports for database clients - they are only imported when the class is instantiated
# This avoids hard dependency on all clients if only one backend is used.
try:
    from elasticsearch import Elasticsearch, helpers as es_helpers
except ImportError:
    Elasticsearch = None
    es_helpers = None
    logger.debug(
        "Elasticsearch client not installed. ElasticsearchStorageBackend will not be available.")

try:
    import psycopg2
    from psycopg2 import sql as pg_sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    psycopg2 = None
    pg_sql = None
    ISOLATION_LEVEL_AUTOCOMMIT = None
    logger.debug(
        "psycopg2-binary not installed. PostgreSQLStorageBackend will not be available.")


# Updated to use PreprocessSingleResponse directly
from src.schemas.data_models import PreprocessSingleResponse
from src.utils.config_manager import ConfigManager, JsonlStorageConfig, ElasticsearchStorageConfig, PostgreSQLStorageConfig

logger = logging.getLogger("ingestion_service")


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
    """

    def __init__(self, config: JsonlStorageConfig):
        self.output_directory = Path(config.output_directory)
        self.current_file_path: Optional[Path] = None
        self._file_handle = None
        self._current_date: Optional[date] = None
        logger.info(
            f"Initialized JSONLStorageBackend with output directory: {self.output_directory}")

    def initialize(self):
        """
        Ensures the output directory exists.
        """
        try:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            logger.info(
                f"JSONL storage directory ensured: {self.output_directory}")
        except Exception as e:
            logger.critical(
                f"Failed to create JSONL output directory {self.output_directory}: {e}")
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
        # model_dump(mode='json') handles datetime/date objects to ISO format strings
        # and HttpUrl to string, and nested Pydantic models to dicts.
        return data.model_dump(mode='json')

    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """Saves a single processed article to the JSONL file."""
        try:
            self._open_file()  # Ensure the correct daily file is open
            serialized_data = self._serialize_data(data)
            json_line = json.dumps(serialized_data, ensure_ascii=False)
            self._file_handle.write(json_line + '\n')
            # self._file_handle.flush() # Optional: Force write to disk immediately (can impact performance)
            logger.debug(
                f"Saved single document {data.document_id} to JSONL file.")
        except Exception as e:
            logger.error(
                f"Failed to write record {data.document_id} to JSONL file: {e}", exc_info=True)
            raise  # Re-raise to ensure error is propagated if necessary

    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """Saves a batch of processed articles to the JSONL file."""
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
            # self._file_handle.flush()
            logger.info(
                f"Saved batch of {len(data_list)} documents to JSONL file.")
        except Exception as e:
            logger.error(
                f"Failed to save batch to JSONL file: {e}", exc_info=True)
            raise

    def close(self):
        """Closes the current file handle if open."""
        if self._file_handle:
            try:
                self._file_handle.close()
                logger.info(
                    f"Closed JSONL file handle: {self.current_file_path}")
            except Exception as e:
                logger.error(
                    f"Error closing JSONL file {self.current_file_path}: {e}", exc_info=True)
            finally:
                self._file_handle = None
                self.current_file_path = None
                self._current_date = None


class ElasticsearchStorageBackend(StorageBackend):
    """
    Storage backend that saves processed articles to Elasticsearch.
    Requires Elasticsearch client to be installed and connection details.
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
        if self.es:  # Already initialized
            return

        try:
            # Build connection parameters from config
            connection_params = {
                "hosts": [{"host": self.config.host, "port": self.config.port, "scheme": self.config.scheme}]
            }
            if self.config.api_key:
                connection_params["api_key"] = self.config.api_key
            # Add other potential connection_params from config (e.g., basic_auth, cloud_id)

            self.es = Elasticsearch(**connection_params)
            # Verify connection
            if not self.es.ping():
                raise ConnectionError("Could not connect to Elasticsearch.")
            logger.info("Successfully connected to Elasticsearch.")
            self._ensure_index()
        except Exception as e:
            logger.critical(
                f"Failed to initialize Elasticsearch connection or ensure index '{self.index_name}': {e}", exc_info=True)
            self.es = None  # Ensure ES client is None if initialization fails
            raise  # Re-raise to indicate critical failure

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
                f"Failed to check/create Elasticsearch index '{self.index_name}': {e}", exc_info=True)
            raise

    def _prepare_doc(self, data: PreprocessSingleResponse) -> Dict[str, Any]:
        """
        Prepares a single PreprocessSingleResponse for Elasticsearch indexing.
        Converts Pydantic model to a dictionary suitable for ES,
        handling dates and HttpUrls for JSON serialization.
        """
        # model_dump(mode='json') is the preferred way to convert Pydantic models
        # to JSON-compatible dictionaries, handling complex types automatically.
        doc = data.model_dump(mode='json')
        return doc

    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """Saves a single processed article to Elasticsearch."""
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
                f"Failed to save document {data.document_id} to Elasticsearch: {e}", exc_info=True)
            raise

    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """Saves a batch of processed articles to Elasticsearch using bulk API."""
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

        actions = [
            {
                "_index": self.index_name,
                "_id": data.document_id,
                "_source": self._prepare_doc(data)
            }
            for data in data_list
        ]
        try:
            success_count, errors = es_helpers.bulk(
                self.es, actions, stats_only=True)
            if errors:
                for error in errors:
                    logger.error(f"Elasticsearch bulk save error: {error}")
            logger.info(
                f"Successfully saved {success_count} of {len(data_list)} documents to Elasticsearch (with {len(errors)} errors).")
        except Exception as e:
            logger.error(
                f"Failed to save batch to Elasticsearch: {e}", exc_info=True)
            raise

    def close(self):
        """Closes the Elasticsearch client connection."""
        # The Python Elasticsearch client typically manages connections internally
        # and doesn't require explicit `close()` for HTTP connections like `psycopg2`.
        # However, it's good practice to have this method for consistency across backends.
        if self.es:
            logger.debug(
                "Elasticsearch client does not require explicit close for HTTP connections.")
            self.es = None  # Clear the reference


class PostgreSQLStorageBackend(StorageBackend):
    """
    Storage backend that saves processed articles to PostgreSQL.
    Requires psycopg2-binary client to be installed.
    """

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
        logger.info(
            f"Initialized PostgreSQLStorageBackend for table: {self.table_name} on {config.host}:{config.port}/{config.dbname}")

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Establishes and returns a new PostgreSQL connection."""
        try:
            conn = psycopg2.connect(**self.conn_params)
            conn.autocommit = False  # Manage transactions explicitly
            logger.debug("New PostgreSQL connection established.")
            return conn
        except Exception as e:
            logger.critical(
                f"Failed to establish PostgreSQL connection: {e}", exc_info=True)
            raise

    def initialize(self):
        """
        Connects to the database and ensures the table exists.
        Handles database creation if it doesn't exist, by connecting to default 'postgres' db.
        """
        # First, try to connect to 'postgres' database to create the target db if it doesn't exist
        temp_conn_params = self.conn_params.copy()
        # Temporarily remove target db name
        temp_db_name = temp_conn_params.pop("dbname")
        # Connect to default postgres db
        temp_conn_params["dbname"] = "postgres"

        temp_conn = None
        try:
            temp_conn = psycopg2.connect(**temp_conn_params)
            # Required for CREATE DATABASE
            temp_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = temp_conn.cursor()
            # Check if the target database exists
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
                f"Could not create PostgreSQL database '{temp_db_name}' (might already exist or permissions issue): {e}")
        finally:
            if temp_conn:
                temp_conn.close()

        # Now connect to the actual database and create the table
        try:
            self._connection = self._get_connection()
            self._create_table_if_not_exists()
            logger.info(f"PostgreSQL backend initialized and connected.")
        except Exception as e:
            logger.critical(
                f"Failed to initialize PostgreSQL backend: {e}", exc_info=True)
            self.close()  # Ensure any partial connection is closed
            raise

    def _create_table_if_not_exists(self):
        """Creates the PostgreSQL table if it doesn't exist."""
        if not self._connection:
            logger.error("No active PostgreSQL connection to create table.")
            raise ConnectionError("PostgreSQL connection not established.")

        cur = None
        try:
            cur = self._connection.cursor()
            # Define schema for processed articles. Adjust types as needed.
            # Using JSONB for nested Pydantic models (entities, additional_metadata, etc.)
            create_table_query = pg_sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                document_id VARCHAR(255) PRIMARY KEY,
                version VARCHAR(50),
                original_text TEXT,
                cleaned_text TEXT,
                cleaned_title TEXT,
                cleaned_excerpt TEXT,
                cleaned_author TEXT,
                temporal_metadata DATE,
                entities JSONB,
                language VARCHAR(10),
                cleaned_categories JSONB,
                cleaned_tags JSONB,
                cleaned_geographical_data JSONB,
                cleaned_embargo_date DATE,
                cleaned_media_asset_urls JSONB,
                additional_metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """).format(pg_sql.Identifier(self.table_name))
            cur.execute(create_table_query)
            self._connection.commit()
            logger.info(
                f"PostgreSQL table '{self.table_name}' ensured to exist.")
        except Exception as e:
            logger.critical(
                f"Failed to create PostgreSQL table '{self.table_name}': {e}", exc_info=True)
            if self._connection:
                self._connection.rollback()
            raise
        finally:
            if cur:
                cur.close()

    def _prepare_sql_data(self, data: PreprocessSingleResponse) -> Dict[str, Any]:
        """
        Prepares a single PreprocessSingleResponse for SQL insertion.
        Converts Pydantic models/types to suitable SQL types.
        """
        # Pydantic's .model_dump(mode='json') handles datetime/date serialization to ISO format strings,
        # HttpUrl to string, and nested Pydantic models to dicts (which are then JSON-serialized for JSONB columns).

        # Convert temporal_metadata string (YYYY-MM-DD) to date object if it's not None, for DATE type in PG
        temporal_metadata_date = None
        if data.temporal_metadata:
            try:
                temporal_metadata_date = datetime.strptime(
                    data.temporal_metadata, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(
                    f"Invalid temporal_metadata date format for document {data.document_id}: {data.temporal_metadata}. Storing as NULL.")

        # Convert embargo_date from date object to standard date for psycopg2
        cleaned_embargo_date = data.cleaned_embargo_date

        return {
            "document_id": data.document_id,
            "version": data.version,
            "original_text": data.original_text,
            "cleaned_text": data.cleaned_text,
            "cleaned_title": data.cleaned_title,
            "cleaned_excerpt": data.cleaned_excerpt,
            "cleaned_author": data.cleaned_author,
            "temporal_metadata": temporal_metadata_date,
            # Convert list of Entity models to JSON string
            "entities": json.dumps([entity.model_dump(mode='json') for entity in data.entities]),
            "language": data.language,
            "cleaned_categories": json.dumps(data.cleaned_categories) if data.cleaned_categories is not None else None,
            "cleaned_tags": json.dumps(data.cleaned_tags) if data.cleaned_tags is not None else None,
            "cleaned_geographical_data": json.dumps(data.cleaned_geographical_data) if data.cleaned_geographical_data is not None else None,
            "cleaned_embargo_date": cleaned_embargo_date,
            # Convert HttpUrl to string list then JSON
            "cleaned_media_asset_urls": json.dumps([str(url) for url in data.cleaned_media_asset_urls]) if data.cleaned_media_asset_urls is not None else None,
            "additional_metadata": json.dumps(data.additional_metadata) if data.additional_metadata is not None else None
        }

    def save(self, data: PreprocessSingleResponse, **kwargs: Any) -> None:
        """Saves a single processed article to PostgreSQL."""
        if not self._connection:
            logger.error(
                f"No active PostgreSQL connection. Skipping save for document {data.document_id}.")
            raise ConnectionError("PostgreSQL connection not established.")

        prepared_data = self._prepare_sql_data(data)
        cur = None
        try:
            cur = self._connection.cursor()

            # Using psycopg2.sql.Identifier for table and column names for safety against SQL injection
            # Using pg_sql.Literal for values is handled by execute with %s
            columns = pg_sql.SQL(', ').join(
                map(pg_sql.Identifier, prepared_data.keys()))
            placeholders = pg_sql.SQL(', ').join(
                pg_sql.Placeholder() * len(prepared_data))

            # Upsert logic: INSERT ... ON CONFLICT (document_id) DO UPDATE SET ...
            # Exclude document_id from the SET clause as it's the conflict target
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
            self._connection.commit()
            logger.debug(
                f"Saved single document {data.document_id} to PostgreSQL.")
        except Exception as e:
            logger.error(
                f"Failed to save document {data.document_id} to PostgreSQL: {e}", exc_info=True)
            if self._connection:
                self._connection.rollback()
            raise
        finally:
            if cur:
                cur.close()

    def save_batch(self, data_list: List[PreprocessSingleResponse], **kwargs: Any) -> None:
        """Saves a batch of processed articles to PostgreSQL using executemany."""
        if not self._connection:
            logger.error(
                "No active PostgreSQL connection. Skipping batch save.")
            raise ConnectionError("PostgreSQL connection not established.")
        if not data_list:
            logger.debug(
                "Attempted to save an empty batch to PostgreSQL. Skipping.")
            return

        cur = None
        try:
            cur = self._connection.cursor()

            # Get column names from the first item to construct the query
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
            self._connection.commit()
            logger.info(
                f"Saved batch of {len(data_list)} documents to PostgreSQL.")
        except Exception as e:
            logger.error(
                f"Failed to save batch to PostgreSQL: {e}", exc_info=True)
            if self._connection:
                self._connection.rollback()
            raise
        finally:
            if cur:
                cur.close()

    def close(self):
        """Closes the PostgreSQL connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("PostgreSQL connection closed.")
            except Exception as e:
                logger.error(
                    f"Error closing PostgreSQL connection: {e}", exc_info=True)
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

        # Determine which backends to use for this call
        backends_to_use = []
        if requested_backends:
            # If specific backends are requested, use them if they are also enabled in settings
            for backend_name in requested_backends:
                if backend_name in storage_config.enabled_backends:
                    backends_to_use.append(backend_name)
                else:
                    logger.warning(
                        f"Requested backend '{backend_name}' is not enabled in settings. Skipping.")
        else:
            # If no specific backends requested, use all enabled backends from settings
            backends_to_use = storage_config.enabled_backends

        if not backends_to_use:
            # Fallback to JSONL if no backends explicitly enabled or requested
            logger.info(
                "No storage backends enabled or requested. Defaulting to 'jsonl'.")
            backends_to_use = ["jsonl"]

        active_backends: List[StorageBackend] = []

        for backend_name in backends_to_use:
            backend_name_lower = backend_name.lower()

            if backend_name_lower not in cls._initialized_backends:
                # Backend not yet initialized, create and initialize it
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

                    backend.initialize()  # Initialize connection/resources
                    cls._initialized_backends[backend_name_lower] = backend
                    logger.info(
                        f"Storage backend '{backend_name}' successfully initialized.")
                    active_backends.append(backend)

                except (ValueError, ImportError, ConnectionError) as e:
                    logger.critical(
                        f"Failed to initialize storage backend '{backend_name}': {e}. This backend will be skipped.", exc_info=True)
                    # Do not re-raise a critical error here, allow other backends to proceed.
                    # The factory should return whatever it *could* initialize.
                except Exception as e:
                    logger.critical(
                        f"An unexpected error occurred during initialization of backend '{backend_name}': {e}. Skipping.", exc_info=True)
            else:
                # Backend already initialized, reuse it
                backend = cls._initialized_backends[backend_name_lower]
                active_backends.append(backend)
                logger.debug(
                    f"Reusing already initialized storage backend: {backend_name}.")

        return active_backends

    @classmethod
    def close_all_backends(cls):
        """Closes all initialized storage backend connections/resources."""
        logger.info("Attempting to close all initialized storage backends.")
        # Iterate over a copy
        for name, backend in list(cls._initialized_backends.items()):
            try:
                backend.close()
                logger.info(f"Storage backend '{name}' successfully closed.")
            except Exception as e:
                logger.error(
                    f"Error closing storage backend '{name}': {e}", exc_info=True)
            finally:
                # Remove from tracking dictionary
                del cls._initialized_backends[name]


# Ensure all backends are closed gracefully on program exit
atexit.register(StorageBackendFactory.close_all_backends)
