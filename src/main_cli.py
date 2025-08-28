"""
src/main_cli.py

This is the dedicated entrypoint script for the CLI application using argparse.
It parses command-line arguments and calls the appropriate function from src.main.
"""

import sys
import os
import logging
import argparse
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

# Instantiate TextPreprocessor to ensure spaCy model is loaded
preprocessor = TextPreprocessor()


def main():
    """
    Main function to parse arguments and dispatch to CLI commands.
    """
    logger.info("TextPreprocessor initialized for CLI, spaCy model loaded.")

    parser = argparse.ArgumentParser(
        description="CLI for the Data Ingestion & Preprocessing Microservice."
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands")

    # 'preprocess-file' command parser
    preprocess_parser = subparsers.add_parser(
        "preprocess-file", help="Processes a file containing structured article objects in parallel."
    )
    preprocess_parser.add_argument(
        "--input-path", "-i", type=str, required=True,
        help="Path to the input file (JSONL format, one JSON object per line)."
    )
    preprocess_parser.add_argument(
        "--output-path", "-o", type=str, required=True,
        help="Path to the output file (JSONL format)."
    )
    preprocess_parser.add_argument(
        "--use-celery", action="store_true",
        help="Submit batch processing tasks to Celery for asynchronous execution."
    )

    args = parser.parse_args()

    if args.command == "preprocess-file":
        logger.debug(f"Executing preprocess-file command with args: {args}")
        preprocess_file(input_path=args.input_path,
                        output_path=args.output_path, use_celery=args.use_celery)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

# src/main_cli.py


# """
# src/main_cli.py

# This is the dedicated entrypoint script for the CLI application using argparse.
# It parses command-line arguments and calls the appropriate function from src.main.
# """

# import sys
# import os
# import logging
# import argparse
# from src.main import preprocess_file
# from src.utils.config_manager import ConfigManager
# from src.utils.logger import setup_logging
# from src.core.processor import preprocessor

# # Add src to the Python path if it's not already there.
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# if project_root not in sys.path:
#     sys.path.insert(0, project_root)

# src_dir = os.path.abspath(os.path.dirname(__file__))
# if src_dir not in sys.path:
#     sys.path.insert(0, src_dir)

# # Set up logging early in the entrypoint script
# settings = ConfigManager.get_settings()
# setup_logging()
# logger = logging.getLogger("ingestion_service")


# def main():
#     """
#     Main function to parse arguments and dispatch to CLI commands.
#     """
#     # Ensure the spaCy model is loaded for the CLI to work.
#     # This also triggers the singleton initialization of TextPreprocessor.
#     _ = preprocessor.nlp
#     logger.info("SpaCy model initialized for CLI.")

#     parser = argparse.ArgumentParser(
#         description="CLI for the Data Ingestion & Preprocessing Microservice."
#     )

#     subparsers = parser.add_subparsers(
#         dest="command", help="Available commands")

#     # 'preprocess-file' command parser
#     preprocess_parser = subparsers.add_parser(
#         "preprocess-file", help="Processes a file containing structured article objects in parallel."
#     )
#     preprocess_parser.add_argument(
#         "--input-path", "-i", type=str, required=True,
#         help="Path to the input file (JSONL format, one JSON object per line)."
#     )
#     preprocess_parser.add_argument(
#         "--output-path", "-o", type=str, required=True,
#         help="Path to the output file (JSONL format)."
#     )
#     preprocess_parser.add_argument(
#         "--use-celery", action="store_true",
#         help="Submit batch processing tasks to Celery for asynchronous execution."
#     )

#     args = parser.parse_args()

#     if args.command == "preprocess-file":
#         logger.debug(f"Executing preprocess-file command with args: {args}")
#         preprocess_file(input_path=args.input_path,
#                         output_path=args.output_path, use_celery=args.use_celery)
#     else:
#         parser.print_help()
#         sys.exit(1)


# if __name__ == "__main__":
#     main()

# src/main_cli.py
