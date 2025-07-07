"""
src/celery_app.py

Defines the Celery application instance and registers tasks.
This file is the entry point for Celery workers.
"""

import os
import logging
from celery import Celery
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging
# Import preprocessor for task execution
from src.core.processor import preprocessor
from src.schemas.data_models import ArticleInput, PreprocessFileResult, PreprocessSingleResponse
from pydantic import ValidationError
import time
import json
from typing import Optional, Dict, Any  # <--- ADDED Dict and Any here

# Load settings and configure logging
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Initialize Celery app
# Use environment variables for broker/backend for better Docker integration
celery_app = Celery(
    "ingestion_tasks",
    broker=os.getenv("CELERY_BROKER_URL", settings.celery.broker_url),
    backend=os.getenv("CELERY_RESULT_BACKEND", settings.celery.result_backend)
)

# Configure Celery from settings.yaml
celery_app.conf.update(
    task_acks_late=settings.celery.task_acks_late,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    worker_concurrency=settings.celery.worker_concurrency,
    task_annotations=settings.celery.task_annotations
)

# Optional: Ensure spaCy model is loaded when worker starts
# This is crucial for performance and avoiding re-loading per task


@celery_app.on_after_configure.connect
def setup_spacy_model(sender, **kwargs):
    """
    Ensures the spaCy model is loaded once per Celery worker process.
    """
    logger.info("Celery worker starting up. Initializing spaCy model...")
    try:
        _ = preprocessor.nlp
        logger.info("SpaCy model loaded successfully in Celery worker.")
    except Exception as e:
        logger.critical(
            f"Failed to load spaCy model in Celery worker: {e}", exc_info=True)
        raise RuntimeError(
            "Celery worker could not start due to spaCy model loading failure.")


@celery_app.task(bind=True, name="preprocess_article_task")
def preprocess_article_task(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Celery task to preprocess a single article.
    This task is designed to be robust and fault-tolerant.
    """
    document_id = article_data.get("document_id", "N/A")
    logger.info(f"Celery task received for document_id={document_id}. Task ID: {self.request.id}", extra={
                "document_id": document_id, "task_id": self.request.id})
    start_time = time.time()

    try:
        # 1. Input Data Validation (re-validate inside task for robustness)
        input_article = ArticleInput.model_validate(article_data)

        # 2. Core Processing
        processed_data_dict = preprocessor.preprocess(
            text=input_article.text,
            title=input_article.title,
            excerpt=input_article.excerpt,
            author=input_article.author,
            reference_date=input_article.publication_date
        )

        # 3. Output Data Validation and return as dictionary
        response = PreprocessSingleResponse(
            document_id=input_article.document_id,
            version="1.0",
            **processed_data_dict
        )

        duration = (time.time() - start_time) * 1000  # in ms
        logger.info(f"Celery task completed for document_id={document_id} in {duration:.2f}ms.", extra={
                    "document_id": document_id, "task_id": self.request.id, "duration_ms": duration})

        # Return the dictionary representation of the Pydantic model
        return response.model_dump()

    except ValidationError as e:
        logger.error(f"Celery task validation failed for document_id={document_id}. Error: {e.errors()}", extra={
                     "document_id": document_id, "task_id": self.request.id, "raw_input_sample": str(article_data)[:200]})
        # Optionally, raise a custom exception or return a specific error structure
        return {"error": "ValidationError", "details": e.errors(), "document_id": document_id}
    except Exception as e:
        logger.error(f"Celery task failed for document_id={document_id}. Error: {e}", exc_info=True, extra={
                     "document_id": document_id, "task_id": self.request.id})
        # Implement retry logic if desired
        # raise self.retry(exc=e, countdown=60, max_retries=3)
        return {"error": "ProcessingError", "details": str(e), "document_id": document_id}
