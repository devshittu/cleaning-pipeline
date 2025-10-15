# Data Ingestion & Preprocessing Microservice

> **Enterprise-grade text preprocessing pipeline for news articles with NLP enrichment, multi-backend storage, and production-ready monitoring.**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green.svg)](https://fastapi.tiangolo.com/)
[![spaCy](https://img.shields.io/badge/spaCy-3.8.0-09a3d5.svg)](https://spacy.io/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![GPU Support](https://img.shields.io/badge/GPU-CUDA%20enabled-green.svg)](https://developer.nvidia.com/cuda-zone)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [Docker Setup](#docker-setup-recommended)
  - [Non-Docker Setup](#non-docker-setup)
- [Usage](#usage)
  - [API Usage](#api-usage)
  - [CLI Usage](#cli-usage)
- [Configuration](#configuration)
- [Storage Backends](#storage-backends)
- [Monitoring](#monitoring)
- [Development](#development)
- [Testing](#testing)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

The **Data Ingestion & Preprocessing Microservice** is a production-ready system for cleaning, normalizing, and enriching unstructured text data. Built specifically for news article processing pipelines, it provides:

- **Advanced Text Cleaning**: HTML removal, encoding fixes, punctuation normalization, typo correction
- **NLP Enrichment**: Named Entity Recognition (NER), temporal metadata extraction, language detection
- **Flexible Processing**: Synchronous API endpoints and asynchronous Celery workers
- **Multi-Backend Storage**: JSONL, PostgreSQL, Elasticsearch support
- **Production Monitoring**: Prometheus metrics, Grafana dashboards, structured logging
- **NER-Protected Typo Correction**: Prevents correcting proper nouns like "San Francisco"

### What Problems Does It Solve?

1. **Data Quality**: Cleans messy, unstructured text from various sources
2. **Standardization**: Normalizes dates, currencies, units across datasets
3. **Enrichment**: Extracts entities, metadata, and linguistic features
4. **Scale**: Processes thousands of articles efficiently with Celery workers
5. **Flexibility**: Configurable cleaning pipeline via YAML or API overrides
6. **Observability**: Built-in metrics and distributed tracing

---

## ✨ Features

### Text Cleaning Pipeline

- ✅ **HTML/Markup Removal**: Strips HTML tags and entities
- ✅ **Encoding Fixes**: Handles mojibake using `ftfy`
- ✅ **Punctuation Normalization**: Smart quotes, dashes, ellipses
- ✅ **Whitespace Normalization**: Collapses excessive spaces/tabs
- ✅ **Currency Standardization**: `$100` → `USD 100`
- ✅ **Unit Standardization**: `5m` → `5 meters`
- ✅ **NER-Protected Typo Correction**: Uses spaCy entities to avoid false corrections
- ✅ **Configurable**: Enable/disable each step via YAML or API

### NLP & Enrichment

- 🔍 **Named Entity Recognition**: Extracts people, organizations, locations, dates
- 📅 **Temporal Metadata Extraction**: Normalizes relative dates ("yesterday" → "2025-10-14")
- 🌍 **Language Detection**: Identifies article language using `langdetect`
- 📊 **Metadata Inference**: Calculates word count, reading time

### API & CLI

- 🚀 **RESTful API**: FastAPI with automatic OpenAPI docs
- 💻 **Rich CLI**: Beautiful terminal interface with progress bars
- 🔄 **Async Processing**: Celery integration for batch jobs
- 📁 **File Upload**: Process JSONL files via API
- ⚙️ **Custom Cleaning**: Per-request configuration overrides

### Storage & Infrastructure

- 💾 **Multi-Backend**: JSONL, PostgreSQL, Elasticsearch
- 🐳 **Dockerized**: Production-ready Docker Compose setup
- 🎯 **GPU Support**: CUDA-enabled for transformer models
- 📊 **Monitoring**: Prometheus + Grafana dashboards
- 🔍 **Distributed Tracing**: Request ID propagation
- ⚡ **Connection Pooling**: PostgreSQL (5-20 connections)
- 🔁 **Retry Logic**: Exponential backoff for resilience

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│         (Web UI, Scripts, Data Pipelines, ETL Jobs)             │
└─────────────────────┬───────────────────────┬───────────────────┘
                      │                       │
                      ├───────────────────────┤
                      │                       │
              ┌───────▼───────┐      ┌───────▼────────┐
              │   API Gateway │      │   CLI Tool     │
              │   (FastAPI)   │      │   (Click)      │
              │   Port 8000   │      │                │
              └───────┬───────┘      └───────┬────────┘
                      │                       │
                      └───────────┬───────────┘
                                  │
                     ┌────────────▼────────────┐
                     │  Text Preprocessor      │
                     │  (spaCy + NLP Pipeline) │
                     │  - Cleaning             │
                     │  - NER                  │
                     │  - Temporal Extraction  │
                     └────────────┬────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
          ┌───────▼───────┐ ┌────▼─────┐ ┌──────▼──────┐
          │  Celery Queue │ │  Redis   │ │   Storage   │
          │  (Async Jobs) │ │  Broker  │ │   Backends  │
          └───────┬───────┘ └──────────┘ └──────┬──────┘
                  │                              │
          ┌───────▼───────┐              ┌──────▼──────┐
          │ Celery Workers│              │   - JSONL   │
          │ (4x processes)│              │   - PostgreSQL
          └───────────────┘              │   - Elasticsearch
                                          └─────────────┘

                     ┌──────────────────────┐
                     │  Monitoring Stack    │
                     │  - Prometheus        │
                     │  - Grafana           │
                     │  - Structured Logs   │
                     └──────────────────────┘
```

### Processing Flow

1. **Ingestion**: Articles arrive via API POST or CLI file upload
2. **Validation**: Pydantic schemas validate structure
3. **Cleaning**: Modular pipeline applies configured cleaning steps
4. **NER Protection**: Entities extracted before typo correction
5. **Enrichment**: Temporal metadata, language detection
6. **Storage**: Results persisted to configured backends
7. **Response**: Synchronous return (API) or task ID (Celery)

---

## 🛠️ Tech Stack

### Core Framework

- **[FastAPI](https://fastapi.tiangolo.com/)** 0.111.0 - Modern async web framework
- **[Uvicorn](https://www.uvicorn.org/)** 0.30.1 - ASGI server

### NLP & Text Processing

- **[spaCy](https://spacy.io/)** 3.8.0 - Industrial-strength NLP
  - Model: `en_core_web_trf` (Transformer-based)
- **[ftfy](https://ftfy.readthedocs.io/)** 6.2.0 - Encoding fixes
- **[pyspellchecker](https://github.com/barrust/pyspellchecker)** 0.8.0 - Typo correction
- **[dateparser](https://dateparser.readthedocs.io/)** 1.2.0 - Date normalization
- **[langdetect](https://github.com/Mimino666/langdetect)** 1.0.9 - Language detection

### Data Validation

- **[Pydantic](https://docs.pydantic.dev/)** 2.7.1 - Data validation
- **[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** 2.2.1 - Configuration management

### Task Queue & Caching

- **[Celery](https://docs.celeryq.dev/)** 5.4.0 - Distributed task queue
- **[Redis](https://redis.io/)** 7.0 - Message broker & result backend

### Storage

- **[Elasticsearch](https://www.elastic.co/)** 8.14.0 - Search engine
- **[PostgreSQL](https://www.postgresql.org/)** 16.3 - Relational database
- **[psycopg2-binary](https://www.psycopg.org/)** 2.9.9 - PostgreSQL adapter

### Monitoring & Observability

- **[Prometheus](https://prometheus.io/)** - Metrics collection
- **[Grafana](https://grafana.com/)** - Visualization
- **[prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)** 7.0.0 - FastAPI metrics
- **[python-json-logger](https://github.com/madzak/python-json-logger)** 2.0.7 - Structured logging

### CLI

- **[Click](https://click.palletsprojects.com/)** 8.1.7 - CLI framework
- **[Rich](https://rich.readthedocs.io/)** 13.7.1 - Terminal formatting

### Infrastructure

- **[Docker](https://www.docker.com/)** - Containerization
- **[Docker Compose](https://docs.docker.com/compose/)** - Orchestration
- **[NVIDIA CUDA](https://developer.nvidia.com/cuda-zone)** - GPU acceleration

### Resilience

- **[Tenacity](https://tenacity.readthedocs.io/)** 8.3.0 - Retry logic with exponential backoff

---

## 🚀 Quick Start

### Prerequisites

**Docker Setup (Recommended):**

- Docker Engine 20.10+
- Docker Compose 2.0+
- NVIDIA Docker (optional, for GPU)
- 8GB RAM minimum, 16GB recommended

**Non-Docker Setup:**

- Python 3.11+
- Redis 7.0+ (for Celery)
- PostgreSQL 16+ (optional)
- Elasticsearch 8.14+ (optional)

---

### Docker Setup (Recommended)

#### 1. Clone Repository

```bash
git clone <repository-url>
cd cleaning-pipeline
```

#### 2. Configure Environment

```bash
# Review and customize settings
cat config/settings.yaml

# Optional: Create .env file for secrets
cat > .env << EOF
POSTGRES_PASSWORD=secure_password
ELASTICSEARCH_API_KEY=your_api_key
EOF
```

#### 3. Start Services

```bash
# Start all services
./run.sh start

# Or use docker compose directly
docker compose up -d
```

#### 4. Verify Installation

```bash
# Check service health
curl http://localhost:8000/health

# Test spaCy model
docker compose exec ingestion-service python -m src.main_cli test-model

# View API docs
open http://localhost:8000/docs
```

#### 5. Process Your First Article

```bash
# Via API
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-001",
      "text": "Apple Inc. announced new products in San Francisco yesterday."
    }
  }'

# Via CLI
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl
```

---

### Non-Docker Setup

#### 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
  build-essential redis-server postgresql-14

# macOS (using Homebrew)
brew install python@3.11 redis postgresql

# Start services
sudo systemctl start redis-server
sudo systemctl start postgresql
```

#### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_trf
```

#### 4. Configure Application

```bash
# Copy and edit configuration
cp config/settings.yaml config/settings.local.yaml

# Edit settings for local environment
nano config/settings.local.yaml
```

**Key changes for local setup:**

```yaml
general:
  gpu_enabled: False  # Unless you have CUDA

celery:
  broker_url: "redis://localhost:6379/0"
  result_backend: "redis://localhost:6379/0"

storage:
  jsonl:
    output_path: "./data/processed_articles.jsonl"
```

#### 5. Initialize Database (if using PostgreSQL)

```bash
# Create database
sudo -u postgres psql -c "CREATE DATABASE newsdb;"
sudo -u postgres psql -c "CREATE USER user WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE newsdb TO user;"
```

#### 6. Start Services

```bash
# Terminal 1: Start API
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start Celery worker
celery -A src.celery_app worker --loglevel=INFO --concurrency=4

# Terminal 3: Use CLI
python -m src.main_cli info
```

#### 7. Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# Test CLI
python -m src.main_cli test-model --text "Test article from New York."
```

---

## 📖 Usage

### API Usage

See **[API Usage Guide](./docs/API_USAGE.md)** for comprehensive examples.

**Quick Example:**

```bash
# Process single article
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "news-001",
      "text": "Microsoft released Azure updates in Seattle yesterday.",
      "title": "Azure Updates",
      "author": "Tech Reporter"
    }
  }' | jq .
```

**Interactive API Docs:**

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

### CLI Usage

See **[CLI Usage Guide](./docs/CLI_USAGE.md)** for comprehensive examples.

**Quick Examples:**

```bash
# Docker
docker compose exec ingestion-service python -m src.main_cli --help

# Show system info
docker compose exec ingestion-service python -m src.main_cli info

# Test model
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Apple Inc. in San Francisco"

# Process file (synchronous)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl

# Process with Celery (asynchronous)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --celery

# Validate file
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/input.jsonl
```

---

## ⚙️ Configuration

### Configuration File

All settings are in `config/settings.yaml`:

```yaml
general:
  log_level: INFO
  gpu_enabled: True

ingestion_service:
  model_name: "en_core_web_trf"
  model_cache_dir: "/app/.cache/spacy"
  
  # Cleaning pipeline - each step is configurable
  cleaning_pipeline:
    remove_html_tags: true
    normalize_whitespace: true
    fix_encoding: true
    normalize_punctuation: true
    standardize_units: true
    standardize_currency: true
    enable_typo_correction: true
    
    # Typo correction settings
    typo_correction:
      min_word_length: 2
      max_word_length: 15
      skip_capitalized_words: true
      use_ner_entities: true  # CRITICAL: Protects proper nouns
      confidence_threshold: 0.7

celery:
  broker_url: "redis://redis:6379/0"
  worker_concurrency: 4

storage:
  enabled_backends: ["jsonl"]  # Add "postgresql", "elasticsearch"
  
  jsonl:
    output_path: "/app/data/processed_articles.jsonl"
  
  postgresql:
    host: "postgres"
    port: 5432
    dbname: "newsdb"
    user: "user"
    password: "password"
  
  elasticsearch:
    host: "elasticsearch"
    port: 9200
    index_name: "news_articles"
```

### Runtime Configuration Overrides

**Via API (per-request):**

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {...},
    "cleaning_config": {
      "enable_typo_correction": false,
      "standardize_currency": false
    }
  }'
```

**Via CLI flags:**

```bash
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-typo-correction \
  --disable-html-removal
```

---

## 💾 Storage Backends

### JSONL (Default)

**Configuration:**

```yaml
storage:
  enabled_backends: ["jsonl"]
  jsonl:
    output_path: "/app/data/processed_articles.jsonl"
```

**Features:**

- Daily file rotation
- Human-readable format
- Easy integration with data pipelines

### PostgreSQL

**Configuration:**

```yaml
storage:
  enabled_backends: ["jsonl", "postgresql"]
  postgresql:
    host: "postgres"
    port: 5432
    dbname: "newsdb"
    user: "user"
    password: "password"
    table_name: "processed_articles"
```

**Enable in Docker Compose:**

Uncomment the `postgres` service in `docker-compose.yml`:

```yaml
postgres:
  image: postgres:16.3-alpine
  environment:
    POSTGRES_DB: newsdb
    POSTGRES_USER: user
    POSTGRES_PASSWORD: password
  ports:
    - "5432:5432"
  volumes:
    - pg_data:/var/lib/postgresql/data
```

**Features:**

- Connection pooling (5-20 connections)
- Automatic retry logic
- UPSERT on conflict

### Elasticsearch

**Configuration:**

```yaml
storage:
  enabled_backends: ["jsonl", "elasticsearch"]
  elasticsearch:
    host: "elasticsearch"
    port: 9200
    scheme: "http"
    index_name: "news_articles"
    api_key: null
```

**Enable in Docker Compose:**

Uncomment the `elasticsearch` service in `docker-compose.yml`:

```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.14.0
  environment:
    - xpack.security.enabled=false
    - discovery.type=single-node
    - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
  ports:
    - "9200:9200"
  volumes:
    - es_data:/usr/share/elasticsearch/data
```

**Features:**

- Bulk insert with 500-item batching
- Automatic index creation
- Retry logic for resilience

---

## 📊 Monitoring

### Prometheus Metrics

**Access:** <http://localhost:9090>

**Key Metrics:**

- `http_requests_total` - Total requests by endpoint/status
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_in_progress` - Active requests

**Query Examples:**

```promql
# Request rate by endpoint
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### Grafana Dashboards

**Access:** <http://localhost:3000> (user: `admin`, pass: `admin`)

**Pre-configured Dashboards:**

1. API Performance Overview
2. Request/Response Metrics
3. Error Rate Tracking
4. Celery Worker Stats

### Structured Logging

**Log Format:** JSON Lines

**Example Log Entry:**

```json
{
  "levelname": "INFO",
  "asctime": "2025-10-15 08:30:45,123",
  "filename": "processor.py",
  "funcName": "preprocess",
  "lineno": 245,
  "message": "Processing complete for document_id=news-001",
  "document_id": "news-001",
  "request_id": "a1b2c3d4-5678",
  "duration_ms": 125.34
}
```

**View Logs:**

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f ingestion-service

# Celery workers
docker compose logs -f celery-worker

# Tail JSON logs
tail -f logs/ingestion_service.jsonl | jq .
```

---

## 🔧 Development

### Development Mode

**Enable hot-reloading:**

```bash
# Use development compose file
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or use run script
./run.sh start dev
```

**Changes in dev mode:**

- Source code mounted as volume
- Auto-reload on file changes
- Debug logging enabled

### Project Structure

```
cleaning-pipeline/
├── config/
│   └── settings.yaml          # Configuration
├── data/
│   ├── input.jsonl            # Sample input
│   └── output.jsonl           # Processed output
├── logs/
│   └── ingestion_service.jsonl
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       └── datasources/
├── src/
│   ├── api/
│   │   └── app.py             # FastAPI application
│   ├── core/
│   │   └── processor.py       # Text preprocessing logic
│   ├── schemas/
│   │   └── data_models.py     # Pydantic models
│   ├── storage/
│   │   └── backends.py        # Storage implementations
│   ├── utils/
│   │   ├── config_manager.py  # Configuration loading
│   │   ├── logger.py          # Logging setup
│   │   └── text_cleaners.py   # Modular cleaning functions
│   ├── celery_app.py          # Celery configuration
│   ├── main.py                # CLI batch processing
│   └── main_cli.py            # Click CLI interface
├── tests/
│   └── test_enhancements.py   # Unit tests
├── docker-compose.yml         # Production setup
├── docker-compose.dev.yml     # Development overrides
├── Dockerfile                 # Application container
├── requirements.txt           # Python dependencies
├── run.sh                     # Helper script
└── README.md                  # This file
```

### Adding New Features

#### 1. Add a New Cleaning Step

**In `src/utils/text_cleaners.py`:**

```python
def remove_emojis(text: str) -> str:
    """Remove emoji characters from text."""
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text)
```

**In `config/settings.yaml`:**

```yaml
cleaning_pipeline:
  remove_emojis: true
```

**In `src/utils/config_manager.py`:**

```python
class CleaningPipelineSettings(BaseModel):
    remove_emojis: bool = Field(True, description="Remove emoji characters.")
```

#### 2. Add a New Storage Backend

Create a new class in `src/storage/backends.py`:

```python
class MongoDBStorageBackend(StorageBackend):
    def __init__(self, config: MongoDBStorageConfig):
        # Implementation
        pass
    
    def save(self, data: PreprocessSingleResponse, **kwargs) -> None:
        # Implementation
        pass
```

Update `StorageBackendFactory.get_backends()` to include the new backend.

---

## 🧪 Testing

### Run Unit Tests

```bash
# Docker
docker compose exec ingestion-service pytest tests/ -v

# Non-Docker
pytest tests/ -v --cov=src --cov-report=html
```

### Test Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

### Integration Tests

```bash
# Test API endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/preprocess -d '{...}'

# Test CLI
docker compose exec ingestion-service python -m src.main_cli test-model
```

### Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test API
ab -n 1000 -c 10 -p payload.json -T application/json \
  http://localhost:8000/v1/preprocess
```

---

## ⚡ Performance

### Benchmarks

**Hardware:** RTX A4000 GPU, 32GB RAM, 8-core CPU

| Mode | Articles/min | Latency (p95) | Notes |
|------|--------------|---------------|-------|
| API (sync) | 120 | 250ms | Single-threaded |
| CLI (multi-thread) | 480 | N/A | 4 threads |
| Celery (async) | 1,200 | N/A | 4 workers |
| Celery (GPU) | 2,400 | N/A | GPU-accelerated NER |

### Optimization Tips

#### 1. Enable GPU Acceleration

```yaml
# config/settings.yaml
general:
  gpu_enabled: True
```

```bash
# Verify GPU usage
docker compose exec ingestion-service nvidia-smi
```

#### 2. Scale Celery Workers

```bash
# Scale to 8 workers
docker compose up -d --scale celery-worker=8

# Or edit config/settings.yaml
celery:
  worker_concurrency: 8
```

#### 3. Tune Batch Processing

```yaml
ingestion_service:
  batch_processing_threads: 8  # For CLI
```

#### 4. Disable Expensive Features

For high-throughput scenarios:

```yaml
cleaning_pipeline:
  enable_typo_correction: false  # Most expensive operation
  fix_encoding: true  # Keep for data quality
```

#### 5. Connection Pooling

PostgreSQL automatically uses pooling (5-20 connections). Adjust in code:

```python
# src/storage/backends.py
PostgreSQLStorageBackend._connection_pool = psycopg2_pool.ThreadedConnectionPool(
    minconn=10,
    maxconn=50,
    **self.conn_params
)
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. SpaCy Model Not Found

**Error:** `OSError: [E050] Can't find model 'en_core_web_trf'`

**Solution:**

```bash
# Docker: Rebuild with model
docker compose down
docker compose build --no-cache ingestion-service
docker compose up -d

# Non-Docker: Download model
python -m spacy download en_core_web_trf
```

#### 2. GPU Not Detected

**Error:** `SpaCy GPU unavailable: Cannot use GPU, CuPy is not installed`

**Solution:**

```bash
# Install NVIDIA Docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

#### 3. Celery Workers Not Processing

**Check worker status:**

```bash
docker compose logs celery-worker
docker compose exec ingestion-service celery -A src.celery_app inspect active
```

**Restart workers:**

```bash
docker compose restart celery-worker
```

#### 4. Out of Memory Errors

**Reduce batch size:**

```bash
# Split large files
split -l 500 input.jsonl chunk_

# Process in smaller batches
for file in chunk_*; do
  docker compose exec ingestion-service python -m src.main_cli process \
    -i /app/data/$file \
    -o /app/data/output_$file
done
```

#### 5. Port Already in Use

**Error:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:**

```bash
# Find process using port
sudo lsof -i :8000

# Kill process or change port in docker-compose.yml
```

### Debug Mode

**Enable debug logging:**

```yaml
# config/settings.yaml
general:
  log_level: DEBUG
```

```bash
# Restart services
docker compose restart ingestion-service celery-worker
```

### Health Checks

```bash
# API
curl http://localhost:8000/health

# Redis
docker compose exec redis redis-cli ping

# PostgreSQL (if enabled)
docker compose exec postgres pg_isready

# Elasticsearch (if enabled)
curl http://localhost:9200/_cluster/health
```

---

## 📚 Documentation

- **[CLI Usage Guide](./docs/CLI_USAGE.md)** - Comprehensive CLI examples
- **[API Usage Guide](./docs/API_USAGE.md)** - REST API reference
- **[API Docs (Swagger)](http://localhost:8000/docs)** - Interactive API documentation
- **[Configuration Reference](./config/settings.yaml)** - All available settings

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/`)
6. Commit with clear messages (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings for public functions
- Keep functions focused and small

### Testing Requirements

- Unit tests for new features
- Integration tests for API endpoints
- Maintain >80% code coverage

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **spaCy** team for excellent NLP library
- **FastAPI** for modern Python web framework
- **Celery** for distributed task processing
- **Prometheus** and **Grafana** for monitoring

---

## 📞 Support

For issues, questions, or contributions:

- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email:** <support@example.com>

---

## 🗺️ Roadmap

- [ ] Add support for more languages (multilingual models)
- [ ] Implement real-time streaming API
- [ ] Add S3/Cloud storage backends
- [ ] Machine learning-based content classification
- [ ] GraphQL API support
- [ ] Kubernetes deployment manifests
- [ ] Advanced sentiment analysis
- [ ] Document summarization
- [ ] Topic modeling integration

---

**Made with ❤️ for data engineers and NLP practitioners**
