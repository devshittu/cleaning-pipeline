#!/bin/bash
set -e

# Activate the virtual environment
source /opt/venv/bin/activate

# Debug: Print Python version and PYTHONPATH
echo "Python version: $(python --version)"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Current directory: $(pwd)"

# Execute the dedicated CLI entrypoint module using `python -m`.
# This is the standard and most robust way to run a Typer CLI application.
# It ensures `sys.argv` is correctly structured for Typer's parsing.
# The `"$@"` passes all arguments from the shell script directly to the Python module.
echo "Executing command: python -m src.main_cli $@"
python -m src.main_cli "$@"

# No need for complex fallback logic; if the above fails, set -e will exit.
