"""
utils/config_manager.py

Handles loading application settings from a YAML configuration file
using Pydantic for validation and type-hinting.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import os


class GeneralSettings(BaseModel):
    """General application settings."""
    log_level: str
    gpu_enabled: bool


class IngestionServiceSettings(BaseModel):
    """Settings for the Ingestion Microservice."""
    port: int
    model_name: str
    model_cache_dir: str
    dateparser_languages: List[str]
    batch_processing_threads: int

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        protected_namespaces=()  # Suppress model_ namespace warnings
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

            ConfigManager._settings = Settings.model_validate(config_data)

        return ConfigManager._settings


if __name__ == '__main__':
    # Example usage for testing the ConfigManager
    settings = ConfigManager.get_settings()
    print("--- Loaded Settings ---")
    print(f"Log Level: {settings.general.log_level}")
    print(f"GPU Enabled: {settings.general.gpu_enabled}")
    print(f"Ingestion Port: {settings.ingestion_service.port}")
    print(f"spaCy Model: {settings.ingestion_service.model_name}")
    print(
        f"Log Handler: {settings.logging.handlers['ingestion_file'].filename}")
