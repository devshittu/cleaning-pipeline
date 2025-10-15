"""
api/app.py

Defines the FastAPI application for the Ingestion Microservice,
exposing RESTful endpoints for preprocessing.

FIXES APPLIED:
- Fix #5: Batch size validation and rate limiting
- Fix #7: Prometheus metrics integration
- Fix #10: Request ID tracing middleware
- Fix #11: API versioning with /v1 prefix
"""

import logging
import time
import uuid
import json
from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Request, UploadFile, File, Form, Header, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import List, Dict, Any, Optional

# Prometheus instrumentation (Fix #7)
from prometheus_fastapi_instrumentator import Instrumentator

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
from src.storage.backends import StorageBackendFactory

# Import Celery app and task
from src.celery_app import celery_app, preprocess_article_task

# Load settings and configure logging
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Constants for rate limiting
MAX_BATCH_SIZE = 1000  # Maximum articles per batch request
MAX_FILE_SIZE_MB = 50  # Maximum file upload size

# Initialize FastAPI app with versioning
app = FastAPI(
    title="Data Ingestion & Preprocessing Service",
    description="A microservice for ingesting, cleaning, and enriching unstructured text. "
                "Optimized for news article processing pipelines.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Prometheus metrics instrumentation (Fix #7)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
logger.info("Prometheus metrics enabled at /metrics endpoint")

# Global TextPreprocessor instance per Uvicorn worker process
preprocessor = TextPreprocessor()


# MIDDLEWARE: Request ID tracing (Fix #10)
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    Adds X-Request-ID header to all requests for distributed tracing.
    If client provides X-Request-ID, it's preserved; otherwise, a new UUID is generated.
    
    IMPROVEMENT: Enables end-to-end request tracking across microservices.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    # Log the incoming request
    logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={"request_id": request_id, "client_ip": request.client.host}
    )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    # Log the response
    logger.info(
        f"Outgoing response: {response.status_code}",
        extra={"request_id": request_id, "status_code": response.status_code}
    )

    return response


# MIDDLEWARE: Request timing
@app.middleware("http")
async def add_timing_middleware(request: Request, call_next):
    """
    Adds X-Process-Time header showing request processing duration.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response


# Root endpoint
@app.get("/", tags=["General"])
async def root():
    """
    Root endpoint providing service information.
    """
    return {
        "service": "Data Ingestion & Preprocessing Service",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "api_version": "v1",
        "endpoints": {
            "health": "GET /health",
            "metrics": "GET /metrics",
            "preprocess_single": "POST /v1/preprocess",
            "preprocess_batch": "POST /v1/preprocess/batch",
            "preprocess_file": "POST /v1/preprocess/batch-file",
            "task_status": "GET /v1/preprocess/status/{task_id}"
        }
    }


@app.get("/health", status_code=status.HTTP_200_OK, tags=["General"])
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

        return {
            "status": "ok",
            "model_loaded": True,
            "spacy_model": settings.ingestion_service.model_name,
            "celery_broker_connected": broker_connected,
            "gpu_enabled": settings.general.gpu_enabled
        }

    logger.error("Health check failed: SpaCy model not loaded.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SpaCy model is not loaded. Service is not ready."
    )


# API v1 Router (Fix #11: Versioning)
v1_router = APIRouter(prefix="/v1", tags=["v1"])


@v1_router.post("/preprocess", response_model=PreprocessSingleResponse, status_code=status.HTTP_200_OK)
async def preprocess_single_article(
    request: PreprocessSingleRequest,
    http_request: Request,
    x_request_id: Optional[str] = Header(None)
):
    """
    Accepts a single structured article and returns the processed, standardized output.
    This endpoint processes synchronously for immediate feedback.
    
    IMPROVEMENTS:
    - Request ID tracing via X-Request-ID header
    - Detailed logging with request context
    """
    article = request.article
    start_time = time.time()
    request_id = http_request.state.request_id

    document_id = article.document_id
    logger.info(
        f"Received request for document_id={document_id}.",
        extra={
            "document_id": document_id,
            "endpoint": "/v1/preprocess",
            "request_id": request_id
        }
    )

    try:

        # Extract custom cleaning config if provided
        custom_config = None
        if request.cleaning_config:
            custom_config = request.cleaning_config.model_dump(exclude_none=True)

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
            geographical_data=article.geographical_data,
            embargo_date=article.embargo_date,
            sentiment=article.sentiment,
            word_count=article.word_count,
            publisher=article.publisher,
            additional_metadata=article.additional_metadata,
            custom_cleaning_config=custom_config  # ADD THIS LINE
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

        # Persist to requested storage backends if specified
        persist_to_backends = request.persist_to_backends
        if persist_to_backends:
            backends = StorageBackendFactory.get_backends(persist_to_backends)
            for backend in backends:
                backend.save(response)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"Successfully processed document_id={document_id} in {duration:.2f}ms.",
            extra={
                "document_id": document_id,
                "duration_ms": duration,
                "request_id": request_id
            }
        )

        return response

    except ValidationError as e:
        logger.warning(
            f"Invalid request payload for /v1/preprocess: {e.errors()}",
            extra={"document_id": document_id, "request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {e.errors()}"
        )
    except Exception as e:
        logger.error(
            f"Internal server error during single article preprocessing: {e}",
            exc_info=True,
            extra={"document_id": document_id, "request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during preprocessing."
        )


@v1_router.post("/preprocess/batch", status_code=status.HTTP_202_ACCEPTED)
async def submit_batch(request: PreprocessBatchRequest, http_request: Request):
    """
    Accepts a list of structured articles and submits them as a batch job to Celery.
    Returns a list of task IDs for tracking. This endpoint is non-blocking.
    
    IMPROVEMENTS:
    - Fix #5: Batch size validation (max 1000 articles)
    - Request ID tracing
    """
    articles = request.articles
    request_id = http_request.state.request_id

    logger.info(
        f"Received request to submit a batch job for {len(articles)} articles to Celery.",
        extra={"request_id": request_id, "batch_size": len(articles)}
    )

    # Fix #5: Validate batch size
    if not articles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch request must contain at least one article."
        )

    if len(articles) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size ({len(articles)}) exceeds maximum allowed ({MAX_BATCH_SIZE}). "
            f"Please split your batch into smaller chunks."
        )

    task_ids = []
    for i, article_input in enumerate(articles):
        task = preprocess_article_task.delay(
            article_input.model_dump_json(), None)
        task_ids.append(task.id)
        logger.debug(
            f"Submitted article {i+1} as Celery task: {task.id}",
            extra={
                "document_id": article_input.document_id,
                "task_id": task.id,
                "request_id": request_id
            }
        )

    return {
        "message": "Batch processing job submitted to Celery.",
        "task_ids": task_ids,
        "batch_size": len(articles),
        "request_id": request_id
    }


@v1_router.post("/preprocess/batch-file", status_code=status.HTTP_202_ACCEPTED)
async def submit_batch_file(
    http_request: Request,
    file: UploadFile = File(...),
    persist_to_backends: str = Form(None)
):
    """
    Accepts a JSONL file upload containing structured articles (one per line) and submits them as a batch job to Celery.
    Returns a list of task IDs for tracking. This endpoint is non-blocking.
    Handles validation and skips invalid lines with logging.
    Optionally specifies storage backends (e.g., 'jsonl,elasticsearch') for persisting processed results.
    
    IMPROVEMENTS:
    - Fix #5: File size validation (max 50MB)
    - Request ID tracing
    """
    request_id = http_request.state.request_id

    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)  # Reset to beginning

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed ({MAX_FILE_SIZE_MB}MB)"
        )

    try:
        contents = await file.read()
        lines = contents.decode('utf-8').splitlines()
    except Exception as e:
        logger.error(
            f"Failed to read uploaded file: {e}",
            extra={"request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file upload or encoding error."
        )

    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must contain at least one article."
        )

    # Fix #5: Validate total articles in file
    if len(lines) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File contains {len(lines)} articles, exceeding maximum allowed ({MAX_BATCH_SIZE}). "
            f"Please split your file into smaller chunks."
        )

    task_ids = []
    skipped_lines = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        try:
            article_data = json.loads(line)
            article_input = ArticleInput.model_validate(article_data)
            task = preprocess_article_task.delay(
                json.dumps(article_data), persist_to_backends)
            task_ids.append(task.id)
            logger.debug(
                f"Submitted article {i+1} from file as Celery task: {task.id}",
                extra={
                    "document_id": article_input.document_id,
                    "task_id": task.id,
                    "request_id": request_id
                }
            )
        except json.JSONDecodeError as e:
            skipped_lines += 1
            logger.warning(
                f"Skipping malformed JSON line in uploaded file (line {i+1}): {e}",
                extra={"request_id": request_id}
            )
        except ValidationError as e:
            skipped_lines += 1
            logger.warning(
                f"Invalid article data in uploaded file line {i+1}: {e.errors()}",
                extra={"request_id": request_id}
            )

    if not task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid articles found in the uploaded file."
        )

    return {
        "message": "Batch file processing job submitted to Celery.",
        "task_ids": task_ids,
        "total_articles": len(task_ids),
        "skipped_lines": skipped_lines,
        "request_id": request_id
    }


@v1_router.get("/preprocess/status/{task_id}")
async def get_batch_job_status(task_id: str, http_request: Request):
    """
    Retrieves the status and result of a Celery task by its ID.
    
    IMPROVEMENT: Request ID tracing
    """
    request_id = http_request.state.request_id
    task = celery_app.AsyncResult(task_id)

    if task.state == 'PENDING':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task is pending or unknown (might not have started yet or task ID is invalid).",
            "request_id": request_id
        }
    elif task.state == 'STARTED':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task has started processing.",
            "request_id": request_id
        }
    elif task.state == 'PROGRESS':
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Task is in progress.",
            "info": task.info,
            "request_id": request_id
        }
    elif task.state == 'SUCCESS':
        response = {
            "task_id": task.id,
            "status": task.state,
            "result": task.result,
            "message": "Task completed successfully.",
            "request_id": request_id
        }
    elif task.state == 'FAILURE':
        response = {
            "task_id": task.id,
            "status": task.state,
            "error": str(task.info),
            "message": "Task failed.",
            "request_id": request_id
        }
    else:
        response = {
            "task_id": task.id,
            "status": task.state,
            "message": "Unknown task state.",
            "request_id": request_id
        }

    return response


# Include v1 router in the main app
app.include_router(v1_router)

# api/app.py
