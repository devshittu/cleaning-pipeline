"""
utils/logger.py

Configures a structured, JSON-formatted logger for the application.
"""

import logging
import logging.config
from pythonjsonlogger.jsonlogger import JsonFormatter
import os
import yaml
from src.utils.config_manager import ConfigManager


class CustomJsonFormatter(JsonFormatter):
    """
    Custom JSON formatter to allow adding extra fields to log records if needed.
    Currently a placeholder for future customization.
    """

    def add_fields(self, log_record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, message_dict)
        # Add custom fields here if needed in the future
        # Example: log_record['service_name'] = os.getenv("SERVICE_NAME", "ingestion_service")


def setup_logging(config_path: str = "./config/settings.yaml"):
    """
    Sets up structured logging based on the configuration file.
    Ensures log directories exist and falls back to basic logging if configuration fails.
    """
    if not os.path.exists(config_path):
        logging.warning(
            f"Logging configuration file not found at {config_path}. Using default console logging."
        )
        logging.basicConfig(
            level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        log_config = config.get("logging")
        if log_config:
            # Ensure log directories exist for file-based handlers
            for handler_name, handler_config in log_config.get("handlers", {}).items():
                if 'filename' in handler_config:
                    log_dir = os.path.dirname(handler_config['filename'])
                    if log_dir and not os.path.exists(log_dir):
                        os.makedirs(log_dir, exist_ok=True)
            logging.config.dictConfig(log_config)
            logging.info("Logging configured successfully.")
        else:
            logging.warning(
                "No 'logging' section found in settings.yaml. Using default console logging."
            )
            logging.basicConfig(
                level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

    except Exception as e:
        logging.error(
            f"Error setting up logging from {config_path}: {e}", exc_info=True
        )
        logging.basicConfig(
            level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Set the ingestion_service logger's level from settings
    settings = ConfigManager.get_settings()
    ingestion_logger = logging.getLogger("ingestion_service")
    ingestion_logger.setLevel(settings.general.log_level)


if __name__ == "__main__":
    # Example usage for testing the logger configuration
    setup_logging()
    logger = logging.getLogger("ingestion_service")
    logger.info("This is an info message.", extra={
                'extra_field': 'value', 'user_id': '123'})
    logger.warning("This is a warning message.", extra={'status_code': 404})
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("An error occurred.", exc_info=True)
