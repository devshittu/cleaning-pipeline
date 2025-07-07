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
        return {"status": "ok", "model_loaded": True}

    logger.error("Health check failed: SpaCy model not loaded.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SpaCy model is not loaded. Service is not ready."
    )


@app.post("/preprocess-single", response_model=PreprocessSingleResponse)
async def preprocess_single_article(request: PreprocessSingleRequest, http_request: Request):
    """
    Accepts a single structured article and returns the processed, standardized output.
    The document_id is carried over from the input payload.
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


def process_batch_in_background(articles: List[ArticleInput]):
    """
    Worker function to process a list of structured articles. This is intended to be run
    as a background task.
    """
    logger.info(
        f"Starting background task to process a batch of {len(articles)} articles.")

    for i, article in enumerate(articles):
        # Use the document_id from the payload for traceability
        document_id = article.document_id

        start_time = time.time()
        try:
            # Process each article, passing all relevant metadata
            processed_data = preprocessor.preprocess(
                text=article.text,
                title=article.title,
                excerpt=article.excerpt,
                author=article.author,
                reference_date=article.publication_date
            )

            duration = (time.time() - start_time) * 1000  # in ms
            logger.info(f"Processed batch item {i+1}/{len(articles)}. document_id={document_id}", extra={
                        "document_id": document_id, "duration_ms": duration})

        except Exception as e:
            # Log the failure and continue processing the rest of the batch,
            # preventing the entire task from failing. This is basic fault tolerance.
            logger.error(f"Error processing item {i+1} in batch. document_id={document_id}. Error: {e}",
                         exc_info=True, extra={"document_id": document_id})

    logger.info(
        f"Background batch processing completed for {len(articles)} articles.")


@app.post("/preprocess-batch", response_model=PreprocessBatchResponse)
async def preprocess_batch(request: PreprocessBatchRequest, background_tasks: BackgroundTasks):
    """
    Accepts a list of structured articles and processes them in a background task.
    This endpoint is non-blocking and returns an immediate acknowledgment.
    """
    articles = request.articles
    logger.info(
        f"Received request to process a batch of {len(articles)} articles.")

    # Add the processing task to FastAPI's background tasks queue
    background_tasks.add_task(process_batch_in_background, articles)

    # Return an immediate response. The actual results are not returned via this endpoint.
    return PreprocessBatchResponse(processed_articles=[])

