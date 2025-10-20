# Data Ingestion & Preprocessing CLI

**Version:** 1.0.0

A command-line interface for cleaning and preprocessing news articles with NLP enrichment.

**Contact:** support@example.com

---

## Commands

### `docs`

📚 Documentation commands for CLI reference and export.

**Usage:** `ingestion-cli docs [OPTIONS]`

---

### `process`


    Process a JSONL file containing news articles.
    
    
    Examples:
        # Process locally (synchronous)
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl
        
        # Process with Celery (asynchronous)
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl --celery
        
        # Disable typo correction
        ingestion-cli process -i data/input.jsonl -o data/output.jsonl --disable-typo-correction
    

**Usage:** `ingestion-cli process [OPTIONS]`

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `-i, --input` | file | True | None | Path to input JSONL file (one article per line) |
| `-o, --output` | file | True | None | Path to output JSONL file |
| `--celery` | boolean | False | False | Submit tasks to Celery workers (async) or process locally (sync) |
| `--backends` | text | False | None | Comma-separated list of storage backends (e.g., "jsonl,postgresql,elasticsearch") |
| `--disable-typo-correction` | boolean | False | False | Disable typo correction for this batch |
| `--disable-html-removal` | boolean | False | False | Disable HTML tag removal |
| `--disable-currency-standardization` | boolean | False | False | Disable currency standardization ($100 → USD 100) |

**Examples:**

- Process file locally (synchronous)
  ```bash
  ingestion-cli process -i input.jsonl -o output.jsonl
  ```

- Process with Celery (asynchronous)
  ```bash
  ingestion-cli process -i input.jsonl -o output.jsonl --celery
  ```

- Disable typo correction
  ```bash
  ingestion-cli process -i input.jsonl -o output.jsonl --disable-typo-correction
  ```

---

### `validate`


    Validate a JSONL file for correct format and schema.
    
    
    Example:
        ingestion-cli validate data/input.jsonl
    

**Usage:** `ingestion-cli validate [OPTIONS]`

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `input_path` | file | True | None | No description |

**Examples:**

- Validate JSONL file
  ```bash
  ingestion-cli validate input.jsonl
  ```

---

### `info`


    Display system and configuration information.
    

**Usage:** `ingestion-cli info [OPTIONS]`

---

### `test-model`


    Test the spaCy model with sample text using NER-protected cleaning.
    
    
    Example:
        ingestion-cli test-model --text "Apple Inc. in San Francisco"
        ingestion-cli test-model --text "Your text" --disable-typo-correction
    

**Usage:** `ingestion-cli test-model [OPTIONS]`

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--text` | text | False | This is a test article about artificial intelligence and machine learning. | Test text to process |
| `--disable-typo-correction` | boolean | False | False | Disable typo correction for this test |

**Examples:**

- Test with default text
  ```bash
  ingestion-cli test-model
  ```

- Test with custom text
  ```bash
  ingestion-cli test-model --text "Apple Inc. in San Francisco"
  ```

---

