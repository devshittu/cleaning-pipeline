"""
main.py

Contains the core CLI logic for batch file processing using argparse.
This file defines the `preprocess_file` function and helper logic,
which will be called by `src/main_cli.py`.
It now includes an option to submit batch jobs to Celery.

ENHANCED:
- Resilient error handling - continues on validation errors
- Comprehensive error reporting at end
- Statistics on success/failure rates
- Detailed error summary with line numbers
"""

import logging
import json
import sys
from typing import Optional, List, Dict, Any, Tuple
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
from src.utils.json_sanitizer import sanitize_and_parse_json  # NEW

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


class ProcessingError:
    """Container for processing error details."""

    def __init__(self, line_number: int, document_id: str, error_type: str, error_message: str, raw_data_sample: str = ""):
        self.line_number = line_number
        self.document_id = document_id
        self.error_type = error_type
        self.error_message = error_message
        self.raw_data_sample = raw_data_sample

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "document_id": self.document_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "raw_data_sample": self.raw_data_sample
        }


class ProcessingStats:
    """Statistics tracker for batch processing."""

    def __init__(self):
        self.total_lines = 0
        self.empty_lines = 0
        self.success_count = 0
        self.json_decode_errors = 0
        self.validation_errors = 0
        self.processing_errors = 0
        self.errors: List[ProcessingError] = []

    def add_error(self, error: ProcessingError):
        self.errors.append(error)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "empty_lines": self.empty_lines,
            "processed_successfully": self.success_count,
            "json_decode_errors": self.json_decode_errors,
            "validation_errors": self.validation_errors,
            "processing_errors": self.processing_errors,
            "total_errors": len(self.errors),
            "success_rate": f"{(self.success_count / max(1, self.total_lines - self.empty_lines)) * 100:.1f}%"
        }


def _sanitize_url(url: str) -> Optional[str]:
    """
    Attempt to fix common URL issues.

    Args:
        url: Potentially malformed URL

    Returns:
        Sanitized URL or None if unfixable
    """
    if not url or not isinstance(url, str):
        return None

    # Fix common typos
    url = url.strip()

    # Fix double dots in scheme (https.://)
    url = url.replace('https.://', 'https://')
    url = url.replace('http.://', 'http://')

    # Fix double s in scheme (httpss://)
    url = url.replace('httpss://', 'https://')
    url = url.replace('httpps://', 'https://')

    # Ensure scheme is present
    if not url.startswith(('http://', 'https://')):
        # Try to add https:// if it looks like a domain
        if '.' in url and not url.startswith('//'):
            url = 'https://' + url

    return url if url.startswith(('http://', 'https://')) else None


def _process_single_article(
    article_data: Dict[str, Any],
    custom_cleaning_config: Optional[Dict[str, Any]] = None,
    line_number: int = 0,
    stats: Optional[ProcessingStats] = None
) -> Optional[PreprocessFileResult]:
    """
    Helper function to process a single article's data from the input file.
    This function includes the processing logic and error handling for one item.

    Args:
        article_data: Raw article data dictionary
        custom_cleaning_config: Optional custom cleaning configuration
        line_number: Line number in input file (for error reporting)
        stats: Statistics tracker

    Returns:
        PreprocessFileResult or None if processing fails
    """
    document_id = article_data.get('document_id', f'line-{line_number}')

    try:
        # 1. Sanitize URLs before validation
        if 'source_url' in article_data and article_data['source_url']:
            sanitized_url = _sanitize_url(article_data['source_url'])
            if sanitized_url:
                article_data['source_url'] = sanitized_url
                logger.debug(f"Sanitized source_url for {document_id}")
            else:
                logger.warning(
                    f"Could not sanitize source_url for {document_id}, removing field")
                article_data.pop('source_url', None)

        # Sanitize media URLs
        if 'media_asset_urls' in article_data and article_data['media_asset_urls']:
            sanitized_media = []
            for url in article_data['media_asset_urls']:
                sanitized = _sanitize_url(url)
                if sanitized:
                    sanitized_media.append(sanitized)
            article_data['media_asset_urls'] = sanitized_media if sanitized_media else None

        # 2. Input Data Validation: Validate the input data against the ArticleInput schema.
        input_article = ArticleInput.model_validate(article_data)

        # Use the document_id from the validated input for traceability
        document_id = input_article.document_id

        # 3. Core Processing: Process the text and all relevant metadata using the core preprocessor.
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
            additional_metadata=input_article.additional_metadata,
            custom_cleaning_config=custom_cleaning_config
        )

        # 4. Output Data Validation and return as dictionary
        response = PreprocessSingleResponse(
            version="1.0",
            **processed_data_dict
        )

        # 5. Persist to storage backends
        backends = StorageBackendFactory.get_backends()
        for backend in backends:
            backend.save(response)

        # 6. Update stats
        if stats:
            stats.success_count += 1

        # 7. Construct the final result object with the unique ID.
        return PreprocessFileResult(
            document_id=document_id,
            version="1.0",
            processed_data=response
        )

    except ValidationError as e:
        if stats:
            stats.validation_errors += 1
            error = ProcessingError(
                line_number=line_number,
                document_id=document_id,
                error_type="ValidationError",
                error_message=str(e.errors()[:3]),  # First 3 errors only
                raw_data_sample=str(article_data)[:200]
            )
            stats.add_error(error)

        logger.warning(
            f"Line {line_number}: Validation error for document_id={document_id}. Skipping. "
            f"Errors: {e.errors()[:2]}"  # Log first 2 errors
        )
        return None

    except Exception as e:
        if stats:
            stats.processing_errors += 1
            error = ProcessingError(
                line_number=line_number,
                document_id=document_id,
                error_type=type(e).__name__,
                error_message=str(e)[:200],
                raw_data_sample=str(article_data)[:200]
            )
            stats.add_error(error)

        logger.error(
            f"Line {line_number}: Processing error for document_id={document_id}. Skipping. "
            f"Error: {str(e)[:100]}"
        )
        return None


def preprocess_file(
    input_path: str,
    output_path: str,
    use_celery: bool = False,
    custom_cleaning_config: Optional[Dict[str, Any]] = None
) -> ProcessingStats:
    """
    Processes a file containing structured article objects (one per line) in parallel.
    Can optionally submit tasks to Celery for asynchronous processing.
    Saves results to storage backends in addition to the output file.

    Args:
        input_path: Path to input JSONL file
        output_path: Path to output JSONL file
        use_celery: If True, submit to Celery workers; if False, process locally
        custom_cleaning_config: Optional custom cleaning configuration dict

    Returns:
        ProcessingStats with detailed results
    """
    input_file_path = Path(input_path)
    output_file_path = Path(output_path)

    if not input_file_path.exists():
        print(
            f"Error: Input file not found at {input_file_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize statistics tracker
    stats = ProcessingStats()

    print(f"Starting batch preprocessing of file: {input_file_path}")
    logger.info(
        f"Starting CLI batch processing from file '{input_file_path}'.")

    with open(input_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    stats.total_lines = len(lines)

    if use_celery:
        print(
            f"Submitting {len(lines)} articles to Celery for asynchronous processing...")
        logger.info(f"Submitting {len(lines)} articles to Celery via CLI.")

        task_results = []
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                stats.empty_lines += 1
                continue

            # Use sophisticated JSON sanitizer
            article_data, parse_error = sanitize_and_parse_json(line, i)

            if article_data is None:
                # JSON parsing failed
                stats.json_decode_errors += 1
                error = ProcessingError(
                    line_number=i,
                    document_id=f"line-{i}",
                    error_type="JSONDecodeError",
                    error_message=parse_error or "Could not parse JSON",
                    raw_data_sample=line[:200]
                )
                stats.add_error(error)
                logger.warning(f"Line {i}: {parse_error}")
                continue

            # Sanitize URLs before sending to Celery
            if 'source_url' in article_data:
                article_data['source_url'] = _sanitize_url(
                    article_data['source_url'])
            if 'media_asset_urls' in article_data:
                article_data['media_asset_urls'] = [
                    url for url in [_sanitize_url(u) for u in article_data['media_asset_urls']]
                    if url
                ] or None

            # Send the article data to Celery task
            task = preprocess_article_task.delay(
                json.dumps(article_data),
                json.dumps(
                    custom_cleaning_config) if custom_cleaning_config else None
            )
            task_results.append(
                (i, task, article_data.get('document_id', f'line-{i}')))

        print(f"\nAll tasks submitted. Waiting for results...")
        logger.info(f"All Celery tasks submitted. Retrieving results...")

        output_lines = []
        for i, task, doc_id in tqdm(task_results, desc="Retrieving Celery Results"):
            if task:
                try:
                    result_dict = task.get(timeout=3600)
                    if result_dict and not result_dict.get("error"):
                        processed_result = PreprocessFileResult(
                            document_id=result_dict.get("document_id", doc_id),
                            version="1.0",
                            processed_data=PreprocessSingleResponse.model_validate(
                                result_dict)
                        )
                        output_lines.append(processed_result.model_dump_json())
                        stats.success_count += 1

                        # Save to storage backends
                        backends = StorageBackendFactory.get_backends()
                        for backend in backends:
                            backend.save(processed_result.processed_data)
                    else:
                        stats.processing_errors += 1
                        error = ProcessingError(
                            line_number=i,
                            document_id=doc_id,
                            error_type="CeleryTaskError",
                            error_message=str(result_dict.get(
                                "error", "Unknown error"))[:200],
                            raw_data_sample=""
                        )
                        stats.add_error(error)
                        logger.error(
                            f"Celery task failed for line {i}, document_id={doc_id}")

                except Exception as e:
                    stats.processing_errors += 1
                    error = ProcessingError(
                        line_number=i,
                        document_id=doc_id,
                        error_type="CeleryRetrievalError",
                        error_message=str(e)[:200],
                        raw_data_sample=""
                    )
                    stats.add_error(error)
                    logger.error(
                        f"Failed to retrieve result for line {i}: {e}")

    else:  # Synchronous multi-threaded processing
        num_threads = settings.ingestion_service.batch_processing_threads
        print(
            f"Using {num_threads} threads for synchronous parallel processing...")

        output_lines = []
        futures_map = {}  # Map future to line number

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    stats.empty_lines += 1
                    continue

                # Use sophisticated JSON sanitizer
                article_data, parse_error = sanitize_and_parse_json(line, i)

                if article_data is None:
                    # JSON parsing failed even after all sanitization attempts
                    stats.json_decode_errors += 1
                    error = ProcessingError(
                        line_number=i,
                        document_id=f"line-{i}",
                        error_type="JSONDecodeError",
                        error_message=parse_error or "Could not parse JSON",
                        raw_data_sample=line[:200]
                    )
                    stats.add_error(error)
                    logger.warning(f"Line {i}: {parse_error}")
                    continue

                # Successfully parsed, submit for processing
                future = executor.submit(
                    _process_single_article,
                    article_data,
                    custom_cleaning_config,
                    i,  # Pass line number
                    stats  # Pass stats tracker
                )
                futures_map[future] = i

            for future in tqdm(as_completed(futures_map), total=len(futures_map), desc="Processing"):
                processed_result = future.result()
                if processed_result:
                    output_lines.append(processed_result.model_dump_json())

    # Write the processed outputs to the output file in JSONL format
    with open(output_file_path, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    # Print summary
    _print_processing_summary(stats, output_file_path)

    logger.info(
        f"CLI batch processing finished. Results saved to '{output_file_path}'.")
    return stats


def _print_processing_summary(stats: ProcessingStats, output_path: Path):
    """Print detailed processing summary."""
    print("\n" + "="*70)
    print("PROCESSING SUMMARY")
    print("="*70)

    summary = stats.get_summary()
    print(f"Total lines in file:       {summary['total_lines']}")
    print(f"Empty lines skipped:       {summary['empty_lines']}")
    print(f"Successfully processed:    {summary['processed_successfully']}")
    print(f"JSON decode errors:        {summary['json_decode_errors']}")
    print(f"Validation errors:         {summary['validation_errors']}")
    print(f"Processing errors:         {summary['processing_errors']}")
    print(f"Total errors:              {summary['total_errors']}")
    print(f"Success rate:              {summary['success_rate']}")
    print(f"\nResults written to: {output_path}")

    if stats.errors:
        print("\n" + "-"*70)
        print("ERROR DETAILS (first 10)")
        print("-"*70)

        for i, error in enumerate(stats.errors[:10], 1):
            print(f"\n{i}. Line {error.line_number} - {error.error_type}")
            print(f"   Document ID: {error.document_id}")
            print(f"   Error: {error.error_message[:150]}")
            if error.raw_data_sample:
                print(f"   Sample: {error.raw_data_sample[:100]}...")

        if len(stats.errors) > 10:
            print(f"\n... and {len(stats.errors) - 10} more errors")
            print(
                f"\nTo see all errors, check the log file: logs/ingestion_service.jsonl")

        # Save detailed error report
        error_report_path = output_path.parent / \
            f"{output_path.stem}_errors.json"
        with open(error_report_path, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": summary,
                "errors": [e.to_dict() for e in stats.errors]
            }, f, indent=2)
        print(f"\nDetailed error report saved to: {error_report_path}")

    print("="*70 + "\n")

# src/main.py
