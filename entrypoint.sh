#!/bin/bash
set -e

# Activate the virtual environment
source /opt/venv/bin/activate

# Create log and cache directories if they don't exist
mkdir -p /app/logs /app/.cache/spacy

# Load configuration and ensure logging is set up
# This ensures config and logging are ready before the main application starts
python -c "from src.utils.logger import setup_logging; setup_logging(); from src.utils.config_manager import ConfigManager; ConfigManager.get_settings()"

# Get model name from config
MODEL_NAME=$(python -c "from src.utils.config_manager import ConfigManager; print(ConfigManager.get_settings().ingestion_service.model_name)")

echo "Checking for spaCy model: ${MODEL_NAME}"

# Check if the spaCy model is loadable
if python -c "import spacy; spacy.load('${MODEL_NAME}')" 2>/dev/null; then
    echo "spaCy model ${MODEL_NAME} found and loadable."
else
    echo "Error: spaCy model ${MODEL_NAME} not found or not loadable. Ensure it was pre-installed in the Docker image."
    exit 1
fi

echo "Starting Ingestion Service..."

# Execute the main command passed to the script (e.g., `uvicorn ...`)
exec "$@"
# entrypoint.sh