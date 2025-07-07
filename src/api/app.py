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
from src.core.processor import preprocessor
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


@app.on_event("startup")
async def startup_event():
    """Startup event for the Ingestion service."""
    logger.info("Ingestion Service starting up...")
    try:
        # Accessing the preprocessor ensures the model is loaded on startup
        _ = preprocessor.nlp
        logger.info("Ingestion Service startup complete. SpaCy model is ready.")
    except Exception as e:
        logger.critical(
            f"Failed to initialize preprocessor model at startup: {e}", exc_info=True)
        # We raise a critical exception to prevent the service from running if the model isn't loaded.
        raise RuntimeError(
            "Could not initialize service. Check logs for model loading errors.")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.
    Returns 200 OK if the service is running and the spaCy model is loaded.
    """
    if preprocessor.nlp is not None:
        # Also check Celery broker connection for a more complete health check
        try:
            with celery_app.connection_or_acquire() as connection:
                connection.info()  # Try to get info from broker
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

    # Use the document_id from the payload for traceability
    document_id = article.document_id
    logger.info(f"Received request for document_id={document_id}.", extra={
                "document_id": document_id, "endpoint": "/preprocess-single"})

    try:
        # Pass the text and all relevant metadata to the processor
        processed_data = preprocessor.preprocess(
            text=article.text,
            title=article.title,
            excerpt=article.excerpt,
            author=article.author,
            reference_date=article.publication_date
        )

        # Construct the response model using the input document_id
        response = PreprocessSingleResponse(
            document_id=document_id,
            version="1.0",
            **processed_data
        )

        duration = (time.time() - start_time) * 1000  # in ms
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
        # Send each article as a separate task to Celery
        # We send the article_input.model_dump() to ensure it's JSON serializable
        task = preprocess_article_task.delay(article_input.model_dump())
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
            "info": task.info  # Custom progress info if task updates it
        }
    elif task.state == 'SUCCESS':
        response = {
            "task_id": task.id,
            "status": task.state,
            "result": task.result,  # The actual processed data
            "message": "Task completed successfully."
        }
    elif task.state == 'FAILURE':
        response = {
            "task_id": task.id,
            "status": task.state,
            "error": str(task.info),  # Contains the exception or error details
            "message": "Task failed."
        }
    else:
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Unknown task state."
        }

    return response
