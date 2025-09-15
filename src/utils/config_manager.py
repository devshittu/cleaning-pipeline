# src/utils/config_manager.py
"""
utils/config_manager.py

Handles loading application settings from a YAML configuration file
using Pydantic for validation and type-hinting.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import os


class GeneralSettings(BaseModel):
    """General application settings."""
    log_level: str = Field(
        "INFO", description="Set to INFO for production readiness, DEBUG for development.")
    gpu_enabled: bool = Field(
        False, description="Set to True to leverage GPU (e.g., RTX A4000).")


class IngestionServiceSettings(BaseModel):
    """Settings for the Ingestion Microservice."""
    port: int = Field(8000, description="Port for the Ingestion service API.")
    model_name: str = Field(
        "en_core_web_trf", description="The spaCy model to use for NER.")
    model_cache_dir: str = Field(
        "/app/.cache/spacy", description="Path for spaCy to cache models.")
    dateparser_languages: List[str] = Field(
        ["en"], description="Languages for dateparser to consider.")
    batch_processing_threads: int = Field(
        2, description="Number of threads for CLI batch processing.")

    # New setting for language detection confidence threshold
    langdetect_confidence_threshold: float = Field(
        0.9, description="Minimum confidence for language detection.")

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        protected_namespaces=()  # Suppress model_ namespace warnings
    )


class CelerySettings(BaseModel):
    """Settings for Celery task queue."""
    broker_url: str = Field("redis://redis:6379/0",
                            description="Redis as broker URL.")
    result_backend: str = Field(
        "redis://redis:6379/0", description="Redis as result backend URL.")
    task_acks_late: bool = Field(
        True, description="Acknowledge task only after it's done.")
    worker_prefetch_multiplier: int = Field(
        1, description="Only fetch one task at a time per worker process.")
    worker_concurrency: int = Field(
        4, description="Number of worker processes. Adjust based on CPU cores.")
    task_annotations: Dict[str, Dict[str, Any]] = Field(
        {'*': {'rate_limit': '300/m'}}, description="Task-specific annotations for Celery.")

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )


# NEW: Specific configurations for each storage backend
class JsonlStorageConfig(BaseModel):
    """Configuration for JSONL file storage."""
    # output_directory: str = Field(
    #     "./data/processed_output", description="Directory where JSONL files will be stored. Relative to project root."
    # )
    output_path: str = Field("/app/data/processed_articles.jsonl",
                             description="Default output path for JSONL.")



class ElasticsearchStorageConfig(BaseModel):
    """Configuration for Elasticsearch storage."""
    host: str = Field(
        "elasticsearch", description="Elasticsearch host (Docker service name or IP).")
    port: int = Field(9200, description="Elasticsearch port.")
    scheme: str = Field(
        "http", description="Connection scheme (http or https).")
    index_name: str = Field(
        "news_articles", description="Name of the Elasticsearch index.")
    api_key: Optional[str] = Field(
        None, description="Elasticsearch API key for authentication.")
    # Add other ES relevant fields like `cloud_id`, `basic_auth` etc. as needed


class PostgreSQLStorageConfig(BaseModel):
    """Configuration for PostgreSQL storage."""
    host: str = Field(
        "postgres", description="PostgreSQL host (Docker service name or IP).")
    port: int = Field(5432, description="PostgreSQL port.")
    dbname: str = Field("newsdb", description="PostgreSQL database name.")
    user: str = Field("user", description="PostgreSQL username.")
    password: str = Field("password", description="PostgreSQL password.")
    table_name: str = Field("processed_articles",
                            description="Table name for storing articles.")


class StorageSettings(BaseModel):
    """Overall settings for data storage backends."""
    # List of enabled backends that can be used. If empty, JSONL is the default.
    enabled_backends: List[str] = Field(
        ["jsonl"], description="List of storage backend names (e.g., ['jsonl', 'postgresql', 'elasticsearch']) that are enabled for use. If empty, 'jsonl' is used as the default."
    )
    # Optional configurations for each backend type
    jsonl: Optional[JsonlStorageConfig] = Field(
        None, description="JSONL storage specific configuration."
    )
    elasticsearch: Optional[ElasticsearchStorageConfig] = Field(
        None, description="Elasticsearch storage specific configuration."
    )
    postgresql: Optional[PostgreSQLStorageConfig] = Field(
        None, description="PostgreSQL storage specific configuration."
    )

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )


class FormatterConfig(BaseModel):
    """Logging formatter configuration."""
    class_: str = Field(..., alias="class",
                        description="The class path for the formatter (e.g., pythonjsonlogger.jsonlogger.JsonFormatter).")
    format: str = Field(..., description="The log format string.")

    model_config = SettingsConfigDict(
        extra='allow',  # Allow additional fields like format
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )


class HandlerConfig(BaseModel):
    """Logging handler configuration."""
    class_: str = Field(..., alias="class",
                        description="The class path for the handler (e.g., logging.StreamHandler).")
    formatter: Optional[str] = Field(
        None, description="The formatter name to use for this handler.")
    stream: Optional[str] = Field(
        None, description="The stream for StreamHandler (e.g., ext://sys.stdout).")
    filename: Optional[str] = Field(
        None, description="The log file path for file-based handlers.")
    maxBytes: Optional[int] = Field(
        None, description="Maximum file size for RotatingFileHandler.")
    backupCount: Optional[int] = Field(
        None, description="Number of backup files for RotatingFileHandler.")

    model_config = SettingsConfigDict(
        extra='allow',  # Allow additional fields
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    version: int
    disable_existing_loggers: bool
    formatters: Dict[str, FormatterConfig]
    handlers: Dict[str, HandlerConfig]
    root: Dict[str, Any]
    loggers: Dict[str, Dict[str, Any]]

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )


class Settings(BaseSettings):
    """Main settings model, loaded from a YAML file."""
    general: GeneralSettings
    ingestion_service: IngestionServiceSettings
    celery: CelerySettings
    storage: StorageSettings  # Updated to the new StorageSettings
    logging: LoggingConfig

    model_config = SettingsConfigDict(
        protected_namespaces=()
    )


class ConfigManager:
    """
    Singleton class to manage and load application settings.
    """
    _settings: Optional[Settings] = None

    @staticmethod
    def get_settings() -> Settings:
        """
        Loads and returns the application settings. This is a singleton
        method that ensures the config is loaded only once.
        """
        if ConfigManager._settings is None:
            config_path = os.path.join(os.path.dirname(
                __file__), '../../config/settings.yaml')
            if not os.path.exists(config_path):
                raise FileNotFoundError(
                    f"Configuration file not found at {config_path}")

            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            try:
                ConfigManager._settings = Settings.model_validate(config_data)
            except Exception as e:
                # Log a critical error if settings validation fails
                # Using a basic print/logger.error here as full logging might not be set up yet
                print(f"CRITICAL ERROR: Failed to validate settings from {config_path}. "
                      f"Please check your settings.yaml file against the schema. Error: {e}", file=sys.stderr)
                raise RuntimeError(
                    "Failed to load and validate application settings.") from e

        return ConfigManager._settings


if __name__ == '__main__':
    # Example usage for testing the ConfigManager
    import sys
    try:
        settings = ConfigManager.get_settings()
        print("--- Loaded Settings ---")
        print(f"Log Level: {settings.general.log_level}")
        print(f"GPU Enabled: {settings.general.gpu_enabled}")
        print(f"Ingestion Port: {settings.ingestion_service.port}")
        print(f"spaCy Model: {settings.ingestion_service.model_name}")
        print(f"Celery Broker URL: {settings.celery.broker_url}")
        print(f"Enabled Storage Backends: {settings.storage.enabled_backends}")
        if settings.storage.jsonl:
            print(
                f"JSONL Output Path: {settings.storage.jsonl.output_path}")
        if settings.storage.elasticsearch:
            print(f"ES Host: {settings.storage.elasticsearch.host}")
        if settings.storage.postgresql:
            print(f"PG Host: {settings.storage.postgresql.host}")
        print(
            f"Log Handler: {settings.logging.handlers['ingestion_file'].filename}")
    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
