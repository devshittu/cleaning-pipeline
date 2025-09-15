"""
main.py

Contains the core CLI logic for batch file processing using argparse.
This file defines the `preprocess_file` function and helper logic,
which will be called by `src/main_cli.py`.
It now includes an option to submit batch jobs to Celery.
"""

import logging
import json
import sys
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pathlib import Path
from pydantic import ValidationError
from datetime import date
import argparse

from src.core.processor import TextPreprocessor
from src.schemas.data_models import ArticleInput, PreprocessFileResult, PreprocessSingleResponse
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging
from src.storage.backends import StorageBackendFactory

# Import Celery task
from src.celery_app import preprocess_article_task

# Load settings and configure logging once on startup.
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Instantiate TextPreprocessor for use in processing
preprocessor = TextPreprocessor()

# Debug: Log initialization of this module.
logger.debug("src/main.py module loaded. Contains argparse CLI functions.")


def _process_single_article(article_data: Dict[str, Any]) -> Optional[PreprocessFileResult]:
    """
    Helper function to process a single article's data from the input file.
    This function includes the processing logic and error handling for one item.
    """
    try:
        # 1. Input Data Validation: Validate the input data against the ArticleInput schema.
        input_article = ArticleInput.model_validate(article_data)

        # Use the document_id from the validated input for traceability
        document_id = input_article.document_id

        # 2. Core Processing: Process the text and all relevant metadata using the core preprocessor.
        processed_data_dict = preprocessor.preprocess(
            text=input_article.text,
            document_id=input_article.document_id,
            title=input_article.title,
            excerpt=input_article.excerpt,
            author=input_article.author,
            publication_date=input_article.publication_date,
            revision_date=input_article.revision_date,
            source_url=input_article.source_url,
            categories=input_article.categories,
            tags=input_article.tags,
            media_asset_urls=input_article.media_asset_urls,
            geographical_data=input_article.geographical_data,
            embargo_date=input_article.embargo_date,
            sentiment=input_article.sentiment,
            word_count=input_article.word_count,
            publisher=input_article.publisher,
            additional_metadata=input_article.additional_metadata
        )

        # 3. Output Data Validation and return as dictionary
        response = PreprocessSingleResponse(
            version="1.0",
            **processed_data_dict
        )

        # 4. Persist to storage backends
        backends = StorageBackendFactory.get_backends()
        for backend in backends:
            backend.save(response)

        # 5. Construct the final result object with the unique ID.
        return PreprocessFileResult(
            document_id=document_id,
            version="1.0",  # Ensure version is set for PreprocessFileResult
            processed_data=response
        )

    except ValidationError as e:
        logger.error(f"Input data failed Pydantic validation. Skipping article. Error: {e.errors()}", extra={
                     "raw_input_sample": str(article_data)[:200]})
        return None
    except Exception as e:
        logger.error(f"Error processing text for document_id={article_data.get('document_id', 'N/A')}. Error: {e}", exc_info=True, extra={
                     "document_id": article_data.get('document_id', 'N/A')})
        return None


def preprocess_file(input_path: str, output_path: str, use_celery: bool = False):
    """
    Processes a file containing structured article objects (one per line) in parallel.
    Can optionally submit tasks to Celery for asynchronous processing.
    Saves results to storage backends in addition to the output file.
    """
    input_file_path = Path(input_path)
    output_file_path = Path(output_path)

    if not input_file_path.exists():
        print(
            f"Error: Input file not found at {input_file_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Starting batch preprocessing of file: {input_file_path}")
    logger.info(
        f"Starting CLI batch processing from file '{input_file_path}'.")

    with open(input_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if use_celery:
        print(
            f"Submitting {len(lines)} articles to Celery for asynchronous processing...")
        logger.info(f"Submitting {len(lines)} articles to Celery via CLI.")

        task_results = []
        for i, line in enumerate(lines):
            try:
                article_data = json.loads(line.strip())
                # Send the article data to Celery task
                task = preprocess_article_task.delay(json.dumps(article_data))
                task_results.append(task)
                logger.debug(f"Submitted article {i+1} as Celery task: {task.id}", extra={
                             "document_id": article_data.get('document_id', 'N/A'), "task_id": task.id})
            except json.JSONDecodeError as e:
                logger.error(
                    f"Skipping malformed JSON line in Celery submission: '{line.strip()[:100]}...'. Error: {e}")
                task_results.append(None)  # Append None for failed submissions

        print(f"All tasks submitted. You can monitor their status using Celery monitoring tools (e.g., Flower) or by querying the results backend.")
        print(
            f"Results will be written to {output_file_path} once all tasks are complete and retrieved.")
        logger.info(
            f"All Celery tasks submitted. Waiting for results to write to {output_file_path}.")

        output_lines = []
        for i, task in enumerate(tqdm(task_results, total=len(task_results), desc="Retrieving Celery Results")):
            if task:
                try:
                    # .get() blocks until the task is done and fetches the result
                    # Timeout after 1 hour
                    result_dict = task.get(timeout=3600)
                    # Check if task returned a successful result
                    if result_dict and not result_dict.get("error"):
                        # Convert dict result back to Pydantic model for consistency
                        processed_result = PreprocessFileResult(
                            document_id=result_dict.get("document_id", "N/A"),
                            processed_data=PreprocessSingleResponse.model_validate(
                                result_dict)
                        )
                        output_lines.append(processed_result.model_dump_json())
                        # Save to storage backends
                        backends = StorageBackendFactory.get_backends()
                        for backend in backends:
                            backend.save(processed_result.processed_data)
                    else:
                        logger.error(f"Celery task {task.id} returned an error or no valid result: {result_dict}", extra={
                                     "task_id": task.id})
                except Exception as e:
                    logger.error(f"Failed to retrieve result for Celery task {task.id}: {e}", exc_info=True, extra={
                                 "task_id": task.id})
            else:
                logger.warning(
                    f"Skipping a task that failed submission (line {i+1}).")

    else:  # Synchronous multi-threaded processing
        num_threads = settings.ingestion_service.batch_processing_threads
        print(
            f"Using {num_threads} threads for synchronous parallel processing...")

        output_lines = []
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for line in lines:
                try:
                    article_data = json.loads(line.strip())
                    futures.append(executor.submit(
                        _process_single_article, article_data))
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Skipping malformed JSON line due to decode error: '{line.strip()[:100]}...'. Error: {e}")

            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
                processed_result = future.result()
                if processed_result:
                    output_lines.append(processed_result.model_dump_json())

    # Write the processed outputs to the output file in JSONL format
    with open(output_file_path, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    print(f"Processing complete. Results written to: {output_file_path}")
    logger.info(
        f"CLI batch processing finished. Results saved to '{output_file_path}'.")

# src/main.py
