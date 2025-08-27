"""
api/app.py

Defines the FastAPI application for the Ingestion Microservice,
exposing RESTful endpoints for preprocessing.
"""

import logging
import time
import uuid
from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Request
from pydantic import ValidationError
from typing import List, Dict, Any

from src.schemas.data_models import (
    ArticleInput,
    PreprocessSingleRequest,
    PreprocessSingleResponse,
    PreprocessBatchRequest,
    PreprocessBatchResponse
)
from src.core.processor import TextPreprocessor
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging

# Import Celery app and task
from src.celery_app import celery_app, preprocess_article_task

# Load settings and configure logging
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Initialize FastAPI app
app = FastAPI(
    title="Data Ingestion & Preprocessing Service (Stage 1)",
    description="A microservice for ingesting, cleaning, and enriching unstructured text.",
    version="1.0.0"
)

# This is a global variable. A new TextPreprocessor will be loaded once per Uvicorn worker process.
# This approach is safe and efficient.
preprocessor = TextPreprocessor()


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.
    Returns 200 OK if the service is running and the spaCy model is loaded.
    """
    if preprocessor.nlp is not None:
        try:
            with celery_app.connection_or_acquire() as connection:
                connection.info()
            broker_connected = True
        except Exception as e:
            logger.error(f"Celery broker connection failed: {e}")
            broker_connected = False

        return {"status": "ok", "model_loaded": True, "celery_broker_connected": broker_connected}

    logger.error("Health check failed: SpaCy model not loaded.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SpaCy model is not loaded. Service is not ready."
    )


@app.post("/preprocess-single", response_model=PreprocessSingleResponse)
async def preprocess_single_article(request: PreprocessSingleRequest, http_request: Request):
    """
    Accepts a single structured article and returns the processed, standardized output.
    This endpoint processes synchronously for immediate feedback.
    """
    article = request.article
    start_time = time.time()

    document_id = article.document_id
    logger.info(f"Received request for document_id={document_id}.", extra={
                "document_id": document_id, "endpoint": "/preprocess-single"})

    try:
        processed_data = preprocessor.preprocess(
            document_id=article.document_id,
            text=article.text,
            title=article.title,
            excerpt=article.excerpt,
            author=article.author,
            publication_date=article.publication_date,
            revision_date=article.revision_date,
            source_url=article.source_url,
            categories=article.categories,
            tags=article.tags,
            media_asset_urls=article.media_asset_urls,
            additional_metadata=article.additional_metadata
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
            temporal_metadata=processed_data.get("temporal_metadata"),
            entities=processed_data.get("entities", []),
            cleaned_additional_metadata=processed_data.get(
                "cleaned_additional_metadata")
        )

        duration = (time.time() - start_time) * 1000
        logger.info(f"Successfully processed document_id={document_id} in {duration:.2f}ms.", extra={
                    "document_id": document_id, "duration_ms": duration})

        return response

    except ValidationError as e:
        logger.warning(
            f"Invalid request payload for /preprocess-single: {e.errors()}", extra={"document_id": document_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid input: {e.errors()}")
    except Exception as e:
        logger.error(f"Internal server error during single article preprocessing: {e}", exc_info=True, extra={
                     "document_id": document_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Internal server error during preprocessing.")


@app.post("/submit-batch-job", status_code=status.HTTP_202_ACCEPTED)
async def submit_batch_job(request: PreprocessBatchRequest):
    """
    Accepts a list of structured articles and submits them as a batch job to Celery.
    Returns a list of task IDs for tracking. This endpoint is non-blocking.
    """
    articles = request.articles
    logger.info(
        f"Received request to submit a batch job for {len(articles)} articles to Celery.")

    if not articles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Batch request must contain at least one article.")

    task_ids = []
    for i, article_input in enumerate(articles):
        task = preprocess_article_task.delay(article_input.model_dump_json())
        task_ids.append(task.id)
        logger.debug(f"Submitted article {i+1} as Celery task: {task.id}", extra={
                     "document_id": article_input.document_id, "task_id": task.id})

    return {"message": "Batch processing job submitted to Celery.", "task_ids": task_ids}


@app.get("/batch-job-status/{task_id}")
async def get_batch_job_status(task_id: str):
    """
    Retrieves the status and result of a Celery task by its ID.
    """
    task = celery_app.AsyncResult(task_id)

    if task.state == 'PENDING':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task is pending or unknown (might not have started yet or task ID is invalid)."
        }
    elif task.state == 'STARTED':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task has started processing."
        }
    elif task.state == 'PROGRESS':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task is in progress.",
            "info": task.info
        }
    elif task.state == 'SUCCESS':
        response = {
            "task_id": task.id,
            "status": task.state,
            "result": task.result,
            "message": "Task completed successfully."
        }
    elif task.state == 'FAILURE':
        response = {
            "task_id": task.id,
            "status": task.state,
            "error": str(task.info),
            "message": "Task failed."
        }
    else:
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Unknown task state."
        }

    return response

# api/app.py
