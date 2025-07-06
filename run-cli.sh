#!/bin/bash
set -e

# Activate the virtual environment
source /opt/venv/bin/activate

# Debug: Print Python version and PYTHONPATH
echo "Python version: $(python --version)"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Current directory: $(pwd)"
echo "Executing command: python -m src.main $@"

# Check if src.main is importable
if python -c "import src.main" 2>/dev/null; then
    echo "Module src.main is importable."
else
    echo "Error: Failed to import src.main. Check PYTHONPATH and module structure."
    exit 1
fi

# Try running the command with python -m src.main
if python -m src.main "$@" 2>/dev/null; then
    echo "Command executed successfully."
else
    echo "Failed to execute 'python -m src.main $@'. Falling back to 'typer run'."
    # Fallback to typer run
    typer run src.main "$@"
fi