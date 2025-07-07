"""
main.py

Main entry point for the CLI. Handles bulk file processing.
"""

import typer
import logging
import json
import sys
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pathlib import Path
from pydantic import ValidationError
from datetime import date
import uuid

from src.core.processor import preprocessor
from src.schemas.data_models import ArticleInput, PreprocessFileResult, PreprocessSingleResponse
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging

# Initialize Typer CLI app
app = typer.Typer(
    name="ingestion-cli",
    help="CLI for the Data Ingestion & Preprocessing Microservice."
)

# Load settings and configure logging once on startup
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Debug: Log Typer initialization and command-line arguments
logger.debug(f"Typer app initialized with name: {app.info.name}")
logger.debug(f"Command-line arguments: {sys.argv}")

# Debug: Log registered commands
registered_commands = [cmd.name for cmd in app.registered_commands]
logger.debug(f"Registered Typer commands: {registered_commands}")


def _process_single_article(article_data: Dict[str, Any]) -> Optional[PreprocessFileResult]:
    """
    Helper function to process a single article's data from the input file.
    This function includes the processing logic and error handling for one item.
    """
    try:
        # 1. Input Data Validation: Validate the input data against the ArticleInput schema.
        # This is a crucial step for robustness and preventing bad data from entering the pipeline.
        input_article = ArticleInput.model_validate(article_data)

        # Use the document_id from the validated input for all logging
        document_id = input_article.document_id
        logger_extra = {"document_id": document_id}

        # 2. Core Processing: Process the text and all relevant metadata using the core preprocessor.
        processed_data_dict = preprocessor.preprocess(
            text=input_article.text,
            title=input_article.title,
            excerpt=input_article.excerpt,
            author=input_article.author,
            reference_date=input_article.publication_date
        )

        # 3. Output Data Validation: Validate the output data against the response schema.
        processed_data_response = PreprocessSingleResponse(
            document_id=document_id,
            **processed_data_dict
        )

        # 4. Construct the final result object with the unique ID.
        return PreprocessFileResult(
            document_id=document_id,
            original_text=input_article.text,
            processed_data=processed_data_response
        )

    except ValidationError as e:
        # Log validation errors and return None to skip this line.
        # This ensures the CLI is resilient to malformed input data.
        logger.error(f"Input data failed Pydantic validation. Skipping article. Error: {e.errors()}", extra={
                     "raw_input_sample": str(article_data)[:200]})
        return None
    except Exception as e:
        # Log any other unexpected processing errors for a specific article.
        logger.error(f"Error processing text for document_id={article_data.get('document_id', 'N/A')}. Error: {e}", exc_info=True, extra={
                     "document_id": article_data.get('document_id', 'N/A')})
        return None


@app.command("preprocess-file")
def preprocess_file(
    input_path: Path = typer.Option(..., "--input-path", "-i",
                                    help="Path to the input file (JSONL format, one JSON object per line)."),
    output_path: Path = typer.Option(..., "--output-path",
                                     "-o", help="Path to the output file (JSONL format).")
):
    """
    Processes a file containing structured article objects (one per line) in parallel.
    Each JSON object is expected to conform to the ArticleInput schema.
    """
    if not input_path.exists():
        typer.echo(f"Error: Input file not found at {input_path}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Starting batch preprocessing of file: {input_path}")
    logger.info(f"Starting CLI batch processing from file '{input_path}'.")

    # Read all lines from the input file
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    num_threads = settings.ingestion_service.batch_processing_threads
    typer.echo(f"Using {num_threads} threads for parallel processing...")

    output_lines = []

    # Use ThreadPoolExecutor for multi-threading
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit tasks to the executor
        futures = []
        for line in lines:
            try:
                # Attempt to parse each line as a JSON object before submitting to the pool
                article_data = json.loads(line.strip())
                futures.append(executor.submit(
                    _process_single_article, article_data))
            except json.JSONDecodeError as e:
                # Log a clear error for malformed JSON lines and skip them.
                logger.error(
                    f"Skipping malformed JSON line due to decode error: '{line.strip()[:100]}...'. Error: {e}")

        # Iterate over completed futures to get results and write them
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            processed_result = future.result()

            # If processing was successful, format the output and add it to the list
            if processed_result:
                # Convert the Pydantic model to a JSON string
                output_lines.append(processed_result.model_dump_json())

    # Write the processed outputs to the output file in JSONL format
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    typer.echo(
        f"Processing complete. Processed {len(output_lines)} out of {len(lines)} lines successfully. Results written to: {output_path}")
    logger.info(
        f"CLI batch processing finished. Results saved to '{output_path}'.")


if __name__ == "__main__":
    # Ensure the spaCy model is loaded for the CLI to work.
    preprocessor
    # Debug: Log before running Typer app
    logger.debug("Running Typer app...")
    app()