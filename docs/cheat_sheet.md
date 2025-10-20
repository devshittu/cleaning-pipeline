# 🚀 Data Ingestion Pipeline - Ultimate Cheat Sheet

## 📋 Quick Reference Card

| Component | Access | Port | Docs |
|-----------|--------|------|------|
| **API** | <http://localhost:8000> | 8000 | `/docs` |
| **Prometheus** | <http://localhost:9090> | 9090 | - |
| **Grafana** | <http://localhost:3000> | 3000 | admin/admin |
| **CLI** | `docker compose exec ingestion-service python -m src.main_cli` | - | `--help` |

---

## 🎯 CLI Commands Cheat Sheet

### Basic Commands

```bash
# Show system information
docker compose exec ingestion-service python -m src.main_cli info

# Test spaCy model
docker compose exec ingestion-service python -m src.main_cli test-model

# Test with custom text
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Apple Inc. released products in San Francisco yesterday."

# Validate JSONL file
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/input.jsonl
```

### Processing Commands

```bash
# Process file (synchronous - local processing)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl

# Process with Celery (asynchronous - distributed)
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --celery

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

# Multiple flags combined
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/input.jsonl \
  -o /app/data/output.jsonl \
  --disable-typo-correction \
  --disable-html-removal \
  --celery
```

### Documentation Commands

```bash
# View docs in terminal
docker compose exec ingestion-service python -m src.main_cli docs show

# Export as Markdown
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o /app/data/CLI_REFERENCE.md

# Export as JSON
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o /app/data/cli-schema.json

# Export as HTML
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/cli-docs.html

# Generate OpenAPI schema
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-openapi.json

# Copy docs to host
docker compose cp ingestion-service:/app/data/CLI_REFERENCE.md ./
```

---

## 🌐 API Commands Cheat Sheet

### Health & Info

```bash
# Health check
curl http://localhost:8000/health

# Service info
curl http://localhost:8000/

# Metrics (Prometheus format)
curl http://localhost:8000/metrics

# OpenAPI schema
curl http://localhost:8000/openapi.json | jq .
```

### Process Single Article (Synchronous)

```bash
# Minimal request
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-001",
      "text": "Apple Inc. announced new products in San Francisco."
    }
  }' | jq .

# Full metadata request
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-request-123" \
  -d '{
    "article": {
      "document_id": "news-001",
      "text": "The price is $100 and it weighs 5kg.",
      "title": "Product Review",
      "author": "John Doe",
      "publication_date": "2025-10-19",
      "source_url": "https://example.com/article"
    }
  }' | jq .

# With custom cleaning config
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-002",
      "text": "This is a tst article with typos."
    },
    "cleaning_config": {
      "enable_typo_correction": false,
      "standardize_currency": false
    }
  }' | jq .

# Save to specific backends
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-003",
      "text": "Article content here."
    },
    "persist_to_backends": ["jsonl", "postgresql"]
  }' | jq .
```

### Process Batch (Asynchronous via Celery)

```bash
# Submit batch
curl -X POST http://localhost:8000/v1/preprocess/batch \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {
        "document_id": "batch-001",
        "text": "First article content."
      },
      {
        "document_id": "batch-002",
        "text": "Second article content."
      },
      {
        "document_id": "batch-003",
        "text": "Third article content."
      }
    ]
  }' | jq .

# Response will include task_ids
# Save task IDs for status checking
```

### Upload File for Batch Processing

```bash
# Create test file
cat > test_articles.jsonl << 'EOF'
{"document_id":"file-001","text":"Article one."}
{"document_id":"file-002","text":"Article two."}
{"document_id":"file-003","text":"Article three."}
EOF

# Upload file
curl -X POST http://localhost:8000/v1/preprocess/batch-file \
  -F "file=@test_articles.jsonl" \
  -F "persist_to_backends=jsonl,postgresql" | jq .
```

### Check Task Status

```bash
# Check specific task
TASK_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
curl http://localhost:8000/v1/preprocess/status/$TASK_ID | jq .

# Check multiple tasks
for task_id in task1 task2 task3; do
  curl -s http://localhost:8000/v1/preprocess/status/$task_id | jq .
done
```

---

## 🐍 Python SDK Examples

### Using `requests` Library

```python
import requests
import json
import time

BASE_URL = "http://localhost:8000"

# 1. Health check
response = requests.get(f"{BASE_URL}/health")
print(f"Health: {response.json()}")

# 2. Process single article
article = {
    "article": {
        "document_id": "py-001",
        "text": "Microsoft announced Azure updates in Seattle.",
        "title": "Azure News",
        "author": "Tech Reporter"
    }
}

response = requests.post(
    f"{BASE_URL}/v1/preprocess",
    json=article,
    headers={"X-Request-ID": "python-req-001"}
)

if response.status_code == 200:
    result = response.json()
    print(f"Cleaned text: {result['cleaned_text']}")
    print(f"Entities: {result['entities']}")
    print(f"Language: {result.get('cleaned_additional_metadata', {}).get('cleaned_language')}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# 3. Submit batch with custom config
batch = {
    "articles": [
        {"document_id": f"py-batch-{i}", "text": f"Article {i}"}
        for i in range(10)
    ],
    "cleaning_config": {
        "enable_typo_correction": False
    }
}

response = requests.post(f"{BASE_URL}/v1/preprocess/batch", json=batch)
task_ids = response.json()["task_ids"]
print(f"Submitted {len(task_ids)} tasks")

# 4. Poll task status
def wait_for_task(task_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        response = requests.get(f"{BASE_URL}/v1/preprocess/status/{task_id}")
        data = response.json()
        
        if data["status"] == "SUCCESS":
            return data["result"]
        elif data["status"] == "FAILURE":
            raise Exception(f"Task failed: {data.get('error')}")
        
        print(f"Status: {data['status']}")
        time.sleep(2)
    
    raise TimeoutError(f"Task {task_id} timed out")

# Wait for first task
result = wait_for_task(task_ids[0])
print(f"Task completed: {result['document_id']}")

# 5. Upload file
with open("articles.jsonl", "rb") as f:
    files = {"file": f}
    data = {"persist_to_backends": "jsonl"}
    
    response = requests.post(
        f"{BASE_URL}/v1/preprocess/batch-file",
        files=files,
        data=data
    )
    
    print(response.json())

# 6. Error handling
try:
    response = requests.post(
        f"{BASE_URL}/v1/preprocess",
        json={"article": {"document_id": "test"}},  # Missing 'text'
        timeout=30
    )
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e.response.status_code}")
    print(f"Details: {e.response.json()}")
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
```

### Using `httpx` (Async)

```python
import httpx
import asyncio

async def process_articles_async():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Process multiple articles concurrently
        articles = [
            {"document_id": f"async-{i}", "text": f"Article {i}"}
            for i in range(5)
        ]
        
        tasks = [
            client.post(
                "http://localhost:8000/v1/preprocess",
                json={"article": article}
            )
            for article in articles
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                print(f"Article {i} failed: {response}")
            else:
                result = response.json()
                print(f"Article {i}: {result['document_id']} - {len(result['cleaned_text'])} chars")

# Run
asyncio.run(process_articles_async())
```

---

## 🟢 JavaScript/Node.js Examples

### Using `fetch` (Node.js 18+)

```javascript
const BASE_URL = 'http://localhost:8000';

// 1. Health check
async function checkHealth() {
  const response = await fetch(`${BASE_URL}/health`);
  const data = await response.json();
  console.log('Health:', data);
}

// 2. Process single article
async function processArticle() {
  const response = await fetch(`${BASE_URL}/v1/preprocess`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': 'js-req-001'
    },
    body: JSON.stringify({
      article: {
        document_id: 'js-001',
        text: 'Google released new AI features.',
        title: 'Google AI News'
      }
    })
  });
  
  const result = await response.json();
  console.log('Cleaned:', result.cleaned_text);
  console.log('Entities:', result.entities);
}

// 3. Submit batch
async function submitBatch() {
  const articles = Array.from({ length: 10 }, (_, i) => ({
    document_id: `js-batch-${i}`,
    text: `Article ${i} content.`
  }));
  
  const response = await fetch(`${BASE_URL}/v1/preprocess/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ articles })
  });
  
  const { task_ids } = await response.json();
  return task_ids;
}

// 4. Poll task status
async function pollTaskStatus(taskId) {
  while (true) {
    const response = await fetch(
      `${BASE_URL}/v1/preprocess/status/${taskId}`
    );
    const data = await response.json();
    
    if (data.status === 'SUCCESS') {
      console.log('Task completed:', data.result);
      break;
    } else if (data.status === 'FAILURE') {
      console.error('Task failed:', data.error);
      break;
    } else {
      console.log('Status:', data.status);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
}

// 5. Upload file
async function uploadFile() {
  const FormData = require('form-data');
  const fs = require('fs');
  
  const form = new FormData();
  form.append('file', fs.createReadStream('articles.jsonl'));
  form.append('persist_to_backends', 'jsonl');
  
  const response = await fetch(`${BASE_URL}/v1/preprocess/batch-file`, {
    method: 'POST',
    body: form
  });
  
  const result = await response.json();
  console.log('Upload result:', result);
}

// Run examples
(async () => {
  await checkHealth();
  await processArticle();
  const taskIds = await submitBatch();
  await pollTaskStatus(taskIds[0]);
})();
```

### Using `axios`

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const BASE_URL = 'http://localhost:8000';

// Process single article
axios.post(`${BASE_URL}/v1/preprocess`, {
  article: {
    document_id: 'axios-001',
    text: 'Tesla announced new models.'
  }
})
.then(response => {
  console.log('Result:', response.data);
})
.catch(error => {
  console.error('Error:', error.response?.data || error.message);
});

// Upload file
const form = new FormData();
form.append('file', fs.createReadStream('articles.jsonl'));
form.append('persist_to_backends', 'jsonl');

axios.post(`${BASE_URL}/v1/preprocess/batch-file`, form, {
  headers: form.getHeaders()
})
.then(response => {
  console.log('Upload:', response.data);
})
.catch(error => {
  console.error('Upload error:', error.response?.data || error.message);
});
```

---

## 🔧 Docker Management Commands

### Container Management

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart ingestion-service

# View logs
docker compose logs -f ingestion-service
docker compose logs -f celery-worker

# Check service status
docker compose ps

# Scale Celery workers
docker compose up -d --scale celery-worker=4

# Execute commands in container
docker compose exec ingestion-service bash

# Copy files to/from container
docker compose cp local-file.jsonl ingestion-service:/app/data/
docker compose cp ingestion-service:/app/data/output.jsonl ./
```

### Rebuild & Clean

```bash
# Rebuild single service
docker compose build ingestion-service

# Rebuild with no cache
docker compose build --no-cache

# Remove all containers and volumes
docker compose down -v

# Prune Docker system
docker system prune -a
```

---

## 📊 Monitoring Commands

### Prometheus Queries

Access at: <http://localhost:9090>

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# 95th percentile latency
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# Requests in progress
http_requests_in_progress

# Total requests by endpoint
sum by (path) (http_requests_total)
```

### Grafana Dashboards

Access at: <http://localhost:3000> (admin/admin)

Pre-configured dashboards:

- API Performance Overview
- Request/Response Metrics
- Error Rate Tracking
- Celery Worker Stats

### Log Analysis

```bash
# View structured logs
docker compose logs ingestion-service | grep ERROR

# Parse JSON logs
docker compose exec ingestion-service tail -f /app/logs/ingestion_service.jsonl | jq .

# Filter by document_id
docker compose exec ingestion-service grep "doc_001" /app/logs/ingestion_service.jsonl | jq .

# Count errors by type
docker compose exec ingestion-service grep "ERROR" /app/logs/ingestion_service.jsonl | jq -r .message | sort | uniq -c
```

---

## 🧪 Testing Scenarios

### Test 1: End-to-End Pipeline Test

```bash
# 1. Create test data
cat > /tmp/e2e_test.jsonl << 'EOF'
{"document_id":"e2e-001","text":"Apple Inc. released iPhone in San Francisco for $999."}
{"document_id":"e2e-002","text":"The company's revenue was €500M last quarter."}
{"document_id":"e2e-003","text":"Microsoft CEO spoke at the conference yesterday."}
EOF

# 2. Copy to container
docker compose cp /tmp/e2e_test.jsonl ingestion-service:/app/data/

# 3. Process via CLI
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/e2e_test.jsonl \
  -o /app/data/e2e_output.jsonl

# 4. Verify output
docker compose exec ingestion-service cat /app/data/e2e_output.jsonl | jq .

# 5. Check entities were extracted
docker compose exec ingestion-service cat /app/data/e2e_output.jsonl | \
  jq '.processed_data.entities'

# 6. Verify currency standardization
docker compose exec ingestion-service cat /app/data/e2e_output.jsonl | \
  jq '.processed_data.cleaned_text' | grep "USD\|EUR"
```

### Test 2: Malformed JSON Resilience

```bash
# Create file with problematic JSON
cat > /tmp/bad_json.jsonl << 'EOF'
{"document_id":"bad-001","text":"He said "hello" to me"}
{"document_id":"bad-002","text":"Price is $100—very expensive"}
{"document_id":"bad-003","text":"Text with​zero​width​spaces"}
EOF

docker compose cp /tmp/bad_json.jsonl ingestion-service:/app/data/

# Process - should handle all errors gracefully
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/bad_json.jsonl \
  -o /app/data/bad_json_output.jsonl

# Check success rate
docker compose exec ingestion-service cat /app/data/bad_json_output.jsonl | wc -l
```

### Test 3: Custom Cleaning Configuration

```bash
# Test with typo correction disabled
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/test.jsonl \
  -o /app/data/test_no_typo.jsonl \
  --disable-typo-correction

# Verify typos were NOT corrected
docker compose exec ingestion-service cat /app/data/test_no_typo.jsonl | \
  jq '.processed_data.cleaned_text'
```

### Test 4: API Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Create payload
cat > payload.json << 'EOF'
{
  "article": {
    "document_id": "load-test",
    "text": "This is a load test article."
  }
}
EOF

# Run load test
ab -n 100 -c 10 -p payload.json -T application/json \
  http://localhost:8000/v1/preprocess

# Check metrics
curl http://localhost:8000/metrics | grep http_requests_total
```

### Test 5: Celery Worker Scaling

```bash
# Start with 1 worker
docker compose up -d --scale celery-worker=1

# Submit large batch
# ... submit 1000 articles ...

# Monitor processing speed
docker compose logs -f celery-worker | grep "successfully processed"

# Scale to 4 workers
docker compose up -d --scale celery-worker=4

# Monitor improved throughput
```

---

## 🎯 Common Use Cases

### Use Case 1: Daily News Ingestion

```bash
#!/bin/bash
# daily_ingestion.sh

DATE=$(date +%Y-%m-%d)
INPUT_FILE="/data/news_${DATE}.jsonl"
OUTPUT_FILE="/data/processed_${DATE}.jsonl"

# Process with Celery
docker compose exec ingestion-service python -m src.main_cli process \
  -i $INPUT_FILE \
  -o $OUTPUT_FILE \
  --celery \
  --backends jsonl,postgresql

# Generate report
docker compose exec ingestion-service python << EOF
import json
with open('$OUTPUT_FILE') as f:
    articles = [json.loads(line) for line in f]
    print(f"Processed {len(articles)} articles on ${DATE}")
    print(f"Total entities: {sum(len(a['processed_data']['entities']) for a in articles)}")
EOF
```

### Use Case 2: Real-time API Integration

```python
# integration_service.py
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
PIPELINE_URL = "http://localhost:8000"

@app.route('/ingest', methods=['POST'])
def ingest_article():
    article_data = request.json
    
    # Send to pipeline
    response = requests.post(
        f"{PIPELINE_URL}/v1/preprocess",
        json={"article": article_data},
        timeout=30
    )
    
    if response.status_code == 200:
        return jsonify(response.json()), 200
    else:
        return jsonify({"error": "Processing failed"}), 500

if __name__ == '__main__':
    app.run(port=5000)
```

### Use Case 3: Batch ETL Pipeline

```python
# etl_pipeline.py
import requests
import pandas as pd
from datetime import datetime

def extract_from_database():
    # Extract articles from your database
    query = "SELECT * FROM raw_articles WHERE processed = FALSE LIMIT 1000"
    df = pd.read_sql(query, engine)
    return df

def transform_and_load(df):
    articles = df.to_dict('records')
    
    # Submit to pipeline
    response = requests.post(
        "http://localhost:8000/v1/preprocess/batch",
        json={"articles": articles}
    )
    
    task_ids = response.json()["task_ids"]
    print(f"Submitted {len(task_ids)} tasks")
    
    # Wait and collect results
    results = []
    for task_id in task_ids:
        result = wait_for_task(task_id)
        results.append(result)
    
    # Load to destination
    results_df = pd.DataFrame(results)
    results_df.to_sql('processed_articles', engine, if_exists='append')

# Run ETL
df = extract_from_database()
transform_and_load(df)
```

---

## 🆘 Troubleshooting Guide

### Issue: Service not responding

```bash
# Check if container is running
docker compose ps

# Check logs
docker compose logs ingestion-service

# Restart service
docker compose restart ingestion-service

# Health check
curl http://localhost:8000/health
```

### Issue: Celery tasks stuck

```bash
# Check Celery worker logs
docker compose logs celery-worker

# Check Redis
docker compose exec redis redis-cli ping

# Purge Celery queue
docker compose exec ingestion-service celery -A src.celery_app purge

# Restart workers
docker compose restart celery-worker
```

### Issue: Out of memory

```bash
# Check container memory
docker stats ingestion-service

# Reduce batch size in processing
# Edit config/settings.yaml:
# batch_processing_threads: 2  # Reduce from 4
```

### Issue: Slow processing

```bash
# Enable GPU (if available)
# Edit config/settings.yaml:
# gpu_enabled: True

# Scale Celery workers
docker compose up -d --scale celery-worker=8

# Check metrics
curl http://localhost:8000/metrics | grep duration
```

---

## 🔧 Shell Scripts Reference

### run-cli.sh - CLI Execution Wrapper

The `run-cli.sh` script provides a convenient way to run CLI commands from the host machine without typing the full Docker command.

**Location:** `./run-cli.sh`

**Content:**

```bash
#!/bin/bash
set -e

# Activate the virtual environment
source /opt/venv/bin/activate

# Debug: Print Python version and PYTHONPATH
echo "Python version: $(python --version)"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Current directory: $(pwd)"

# Execute the dedicated CLI entrypoint module using `python -m`.
# This is the standard and most robust way to run a CLI application.
# It ensures `sys.argv` is correctly structured for parsing.
# The `"$@"` passes all arguments from the shell script directly to the Python module.
echo "Executing command: python -m src.main_cli $@"
python -m src.main_cli "$@"

# No need for complex fallback logic; if the above fails, set -e will exit.
```

**Usage Examples:**

```bash
# Make executable
chmod +x run-cli.sh

# Run from host (via Docker exec)
docker compose exec ingestion-service ./run-cli.sh info
docker compose exec ingestion-service ./run-cli.sh test-model
docker compose exec ingestion-service ./run-cli.sh process -i /app/data/input.jsonl -o /app/data/output.jsonl

# Or copy to container and use
docker compose cp run-cli.sh ingestion-service:/app/
docker compose exec ingestion-service /app/run-cli.sh validate /app/data/input.jsonl
```

---

### run.sh - Docker Compose Management Script

The `run.sh` script provides convenient shortcuts for managing Docker services.

**Location:** `./run.sh`

**Content:**

```bash
#!/bin/bash

# === CONFIGURATION ===
SCRIPT_NAME="run.sh"
COMPOSE_PROD="docker-compose.yml"
COMPOSE_DEV="docker-compose.dev.yml"
LOGS_DIR="./logs"

# === ANSI COLORS ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# === HELP TEXT ===
show_help() {
  echo -e "${BLUE}Usage: ./$SCRIPT_NAME <command> [options] [dev|prod]${NC}"
  echo ""
  echo -e "${YELLOW}Commands:${NC}"
  echo "  start [services]       Start services (default: all)"
  echo "  rebuild [services]     Rebuild services (default: all)"
  echo "  rebuild-no-cache [services]  Rebuild with --no-cache"
  echo "  clean                  Clean logs and stop containers"
  echo "  down                   Stop and remove containers"
  echo "  status                 Show container statuses"
  echo "  logs [service]         Show logs for a service"
  echo "  help                   Show this help"
  echo ""
  echo -e "${YELLOW}Modes:${NC}"
  echo "  prod (default)         Use production config"
  echo "  dev                    Use development config (hot-reloading)"
  echo ""
  echo -e "${YELLOW}Examples:${NC}"
  echo "  Start all services (prod):          ./$SCRIPT_NAME start"
  echo "  Start all services (dev):           ./$SCRIPT_NAME start dev"
  echo "  Rebuild ingestion-service (dev):    ./$SCRIPT_NAME rebuild ingestion-service dev"
  echo "  Clean and rebuild all (prod):       ./$SCRIPT_NAME clean && ./$SCRIPT_NAME rebuild"
  echo "  Rebuild with no cache (dev):        ./$SCRIPT_NAME rebuild-no-cache dev"
  echo "  Check service logs (prod):          ./$SCRIPT_NAME logs ingestion-service"
  exit 0
}

# === UTILITY FUNCTIONS ===
get_compose_files() {
  local mode="$1"
  if [[ "$mode" == "dev" ]]; then
    echo "-f $COMPOSE_PROD -f $COMPOSE_DEV"
  else
    echo "-f $COMPOSE_PROD"
  fi
}

clean_logs() {
  echo -e "${YELLOW}[*] Cleaning logs...${NC}"
  sudo rm -rf "$LOGS_DIR"/* 2>/dev/null || true
}

prune_builder() {
  echo -e "${YELLOW}[*] Pruning Docker builder...${NC}"
  docker builder prune -f
}

compose_down() {
  local compose_files=$(get_compose_files "$mode")
  echo -e "${YELLOW}[*] Stopping containers...${NC}"
  docker compose $compose_files down -v
}

rebuild_service() {
  local service="$1"
  local no_cache="$2"
  local compose_files=$(get_compose_files "$mode")
  if [[ "$no_cache" == "true" ]]; then
    echo -e "${GREEN}[+] Rebuilding $service with --no-cache${NC}"
    docker compose $compose_files build --no-cache "$service"
  else
    echo -e "${GREEN}[+] Rebuilding $service${NC}"
    docker compose $compose_files build "$service"
  fi
}

start_services() {
  local services=("$@")
  local compose_files=$(get_compose_files "$mode")
  if [[ "${services[*]}" == "all" || ${#services[@]} -eq 0 ]]; then
    echo -e "${GREEN}[+] Starting all services...${NC}"
    docker compose $compose_files up -d
  else
    echo -e "${GREEN}[+] Starting services: ${services[*]}${NC}"
    docker compose $compose_files up -d "${services[@]}"
  fi
}

# === MAIN LOGIC ===
if [[ $# -eq 0 ]]; then
  show_help
fi

command="$1"
mode="prod"
if [[ "$2" == "dev" ]]; then
  mode="dev"
  shift 2
else
  shift 1
fi

case "$command" in
  start)
    start_services "$@"
    ;;
  
  rebuild)
    prune_builder
    if [[ -z "$1" ]]; then
      local compose_files=$(get_compose_files "$mode")
      docker compose $compose_files build
    else
      while [[ "$1" ]]; do
        rebuild_service "$1" "false"
        shift
      done
    fi
    ;;
  
  rebuild-no-cache)
    prune_builder
    if [[ -z "$1" ]]; then
      local compose_files=$(get_compose_files "$mode")
      docker compose $compose_files build --no-cache
    else
      while [[ "$1" ]]; do
        rebuild_service "$1" "true"
        shift
      done
    fi
    ;;
  
  clean)
    clean_logs
    compose_down
    ;;
  
  down)
    compose_down
    ;;
  
  status)
    local compose_files=$(get_compose_files "$mode")
    echo -e "${BLUE}[*] Container Status:${NC}"
    docker compose $compose_files ps
    ;;
  
  logs)
    if [[ -z "$1" ]]; then
      echo -e "${RED}[-] Please specify a service name!${NC}"
      exit 1
    fi
    local compose_files=$(get_compose_files "$mode")
    docker compose $compose_files logs -f "$1"
    ;;
  
  help|*)
    show_help
    ;;
esac
```

**Usage Examples:**

```bash
# Make executable
chmod +x run.sh

# Start all services (production)
./run.sh start

# Start all services (development with hot-reload)
./run.sh start dev

# Rebuild specific service
./run.sh rebuild ingestion-service

# Rebuild with no cache
./run.sh rebuild-no-cache ingestion-service

# Clean logs and stop everything
./run.sh clean

# Stop all containers
./run.sh down

# Check status
./run.sh status

# View logs
./run.sh logs ingestion-service
./run.sh logs celery-worker

# Rebuild everything (production)
./run.sh clean
./run.sh rebuild
./run.sh start

# Development workflow
./run.sh start dev
./run.sh logs ingestion-service  # Watch hot-reload in action
```

---

## 🎯 Combined Workflow Examples

### Complete Setup from Scratch

```bash
# 1. Clone repository
git clone <repository-url>
cd cleaning-pipeline

# 2. Make scripts executable
chmod +x run.sh
chmod +x run-cli.sh

# 3. Start services
./run.sh start

# 4. Wait for services to be ready (check logs)
./run.sh logs ingestion-service

# 5. Test health
curl http://localhost:8000/health

# 6. Run CLI commands
docker compose exec ingestion-service ./run-cli.sh info
docker compose exec ingestion-service ./run-cli.sh test-model
```

### Development Workflow

```bash
# 1. Start in development mode
./run.sh start dev

# 2. Make code changes in src/

# 3. Watch auto-reload in logs
./run.sh logs ingestion-service

# 4. Test changes immediately
docker compose exec ingestion-service ./run-cli.sh test-model \
  --text "Test with new changes"

# 5. Process test file
docker compose exec ingestion-service ./run-cli.sh process \
  -i /app/data/test.jsonl \
  -o /app/data/test_output.jsonl

# 6. Rebuild if needed
./run.sh rebuild ingestion-service dev
```

### Production Deployment

```bash
# 1. Clean environment
./run.sh clean

# 2. Rebuild with no cache
./run.sh rebuild-no-cache

# 3. Start services
./run.sh start

# 4. Verify health
curl http://localhost:8000/health
curl http://localhost:9090  # Prometheus
curl http://localhost:3000  # Grafana

# 5. Run production batch
docker compose exec ingestion-service ./run-cli.sh process \
  -i /app/data/production_input.jsonl \
  -o /app/data/production_output.jsonl \
  --celery

# 6. Monitor
./run.sh logs celery-worker
curl http://localhost:8000/metrics
```

### Troubleshooting with Scripts

```bash
# Check what's running
./run.sh status

# View logs for debugging
./run.sh logs ingestion-service

# Restart specific service
./run.sh down
./run.sh start ingestion-service

# Full clean restart
./run.sh clean
./run.sh rebuild-no-cache
./run.sh start

# Test CLI in isolation
docker compose exec ingestion-service bash
./run-cli.sh --help
./run-cli.sh info
```

---

## 📝 Script Installation

### Option 1: Download from Repository

```bash
# Assuming scripts are in repository
git clone <repository-url>
cd cleaning-pipeline
chmod +x run.sh run-cli.sh
```

### Option 2: Create Manually

```bash
# Create run.sh
cat > run.sh << 'EOF'
[paste run.sh content here]
EOF
chmod +x run.sh

# Create run-cli.sh
cat > run-cli.sh << 'EOF'
[paste run-cli.sh content here]
EOF
chmod +x run-cli.sh

# Copy run-cli.sh to container
docker compose cp run-cli.sh ingestion-service:/app/
```

### Option 3: Direct Execution

```bash
# If scripts are in Dockerfile
docker compose exec ingestion-service ./run-cli.sh --help

# Should work out of the box
```

---

## 🚀 Script Benefits

### run-cli.sh Benefits

✅ **Consistent environment** - Always uses correct Python environment  
✅ **Debug output** - Shows Python version and paths  
✅ **Clean argument passing** - Properly forwards all CLI arguments  
✅ **Error handling** - Fails fast with `set -e`  
✅ **Standard approach** - Uses `python -m` for module execution

### run.sh Benefits

✅ **Simplified commands** - No need to remember long docker compose commands  
✅ **Development mode** - Easy hot-reload with `dev` flag  
✅ **Color output** - Easy to read status messages  
✅ **Service management** - Start/stop/rebuild individual services  
✅ **Log access** - Quick log viewing  
✅ **Clean operations** - Easy cleanup of logs and containers

---

**💡 Pro Tip**: Add these scripts to your project README as "Quick Start" commands!

---

## 📚 Quick Links

- **API Documentation**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>
- **Prometheus**: <http://localhost:9090>
- **Grafana**: <http://localhost:3000>
- **Logs**: `docker compose logs -f ingestion-service`

---

**💡 Pro Tip**: Save this cheat sheet as `CHEATSHEET.md` in your project root for quick reference!

**🎉 Happy Processing!**
