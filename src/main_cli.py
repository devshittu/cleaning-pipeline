"""
src/main_cli.py

This is the dedicated entrypoint script for the CLI application using Click.
It provides intuitive commands for preprocessing news articles.

FIXES APPLIED:
- Fix #12: Migrated from argparse to Click for better UX
- Added rich output formatting and progress indicators
- Improved error handling and user feedback
"""

import sys
import os
import logging
import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import print as rprint

from src.main import preprocess_file
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging
from src.core.processor import TextPreprocessor

# Add src to the Python path if it's not already there.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

src_dir = os.path.abspath(os.path.dirname(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Set up logging early in the entrypoint script
settings = ConfigManager.get_settings()
setup_logging()
logger = logging.getLogger("ingestion_service")

# Rich console for beautiful output
console = Console()

# Instantiate TextPreprocessor to ensure spaCy model is loaded
try:
    preprocessor = TextPreprocessor()
    logger.info("TextPreprocessor initialized for CLI, spaCy model loaded.")
except Exception as e:
    console.print(
        f"[bold red]Error:[/bold red] Failed to initialize TextPreprocessor: {e}")
    sys.exit(1)


@click.group()
@click.version_option(version="1.0.0", prog_name="ingestion-cli")
def cli():
    """
    🧹 Data Ingestion & Preprocessing CLI
    
    A command-line interface for cleaning and preprocessing news articles.
    Supports batch processing, Celery integration, and multiple storage backends.
    """
    pass


@cli.command(name="process")
@click.option(
    '-i', '--input',
    'input_path',
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help='Path to input JSONL file (one article per line)'
)
@click.option(
    '-o', '--output',
    'output_path',
    type=click.Path(dir_okay=False, writable=True),
    required=True,
    help='Path to output JSONL file'
)
@click.option(
    '--celery/--no-celery',
    default=False,
    help='Submit tasks to Celery workers (async) or process locally (sync)'
)
@click.option(
    '--backends',
    type=str,
    default=None,
    help='Comma-separated list of storage backends (e.g., "jsonl,postgresql,elasticsearch")'
)
def process_command(input_path: str, output_path: str, celery: bool, backends: str):
    """
    Process a JSONL file containing news articles.
    
    \b
    Examples:
        # Process locally (synchronous)
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl
        
        # Process with Celery (asynchronous)
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl --celery
        
        # Specify storage backends
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl --backends jsonl,postgresql
    """
    console.print(
        "\n[bold cyan]🚀 Starting Article Processing Pipeline[/bold cyan]\n")

    # Display configuration
    config_table = Table(title="Configuration",
                         show_header=True, header_style="bold magenta")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")

    config_table.add_row("Input File", input_path)
    config_table.add_row("Output File", output_path)
    config_table.add_row(
        "Processing Mode", "Celery (Async)" if celery else "Local (Sync)")
    config_table.add_row("Storage Backends",
                         backends if backends else "Default (from config)")
    config_table.add_row("SpaCy Model", settings.ingestion_service.model_name)
    config_table.add_row(
        "GPU Enabled", "Yes" if settings.general.gpu_enabled else "No")

    console.print(config_table)
    console.print()

    try:
        # Count total lines for progress tracking
        with open(input_path, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for line in f if line.strip())

        console.print(
            f"[bold]Found {total_lines} articles to process[/bold]\n")

        # Call the processing function
        with console.status("[bold green]Processing articles...") as status:
            preprocess_file(
                input_path=input_path,
                output_path=output_path,
                use_celery=celery
            )

        console.print(f"\n[bold green]✅ Processing complete![/bold green]")
        console.print(f"[cyan]Results saved to:[/cyan] {output_path}\n")

    except FileNotFoundError as e:
        console.print(
            f"[bold red]❌ Error:[/bold red] Input file not found: {input_path}")
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="validate")
@click.argument('input_path', type=click.Path(exists=True, dir_okay=False, readable=True))
def validate_command(input_path: str):
    """
    Validate a JSONL file for correct format and schema.
    
    \b
    Example:
        ingestion-cli validate data/input.jsonl
    """
    console.print(
        f"\n[bold cyan]🔍 Validating file:[/bold cyan] {input_path}\n")

    from src.schemas.data_models import ArticleInput
    import json
    from pydantic import ValidationError

    valid_count = 0
    error_count = 0
    errors = []

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Validating...", total=len(lines))

            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    progress.advance(task)
                    continue

                try:
                    article_data = json.loads(line)
                    ArticleInput.model_validate(article_data)
                    valid_count += 1
                except json.JSONDecodeError as e:
                    error_count += 1
                    errors.append(f"Line {i}: Invalid JSON - {str(e)}")
                except ValidationError as e:
                    error_count += 1
                    errors.append(
                        f"Line {i}: Schema validation failed - {e.error_count()} errors")

                progress.advance(task)

        # Display results
        console.print()
        results_table = Table(title="Validation Results",
                              show_header=True, header_style="bold magenta")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Count", style="green")

        results_table.add_row("Total Lines", str(len(lines)))
        results_table.add_row("Valid Articles", str(valid_count))
        results_table.add_row("Errors", str(error_count))

        console.print(results_table)

        if error_count > 0:
            console.print(
                f"\n[bold yellow]⚠️  Found {error_count} errors[/bold yellow]")
            if len(errors) <= 10:
                console.print("\n[bold]Error Details:[/bold]")
                for error in errors:
                    console.print(f"  [red]•[/red] {error}")
            else:
                console.print(f"\n[bold]First 10 errors:[/bold]")
                for error in errors[:10]:
                    console.print(f"  [red]•[/red] {error}")
                console.print(
                    f"\n  [dim]... and {len(errors) - 10} more errors[/dim]")
        else:
            console.print(
                f"\n[bold green]✅ All articles are valid![/bold green]\n")

        sys.exit(0 if error_count == 0 else 1)

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="info")
def info_command():
    """
    Display system and configuration information.
    """
    console.print("\n[bold cyan]ℹ️  System Information[/bold cyan]\n")

    info_table = Table(show_header=True, header_style="bold magenta")
    info_table.add_column("Component", style="cyan")
    info_table.add_column("Details", style="green")

    # System info
    info_table.add_row("CLI Version", "1.0.0")
    info_table.add_row("Python Version", f"{sys.version.split()[0]}")

    # Configuration
    info_table.add_row("Log Level", settings.general.log_level)
    info_table.add_row(
        "GPU Enabled", "Yes" if settings.general.gpu_enabled else "No")
    info_table.add_row("SpaCy Model", settings.ingestion_service.model_name)
    info_table.add_row("Model Cache Dir",
                       settings.ingestion_service.model_cache_dir)

    # Celery
    info_table.add_row("Celery Broker", settings.celery.broker_url)
    info_table.add_row("Worker Concurrency", str(
        settings.celery.worker_concurrency))

    # Storage
    enabled_backends = settings.storage.enabled_backends
    info_table.add_row("Storage Backends", ", ".join(
        enabled_backends) if enabled_backends else "None")

    console.print(info_table)
    console.print()


@cli.command(name="test-model")
@click.option(
    '--text',
    type=str,
    default="This is a test article about artificial intelligence and machine learning.",
    help='Test text to process'
)
def test_model_command(text: str):
    """
    Test the spaCy model with sample text.
    
    \b
    Example:
        ingestion-cli test-model --text "Your sample text here"
    """
    console.print("\n[bold cyan]🧪 Testing SpaCy Model[/bold cyan]\n")

    try:
        with console.status("[bold green]Processing text..."):
            cleaned_text = preprocessor.clean_text(text)
            entities = preprocessor.tag_entities(cleaned_text)

        console.print(f"[bold]Original Text:[/bold]\n{text}\n")
        console.print(f"[bold]Cleaned Text:[/bold]\n{cleaned_text}\n")

        if entities:
            console.print(
                f"[bold green]Found {len(entities)} entities:[/bold green]\n")

            entity_table = Table(show_header=True, header_style="bold magenta")
            entity_table.add_column("Entity", style="cyan")
            entity_table.add_column("Type", style="green")
            entity_table.add_column("Position", style="yellow")

            for entity in entities:
                entity_table.add_row(
                    entity.text,
                    entity.type,
                    f"{entity.start_char}-{entity.end_char}"
                )

            console.print(entity_table)
        else:
            console.print("[yellow]No entities found[/yellow]")

        console.print(f"\n[bold green]✅ Model test complete![/bold green]\n")

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        logger.error(f"Model test failed: {e}", exc_info=True)
        sys.exit(1)


def main():
    """
    Main function to run the CLI application.
    """
    try:
        cli()
    except Exception as e:
        console.print(f"[bold red]❌ Unexpected error:[/bold red] {str(e)}")
        logger.critical(f"CLI crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

# src/main_cli.py
