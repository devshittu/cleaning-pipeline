"""
src/celery_app.py

Defines the Celery application and tasks for asynchronous processing.

FIXES APPLIED:
- Fix #8: Enhanced retry logic with exponential backoff and jitter
- FIXED: Added custom_cleaning_config parameter support
"""

import json
import logging
from celery import Celery
from celery import signals
from src.core.processor import TextPreprocessor
from src.schemas.data_models import ArticleInput, PreprocessSingleResponse
from src.utils.config_manager import ConfigManager
from src.storage.backends import StorageBackendFactory
from typing import Dict, Any, Optional

settings = ConfigManager.get_settings()
logger = logging.getLogger("ingestion_service")

# Initialize the Celery app with a specific name and broker/backend from settings.
celery_app = Celery(
    "ingestion_service",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend
)

# Apply Celery configurations from settings.
celery_app.conf.update(
    task_acks_late=settings.celery.task_acks_late,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    worker_concurrency=settings.celery.worker_concurrency,
    task_annotations=settings.celery.task_annotations,
    # Additional configurations for better reliability
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
    broker_connection_retry_on_startup=True,
)

# A global variable to hold the TextPreprocessor instance per worker process.
# It will be set by the signal handler below.
preprocessor = None


@signals.worker_process_init.connect
def initialize_preprocessor(**kwargs):
    """
    This signal handler runs when each Celery worker process is initialized.
    It's the perfect place to load the heavy spaCy model to ensure a clean
    GPU context for each worker.
    """
    global preprocessor
    logger.info(
        "Celery worker process initializing. Loading TextPreprocessor instance.")
    preprocessor = TextPreprocessor()
    logger.info(
        "TextPreprocessor initialized successfully in Celery worker.")


@signals.worker_process_shutdown.connect
def cleanup_preprocessor(**kwargs):
    """
    Signal handler for worker process shutdown.
    Properly closes TextPreprocessor resources.
    """
    global preprocessor
    if preprocessor:
        logger.info(
            "Celery worker shutting down. Cleaning up TextPreprocessor.")
        preprocessor.close()
        preprocessor = None


@celery_app.task(
    name="preprocess_article",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute initial delay
    autoretry_for=(Exception,),  # Retry on any exception
    retry_backoff=True,  # Enable exponential backoff
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True,  # Add randomness to prevent thundering herd
    acks_late=True,  # Acknowledge task only after completion
    reject_on_worker_lost=True  # Reject task if worker dies
)
def preprocess_article_task(
    self,
    article_data_json: str,
    custom_cleaning_config_json: Optional[str] = None
) -> Dict[str, Any]:
    """
    Celery task to preprocess a single article.
    It receives the article data as a JSON string to ensure proper serialization.
    Optionally accepts custom cleaning configuration as JSON string.
    
    Args:
        article_data_json: JSON string of article data
        custom_cleaning_config_json: Optional JSON string of custom cleaning config
        
    Returns:
        Dictionary with processed article data
    
    IMPROVEMENTS:
    - Fix #8: Exponential backoff with jitter for retries
    - Better error handling and logging
    - Automatic retry on transient failures
    - Support for custom cleaning configuration
    """
    global preprocessor
    if preprocessor is None:
        # This is a fallback in case the signal handler failed, though it
        # should not be needed with the worker_process_init signal.
        logger.warning(
            "Preprocessor not initialized in worker_process_init. Initializing within task.")
        preprocessor = TextPreprocessor()

    document_id = "unknown"  # Default for logging in case of early failure
    try:
        # Parse custom cleaning config if provided
        custom_cleaning_config = None
        if custom_cleaning_config_json:
            try:
                custom_cleaning_config = json.loads(
                    custom_cleaning_config_json)
                logger.debug(
                    f"Using custom cleaning config: {custom_cleaning_config}",
                    extra={"task_id": self.request.id}
                )
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse custom_cleaning_config_json: {e}. Using default config.",
                    extra={"task_id": self.request.id}
                )

        # Pydantic's model_validate_json deserializes the JSON string back into a Pydantic model.
        article_input = ArticleInput.model_validate_json(article_data_json)
        document_id = article_input.document_id  # Update document_id for logging

        logger.info(
            f"Celery task {self.request.id} processing document_id={document_id}.",
            extra={
                "document_id": document_id,
                "task_id": self.request.id,
                "retry_count": self.request.retries
            }
        )

        processed_data = preprocessor.preprocess(
            document_id=article_input.document_id,
            text=article_input.text,
            title=article_input.title,
            excerpt=article_input.excerpt,
            author=article_input.author,
            publication_date=article_input.publication_date,
            revision_date=article_input.revision_date,
            source_url=article_input.source_url,
            categories=article_input.categories,
            tags=article_input.tags,
            media_asset_urls=article_input.media_asset_urls,
            geographical_data=article_input.geographical_data,
            embargo_date=article_input.embargo_date,
            sentiment=article_input.sentiment,
            word_count=article_input.word_count,
            publisher=article_input.publisher,
            additional_metadata=article_input.additional_metadata,
            custom_cleaning_config=custom_cleaning_config  # Pass custom config
        )

        response = PreprocessSingleResponse(
            document_id=document_id,
            version="1.0",
            original_text=processed_data.get("original_text", ""),
            cleaned_text=processed_data.get("cleaned_text", ""),
            cleaned_title=processed_data.get("cleaned_title"),
            cleaned_excerpt=processed_data.get("cleaned_excerpt"),
            cleaned_author=processed_data.get("cleaned_author"),
            cleaned_publication_date=processed_data.get(
                "cleaned_publication_date"),
            cleaned_revision_date=processed_data.get("cleaned_revision_date"),
            cleaned_source_url=processed_data.get("cleaned_source_url"),
            cleaned_categories=processed_data.get("cleaned_categories"),
            cleaned_tags=processed_data.get("cleaned_tags"),
            cleaned_media_asset_urls=processed_data.get(
                "cleaned_media_asset_urls"),
            cleaned_geographical_data=processed_data.get(
                "cleaned_geographical_data"),
            cleaned_embargo_date=processed_data.get("cleaned_embargo_date"),
            cleaned_sentiment=processed_data.get("cleaned_sentiment"),
            cleaned_word_count=processed_data.get("cleaned_word_count"),
            cleaned_publisher=processed_data.get("cleaned_publisher"),
            temporal_metadata=processed_data.get("temporal_metadata"),
            entities=processed_data.get("entities", []),
            cleaned_additional_metadata=processed_data.get(
                "cleaned_additional_metadata")
        )

        # Persist to storage backends (use default backends for Celery tasks)
        try:
            backends = StorageBackendFactory.get_backends()
            for backend in backends:
                backend.save(response)
        except Exception as storage_error:
            # Log storage error but don't fail the entire task
            logger.error(
                f"Failed to persist document_id={document_id} to storage backends: {storage_error}",
                exc_info=True,
                extra={
                    "document_id": document_id,
                    "task_id": self.request.id
                }
            )
            # Optionally, you can decide whether to retry on storage failures
            # For now, we log and continue

        logger.info(
            f"Celery task {self.request.id} successfully processed document_id={document_id}.",
            extra={
                "document_id": document_id,
                "task_id": self.request.id
            }
        )

        # Ensure the result is a dictionary with no Pydantic Url objects,
        # as Celery's serializer cannot handle them.
        response_dict = response.model_dump()
        if response_dict.get('cleaned_source_url') is not None:
            response_dict['cleaned_source_url'] = str(
                response_dict['cleaned_source_url'])
        if response_dict.get('cleaned_media_asset_urls') is not None:
            response_dict['cleaned_media_asset_urls'] = [
                str(url) for url in response_dict['cleaned_media_asset_urls']]

        return response_dict

    except Exception as e:
        logger.error(
            f"Celery task {self.request.id} failed for document_id={document_id}: {e}",
            exc_info=True,
            extra={
                "document_id": document_id,
                "task_id": self.request.id,
                "retry_count": self.request.retries
            }
        )

        # Check if we should retry
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying task {self.request.id} for document_id={document_id} "
                f"(attempt {self.request.retries + 1}/{self.max_retries})",
                extra={
                    "document_id": document_id,
                    "task_id": self.request.id
                }
            )

        # Reraise the exception for Celery to handle retry logic
        raise

# src/celery_app.py
