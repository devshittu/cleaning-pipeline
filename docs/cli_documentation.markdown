# CLI Usage Guide

## Overview

The Data Ingestion & Preprocessing CLI provides a command-line interface for cleaning and preprocessing news articles. It supports batch processing, Celery integration, and multiple storage backends.

---

## Installation & Setup

### Docker Environment (Recommended)

The CLI is pre-installed in the Docker container. No additional setup required.

### Non-Docker Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_trf

# Run CLI directly
python -m src.main_cli --help
```

---

## CLI Commands Reference

### 1. `info` - System Information

Display configuration and system information.

#### Docker Usage

```bash
docker compose exec ingestion-service python -m src.main_cli info
```

#### Non-Docker Usage

```bash
python -m src.main_cli info
```

#### Output

```
ℹ️  System Information

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component          ┃ Details                            ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ CLI Version        │ 1.0.0                              │
│ Python Version     │ 3.11.9                             │
│ Log Level          │ INFO                               │
│ GPU Enabled        │ Yes                                │
│ SpaCy Model        │ en_core_web_trf                    │
│ Model Cache Dir    │ /app/.cache/spacy                  │
│ Typo Correction    │ Enabled                            │
│ NER Protection     │ Enabled                            │
│ HTML Removal       │ Enabled                            │
│ Currency Std       │ Enabled                            │
│ Celery Broker      │ redis://redis:6379/0               │
│ Worker Concurrency │ 4                                  │
│ Storage Backends   │ jsonl                              │
└────────────────────┴────────────────────────────────────┘
```

---

### 2. `test-model` - Test SpaCy Model

Test the NER model with sample text to verify installation and cleaning pipeline.

#### Docker Usage

```bash
# Basic test with default text
docker compose exec ingestion-service python -m src.main_cli test-model

# Test with custom text
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Apple Inc. announced new products in San Francisco yesterday."

# Test without typo correction
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Ths is a test with typos in New York." \
  --disable-typo-correction
```

#### Non-Docker Usage

```bash
python -m src.main_cli test-model \
  --text "Microsoft released updates in Seattle last week."
```

#### Output

```
🧪 Testing SpaCy Model

Original Text:
Apple Inc. announced new products in San Francisco yesterday.

Cleaned Text:
Apple Inc. announced new products in San Francisco yesterday.

Found 3 entities:

┏━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┓
┃ Entity        ┃ Type ┃ Position ┃
┡━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━┩
│ Apple Inc.    │ ORG  │ 0-10     │
│ San Francisco │ GPE  │ 37-50    │
│ yesterday     │ DATE │ 51-60    │
└───────────────┴──────┴──────────┘

✅ Model test complete!
```

---

### 3. `validate` - Validate JSONL Files

Validate input files for correct format and schema compliance.

#### Docker Usage

```bash
# Validate file in mounted volume
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/input.jsonl

# Validate with detailed error reporting
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/invalid_test.jsonl
```

#### Non-Docker Usage

```bash
python -m src.main_cli validate ./data/input.jsonl
```

#### Output (Valid File)

```
🔍 Validating file: /app/data/input.jsonl

Validating... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Validation Results
┏━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric       ┃ Count ┃
┡━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Lines  │ 150   │
│ Valid        │ 150   │
│ Errors       │ 0     │
└──────────────┴───────┘

✅ All articles are valid!
```

#### Output (Invalid File)

```
🔍 Validating file: /app/data/invalid_test.jsonl

Validation Results
┏━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric       ┃ Count ┃
┡━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Lines  │ 100   │
│ Valid        │ 95    │
│ Errors       │ 5     │
└──────────────┴───────┘

⚠️  Found 5 errors

Error Details:
  • Line 12: Invalid JSON - Expecting value: line 1 column 1 (char 0)
  • Line 34: Schema validation failed - 1 errors
  • Line 56: Invalid JSON - Extra data: line 1 column 50 (char 49)
```

---

### 4. `process` - Batch Processing

Process JSONL files containing news articles.

#### Basic Processing (Synchronous)

```bash
# Docker: Process locally (multi-threaded)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl

# Non-Docker
python -m src.main_cli process \
  -i ./data/input.jsonl \
  -o ./data/output.jsonl
```

#### Celery Processing (Asynchronous)

```bash
# Docker: Submit to Celery workers
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --celery

# Non-Docker
python -m src.main_cli process \
  -i ./data/input.jsonl \
  -o ./data/output.jsonl \
  --celery
```

#### Custom Cleaning Configuration

```bash
# Disable typo correction
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-typo-correction

# Disable HTML removal
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-html-removal

# Disable currency standardization
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-currency-standardization

# Combine multiple flags
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-typo-correction \
  --disable-html-removal \
  --celery
```

#### Specify Storage Backends

```bash
# Save to multiple backends
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --backends jsonl,postgresql,elasticsearch
```

#### Output

```
🚀 Starting Article Processing Pipeline

Configuration
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting         ┃ Value                            ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Input File      │ /app/data/input.jsonl            │
│ Output File     │ /app/data/output.jsonl           │
│ Processing Mode │ Local (Sync)                     │
│ Storage         │ Default (from config)            │
│ SpaCy Model     │ en_core_web_trf                  │
│ GPU Enabled     │ Yes                              │
└─────────────────┴──────────────────────────────────┘

Found 1500 articles to process

Processing ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:02:35

✅ Processing complete!
Results saved to: /app/data/output.jsonl
```

---

## Input File Format

The CLI expects JSONL (JSON Lines) format - one JSON object per line.

### Minimal Required Schema

```jsonl
{"document_id":"doc-001","text":"Article content here."}
{"document_id":"doc-002","text":"Another article."}
```

### Full Schema Example

```jsonl
{
  "document_id": "article-12345",
  "text": "Full article text content...",
  "title": "Article Title",
  "excerpt": "Brief summary",
  "author": "John Doe",
  "publication_date": "2024-03-15",
  "revision_date": "2024-03-16",
  "source_url": "https://example.com/article",
  "categories": ["Technology", "AI"],
  "tags": ["machine-learning", "nlp"],
  "media_asset_urls": ["https://example.com/image.jpg"],
  "geographical_data": {"city": "San Francisco", "country": "USA"},
  "embargo_date": "2024-04-01",
  "sentiment": "positive",
  "word_count": 1500,
  "publisher": "Tech News Daily",
  "additional_metadata": {"custom_field": "value"}
}
```

---

## Output File Format

Output is also in JSONL format with cleaned and enriched data.

### Output Schema

```jsonl
{
  "document_id": "article-12345",
  "version": "1.0",
  "original_text": "Original raw text...",
  "cleaned_text": "Cleaned and normalized text...",
  "cleaned_title": "Cleaned Title",
  "cleaned_excerpt": "Cleaned summary",
  "cleaned_author": "John Doe",
  "cleaned_publication_date": "2024-03-15",
  "cleaned_categories": ["Technology", "AI"],
  "cleaned_tags": ["machine-learning", "nlp"],
  "temporal_metadata": "2024-03-15",
  "entities": [
    {"text": "San Francisco", "type": "GPE", "start_char": 45, "end_char": 58},
    {"text": "March 15", "type": "DATE", "start_char": 100, "end_char": 108}
  ],
  "cleaned_additional_metadata": {
    "cleaned_language": "en",
    "cleaned_reading_time": 7
  }
}
```

---

## Advanced Usage Patterns

### 1. Pipeline Validation Before Processing

```bash
# Step 1: Validate input
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/input.jsonl

# Step 2: If valid, process
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl
```

### 2. Testing Configuration Before Batch

```bash
# Test cleaning pipeline with sample text
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Sample article from New York Times."

# If satisfied, run batch
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl
```

### 3. Large File Processing with Celery

```bash
# Submit large batch to Celery (non-blocking)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/large_input.jsonl \
  -o /app/data/large_output.jsonl \
  --celery

# Monitor progress in another terminal
docker compose exec ingestion-service celery -A src.celery_app inspect active

# Check logs
docker compose logs -f celery-worker
```

### 4. Custom Cleaning for Specific Use Cases

```bash
# Preserve original HTML (for web archiving)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-html-removal

# Skip typo correction (for historical text)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/historical.jsonl \
  -o /app/data/cleaned_historical.jsonl \
  --disable-typo-correction
```

---

## Troubleshooting

### Issue: "File not found"

**Docker:**

```bash
# Ensure file is in mounted volume
ls -la data/

# Check mount in container
docker compose exec ingestion-service ls -la /app/data/
```

**Non-Docker:**

```bash
# Use absolute paths or check working directory
pwd
ls -la ./data/
```

### Issue: "SpaCy model not loaded"

```bash
# Docker (rebuild with model)
docker compose down
docker compose build --no-cache ingestion-service
docker compose up -d

# Non-Docker
python -m spacy download en_core_web_trf
```

### Issue: "Celery workers not processing"

```bash
# Check Celery worker status
docker compose logs celery-worker

# Check Redis connectivity
docker compose exec redis redis-cli ping

# Restart workers
docker compose restart celery-worker
```

### Issue: "Out of memory errors"

```bash
# Reduce batch size by processing in chunks
split -l 1000 input.jsonl chunk_

# Process each chunk
for file in chunk_*; do
  docker compose exec ingestion-service python -m src.main_cli process \
    -i /app/data/$file \
    -o /app/data/output_$file
done
```

---

## Performance Tips

### 1. Use Celery for Large Batches

- **Sync mode**: Best for < 1,000 articles
- **Celery mode**: Best for > 1,000 articles or ongoing ingestion

### 2. Adjust Worker Concurrency

Edit `config/settings.yaml`:

```yaml
celery:
  worker_concurrency: 8  # Increase for more CPU cores
```

### 3. Disable Unnecessary Features

```bash
# Minimal cleaning for speed
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-typo-correction
```

### 4. Monitor Resource Usage

```bash
# Check container stats
docker stats ingestion-service celery-worker

# Check GPU usage (if enabled)
docker compose exec ingestion-service nvidia-smi
```

---

## CLI Help Reference

```bash
# Main help
docker compose exec ingestion-service python -m src.main_cli --help

# Command-specific help
docker compose exec ingestion-service python -m src.main_cli process --help
docker compose exec ingestion-service python -m src.main_cli validate --help
docker compose exec ingestion-service python -m src.main_cli test-model --help
```

---

## Next Steps

- **API Usage**: See [API Usage Guide](./API_USAGE.md)
- **Configuration**: See [README.md](./README.md#configuration)
- **Troubleshooting**: See [README.md](./README.md#troubleshooting)
