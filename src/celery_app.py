"""
src/celery_app.py

Defines the Celery application and tasks for asynchronous processing.
"""

import json
import logging
from celery import Celery
from celery import signals
from src.core.processor import TextPreprocessor
from src.schemas.data_models import ArticleInput, PreprocessSingleResponse
from src.utils.config_manager import ConfigManager
from typing import Dict, Any

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
    task_annotations=settings.celery.task_annotations
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


@celery_app.task(name="preprocess_article", bind=True)
def preprocess_article_task(self, article_data_json: str) -> Dict[str, Any]:
    """
    Celery task to preprocess a single article.
    It receives the article data as a JSON string to ensure proper serialization.
    """
    global preprocessor
    if preprocessor is None:
        # This is a fallback in case the signal handler failed, though it
        # should not be needed with the worker_process_init signal.
        logger.warning(
            "Preprocessor not initialized. Initializing within task.")
        preprocessor = TextPreprocessor()

    document_id = "unknown"  # Default for logging in case of early failure
    try:
        # Pydantic's model_validate_json deserializes the JSON string back into a Pydantic model.
        article_input = ArticleInput.model_validate_json(article_data_json)
        document_id = article_input.document_id  # Update document_id for logging

        logger.info(f"Celery task received article for document_id={document_id}.", extra={
                    "document_id": document_id})

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
            additional_metadata=article_input.additional_metadata
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

        logger.info(f"Celery task successfully processed document_id={document_id}.", extra={
                    "document_id": document_id})

        # Ensure the result is a dictionary with no Pydantic Url objects, as Celery's serializer cannot handle them.
        response_dict = response.model_dump()
        if response_dict.get('cleaned_source_url') is not None:
            response_dict['cleaned_source_url'] = str(
                response_dict['cleaned_source_url'])
        if response_dict.get('cleaned_media_asset_urls') is not None:
            response_dict['cleaned_media_asset_urls'] = [
                str(url) for url in response_dict['cleaned_media_asset_urls']]

        return response_dict
    except Exception as e:
        logger.error(f"Celery task failed for document_id={document_id}: {e}", exc_info=True, extra={
                     "document_id": document_id})
        # Reraise the exception for Celery to mark the task as failed
        raise

# src/celery_app.py
