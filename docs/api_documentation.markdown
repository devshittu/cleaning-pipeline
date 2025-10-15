# API Usage Guide

## Overview

The Data Ingestion & Preprocessing API provides RESTful endpoints for real-time article processing. It supports both synchronous (immediate) and asynchronous (Celery-based) processing modes.

**Base URL**: `http://localhost:8000` (Docker) or your deployed endpoint

**API Version**: v1

---

## Quick Start

### 1. Check Service Health

```bash
# Docker
curl http://localhost:8000/health

# Non-Docker
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "model_loaded": true,
  "spacy_model": "en_core_web_trf",
  "celery_broker_connected": true,
  "gpu_enabled": true
}
```

### 2. View API Documentation

```bash
# Interactive Swagger UI
open http://localhost:8000/docs

# ReDoc documentation
open http://localhost:8000/redoc
```

---

## API Endpoints

### 1. Root Endpoint

Get service information and available endpoints.

**Request:**

```bash
curl http://localhost:8000/
```

**Response:**

```json
{
  "service": "Data Ingestion & Preprocessing Service",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs",
  "health": "/health",
  "metrics": "/metrics",
  "api_version": "v1",
  "endpoints": {
    "health": "GET /health",
    "metrics": "GET /metrics",
    "preprocess_single": "POST /v1/preprocess",
    "preprocess_batch": "POST /v1/preprocess/batch",
    "preprocess_file": "POST /v1/preprocess/batch-file",
    "task_status": "GET /v1/preprocess/status/{task_id}"
  }
}
```

---

### 2. Health Check

Check service availability and dependencies.

**Endpoint:** `GET /health`

**Docker Request:**

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "model_loaded": true,
  "spacy_model": "en_core_web_trf",
  "celery_broker_connected": true,
  "gpu_enabled": true
}
```

---

### 3. Prometheus Metrics

View Prometheus metrics for monitoring.

**Endpoint:** `GET /metrics`

**Docker Request:**

```bash
curl http://localhost:8000/metrics
```

**Response:** (Prometheus format)

```
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 384.0
...
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/v1/preprocess",status="200"} 150.0
```

---

### 4. Preprocess Single Article (Synchronous)

Process a single article and get immediate results.

**Endpoint:** `POST /v1/preprocess`

**Request Body Schema:**

```json
{
  "article": {
    "document_id": "string (required)",
    "text": "string (required)",
    "title": "string (optional)",
    "excerpt": "string (optional)",
    "author": "string (optional)",
    "publication_date": "YYYY-MM-DD (optional)",
    "revision_date": "YYYY-MM-DD (optional)",
    "source_url": "string (optional)",
    "categories": ["string"] (optional),
    "tags": ["string"] (optional),
    "media_asset_urls": ["string"] (optional),
    "geographical_data": {} (optional),
    "embargo_date": "YYYY-MM-DD (optional)",
    "sentiment": "string (optional)",
    "word_count": integer (optional),
    "publisher": "string (optional)",
    "additional_metadata": {} (optional)
  },
  "persist_to_backends": ["jsonl", "postgresql"] (optional),
  "cleaning_config": {
    "enable_typo_correction": true,
    "standardize_currency": true
  } (optional)
}
```

#### Example 1: Minimal Request

**Docker:**

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-001",
      "text": "Apple Inc. announced new products in San Francisco yesterday."
    }
  }'
```

**Response:**

```json
{
  "document_id": "test-001",
  "version": "1.0",
  "original_text": "Apple Inc. announced new products in San Francisco yesterday.",
  "cleaned_text": "Apple Inc. announced new products in San Francisco yesterday.",
  "cleaned_title": null,
  "cleaned_excerpt": null,
  "cleaned_author": null,
  "temporal_metadata": "2025-10-14",
  "entities": [
    {
      "text": "Apple Inc.",
      "type": "ORG",
      "start_char": 0,
      "end_char": 10
    },
    {
      "text": "San Francisco",
      "type": "GPE",
      "start_char": 37,
      "end_char": 50
    },
    {
      "text": "yesterday",
      "type": "DATE",
      "start_char": 51,
      "end_char": 60
    }
  ],
  "cleaned_additional_metadata": {
    "cleaned_language": "en",
    "cleaned_reading_time": 1
  }
}
```

#### Example 2: Full Metadata Request

**Docker:**

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-12345" \
  -d '{
    "article": {
      "document_id": "news-67890",
      "text": "The startup raised $5M in funding. The price is $100 per share.",
      "title": "Startup Funding News",
      "excerpt": "Major funding round announced",
      "author": "Jane Reporter",
      "publication_date": "2024-03-15",
      "source_url": "https://example.com/article",
      "categories": ["Business", "Technology"],
      "tags": ["startup", "funding", "venture-capital"],
      "sentiment": "positive",
      "publisher": "Tech News Daily"
    },
    "persist_to_backends": ["jsonl", "postgresql"]
  }'
```

**Response:**

```json
{
  "document_id": "news-67890",
  "version": "1.0",
  "original_text": "The startup raised $5M in funding. The price is $100 per share.",
  "cleaned_text": "The startup raised USD 5 M in funding. The price is USD 100 per share.",
  "cleaned_title": "Startup Funding News",
  "cleaned_excerpt": "Major funding round announced",
  "cleaned_author": "Jane Reporter",
  "cleaned_publication_date": "2024-03-15",
  "cleaned_source_url": "https://example.com/article",
  "cleaned_categories": ["Business", "Technology"],
  "cleaned_tags": ["startup", "funding", "venture-capital"],
  "cleaned_sentiment": "positive",
  "cleaned_publisher": "Tech News Daily",
  "cleaned_word_count": 12,
  "temporal_metadata": "2024-03-15",
  "entities": [
    {
      "text": "USD 5",
      "type": "MONEY",
      "start_char": 20,
      "end_char": 25
    }
  ],
  "cleaned_additional_metadata": {
    "cleaned_language": "en",
    "cleaned_reading_time": 1
  }
}
```

#### Example 3: Custom Cleaning Configuration

**Docker:**

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "test-002",
      "text": "This is a tst article with typos in New York."
    },
    "cleaning_config": {
      "enable_typo_correction": false,
      "standardize_currency": false
    }
  }'
```

---

### 5. Preprocess Batch (Asynchronous via Celery)

Submit multiple articles for asynchronous processing.

**Endpoint:** `POST /v1/preprocess/batch`

**Request Body:**

```json
{
  "articles": [
    {
      "document_id": "string",
      "text": "string",
      ...
    }
  ],
  "persist_to_backends": ["jsonl"],
  "cleaning_config": {} (optional)
}
```

#### Example: Batch Submission

**Docker:**

```bash
curl -X POST http://localhost:8000/v1/preprocess/batch \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {
        "document_id": "batch-001",
        "text": "First article content here."
      },
      {
        "document_id": "batch-002",
        "text": "Second article content here."
      },
      {
        "document_id": "batch-003",
        "text": "Third article content here."
      }
    ],
    "persist_to_backends": ["jsonl"]
  }'
```

**Response:**

```json
{
  "message": "Batch processing job submitted to Celery.",
  "task_ids": [
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "c3d4e5f6-a7b8-9012-cdef-123456789012"
  ],
  "batch_size": 3,
  "request_id": "req-abc123"
}
```

**Rate Limiting:**

- Maximum batch size: **1,000 articles** per request
- Requests exceeding limit will return `413 Request Entity Too Large`

---

### 6. Preprocess Batch File Upload

Upload a JSONL file for batch processing.

**Endpoint:** `POST /v1/preprocess/batch-file`

**Content-Type:** `multipart/form-data`

**Parameters:**

- `file`: JSONL file (required)
- `persist_to_backends`: Comma-separated backend names (optional)

#### Example: File Upload

**Docker:**

```bash
# Create sample file
cat > /tmp/sample.jsonl << EOF
{"document_id":"file-001","text":"Article one."}
{"document_id":"file-002","text":"Article two."}
{"document_id":"file-003","text":"Article three."}
EOF

# Upload file
curl -X POST http://localhost:8000/v1/preprocess/batch-file \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/tmp/sample.jsonl" \
  -F "persist_to_backends=jsonl,postgresql"
```

**Response:**

```json
{
  "message": "Batch file processing job submitted to Celery.",
  "task_ids": [
    "d4e5f6a7-b8c9-0123-defg-234567890123",
    "e5f6a7b8-c9d0-1234-efgh-345678901234",
    "f6a7b8c9-d0e1-2345-fghi-456789012345"
  ],
  "total_articles": 3,
  "skipped_lines": 0,
  "request_id": "req-xyz789"
}
```

**File Constraints:**

- Maximum file size: **50 MB**
- Maximum articles per file: **1,000**
- Format: JSONL (one JSON object per line)

---

### 7. Check Task Status

Retrieve the status and result of a Celery task.

**Endpoint:** `GET /v1/preprocess/status/{task_id}`

**Docker Request:**

```bash
# Get task status
curl http://localhost:8000/v1/preprocess/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

#### Response: Pending

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PENDING",
  "message": "Task is pending or unknown.",
  "request_id": "req-abc123"
}
```

#### Response: Started

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "STARTED",
  "message": "Task has started processing.",
  "request_id": "req-abc123"
}
```

#### Response: Success

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "SUCCESS",
  "result": {
    "document_id": "batch-001",
    "version": "1.0",
    "cleaned_text": "First article content here.",
    "entities": [],
    ...
  },
  "message": "Task completed successfully.",
  "request_id": "req-abc123"
}
```

#### Response: Failure

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "FAILURE",
  "error": "ValidationError: Invalid document_id",
  "message": "Task failed.",
  "request_id": "req-abc123"
}
```

---

## Python SDK Examples

### Using `requests` Library

```python
import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

# 1. Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 2. Process single article
article_data = {
    "article": {
        "document_id": "py-001",
        "text": "Microsoft announced Azure updates in Seattle.",
        "title": "Azure Updates",
        "author": "Tech Reporter"
    }
}

response = requests.post(
    f"{BASE_URL}/v1/preprocess",
    json=article_data,
    headers={"X-Request-ID": "custom-req-001"}
)

if response.status_code == 200:
    result = response.json()
    print(f"Cleaned text: {result['cleaned_text']}")
    print(f"Entities: {result['entities']}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# 3. Submit batch
batch_data = {
    "articles": [
        {"document_id": f"py-batch-{i}", "text": f"Article {i} content."}
        for i in range(10)
    ]
}

response = requests.post(f"{BASE_URL}/v1/preprocess/batch", json=batch_data)
task_ids = response.json()["task_ids"]

# 4. Check task status
import time

for task_id in task_ids:
    while True:
        response = requests.get(f"{BASE_URL}/v1/preprocess/status/{task_id}")
        status_data = response.json()
        
        if status_data["status"] == "SUCCESS":
            print(f"Task {task_id} completed!")
            print(status_data["result"])
            break
        elif status_data["status"] == "FAILURE":
            print(f"Task {task_id} failed: {status_data['error']}")
            break
        else:
            print(f"Task {task_id} status: {status_data['status']}")
            time.sleep(2)

# 5. Upload file
with open("data/input.jsonl", "rb") as f:
    files = {"file": f}
    data = {"persist_to_backends": "jsonl,postgresql"}
    
    response = requests.post(
        f"{BASE_URL}/v1/preprocess/batch-file",
        files=files,
        data=data
    )
    
    print(response.json())
```

### Using `httpx` (Async)

```python
import httpx
import asyncio

async def process_articles():
    async with httpx.AsyncClient() as client:
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
        
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            result = response.json()
            print(f"Processed: {result['document_id']}")

asyncio.run(process_articles())
```

---

## JavaScript/Node.js Examples

### Using `fetch` (Node.js 18+)

```javascript
// 1. Health check
async function checkHealth() {
  const response = await fetch('http://localhost:8000/health');
  const data = await response.json();
  console.log(data);
}

// 2. Process single article
async function processArticle() {
  const response = await fetch('http://localhost:8000/v1/preprocess', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': 'js-req-001'
    },
    body: JSON.stringify({
      article: {
        document_id: 'js-001',
        text: 'Google released new AI features in Mountain View.',
        title: 'Google AI News'
      }
    })
  });
  
  const result = await response.json();
  console.log('Cleaned text:', result.cleaned_text);
  console.log('Entities:', result.entities);
}

// 3. Submit batch
async function submitBatch() {
  const articles = Array.from({ length: 10 }, (_, i) => ({
    document_id: `js-batch-${i}`,
    text: `Article ${i} content.`
  }));
  
  const response = await fetch('http://localhost:8000/v1/preprocess/batch', {
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
      `http://localhost:8000/v1/preprocess/status/${taskId}`
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

// Run examples
checkHealth();
processArticle();
submitBatch().then(taskIds => {
  taskIds.forEach(pollTaskStatus);
});
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
    text: 'Tesla announced new models in Austin, Texas.'
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
form.append('file', fs.createReadStream('data/input.jsonl'));
form.append('persist_to_backends', 'jsonl');

axios.post(`${BASE_URL}/v1/preprocess/batch-file`, form, {
  headers: form.getHeaders()
})
.then(response => {
  console.log('Upload result:', response.data);
})
.catch(error => {
  console.error('Upload error:', error.response?.data || error.message);
});
```

---

## cURL Advanced Examples

### 1. Custom Headers and Request ID

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: custom-tracking-id-12345" \
  -H "User-Agent: MyApp/1.0" \
  -d '{
    "article": {
      "document_id": "curl-001",
      "text": "Amazon Web Services expanded to new regions."
    }
  }' | jq .
```

### 2. Save Response to File

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "curl-002",
      "text": "Netflix released quarterly earnings report."
    }
  }' \
  -o response.json

# Pretty print
cat response.json | jq .
```

### 3. Measure Response Time

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "article": {
      "document_id": "perf-test",
      "text": "Performance testing article content."
    }
  }' \
  -w "\nTime: %{time_total}s\nStatus: %{http_code}\n" \
  -o /dev/null -s
```

### 4. Batch with Custom Config

```bash
curl -X POST http://localhost:8000/v1/preprocess/batch \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {"document_id": "batch-1", "text": "Article 1"},
      {"document_id": "batch-2", "text": "Article 2"}
    ],
    "cleaning_config": {
      "enable_typo_correction": false,
      "standardize_currency": true
    },
    "persist_to_backends": ["jsonl"]
  }' | jq .
```

### 5. Upload Large File with Progress

```bash
curl -X POST http://localhost:8000/v1/preprocess/batch-file \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/large_input.jsonl" \
  -F "persist_to_backends=jsonl,elasticsearch" \
  --progress-bar | jq .
```

---

## Response Headers

All responses include these headers:

- `X-Request-ID`: Trace ID for the request (auto-generated or from request)
- `X-Process-Time`: Processing duration in milliseconds
- `Content-Type`: `application/json`

**Example:**

```bash
curl -I http://localhost:8000/v1/preprocess \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"article":{"document_id":"test","text":"Test"}}'
```

**Response:**

```
HTTP/1.1 200 OK
content-type: application/json
x-request-id: a1b2c3d4-5678-90ab-cdef-1234567890ab
x-process-time: 125.34ms
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Article processed successfully |
| 202 | Accepted | Batch job submitted to Celery |
| 400 | Bad Request | Invalid JSON or missing required fields |
| 413 | Payload Too Large | Batch size > 1000 or file > 50MB |
| 422 | Validation Error | Schema validation failed |
| 500 | Internal Error | Processing error |
| 503 | Service Unavailable | SpaCy model not loaded |

### Error Examples

#### 400 Bad Request

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{"article":{}}'
```

**Response:**

```json
{
  "detail": "Invalid input: [{'type': 'missing', 'loc': ('article', 'document_id')}]"
}
```

#### 413 Payload Too Large

```bash
curl -X POST http://localhost:8000/v1/preprocess/batch \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [/* 1001 articles */]
  }'
```

**Response:**

```json
{
  "detail": "Batch size (1001) exceeds maximum allowed (1000). Please split your batch into smaller chunks."
}
```

---

## Rate Limiting

Default rate limits (configurable in `config/settings.yaml`):

- **Per endpoint**: 300 requests/minute
- **Batch size**: Max 1,000 articles per request
- **File upload**: Max 50 MB per file

**Headers:**

- No rate limit headers currently exposed (can be added via middleware)

---

## Monitoring & Observability

### Prometheus Metrics

Available at: `http://localhost:8000/metrics`

**Key Metrics:**

- `http_requests_total`: Total HTTP requests by method/path/status
- `http_request_duration_seconds`: Request duration histogram
- `http_requests_in_progress`: Current requests being processed

### Grafana Dashboards

Access at: `http://localhost:3000` (user: `admin`, pass: `admin`)

Pre-configured dashboards:

- API Performance Overview
- Request/Response Metrics
- Error Rate Tracking

---

## Best Practices

### 1. Use Request IDs for Tracing

```bash
curl -X POST http://localhost:8000/v1/preprocess \
  -H "X-Request-ID: order-123-process" \
  -H "Content-Type: application/json" \
  -d '{"article":{...}}'
```

### 2. Handle Asynchronous Results

```python
import requests
import time

def wait_for_task(task_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        response = requests.get(
            f"http://localhost:8000/v1/preprocess/status/{task_id}"
        )
        data = response.json()
        
        if data["status"] in ["SUCCESS", "FAILURE"]:
            return data
        
        time.sleep(2)
    
    raise TimeoutError(f"Task {task_id} timed out")
```

### 3. Batch Large Datasets

```python
import requests

def process_in_batches(articles, batch_size=500):
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        response = requests.post(
            "http://localhost:8000/v1/preprocess/batch",
            json={"articles": batch}
        )
        print(f"Submitted batch {i//batch_size + 1}: {response.json()}")
```

### 4. Implement Retry Logic

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def process_with_retry(article_data):
    response = requests.post(
        "http://localhost:8000/v1/preprocess",
        json=article_data,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
```

---

## Performance Tips

### 1. Use Async for High Throughput

```python
import asyncio
import httpx

async def process_concurrent(articles, max_concurrent=10):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_one(article):
        async with semaphore:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/v1/preprocess",
                    json={"article": article}
                )
                return response.json()
    
    tasks = [process_one(article) for article in articles]
    return await asyncio.gather(*tasks)
```

### 2. Use Celery for Large Batches

For > 100 articles, prefer async batch endpoints:

- `/v1/preprocess/batch` for JSON payloads
- `/v1/preprocess/batch-file` for file uploads

### 3. Connection Pooling

```python
import requests

# Reuse session for connection pooling
session = requests.Session()

for article in articles:
    response = session.post(
        "http://localhost:8000/v1/preprocess",
        json={"article": article}
    )
```

---

## Troubleshooting

### Issue: Connection Refused

```bash
# Check if service is running
docker compose ps

# Check logs
docker compose logs ingestion-service

# Restart service
docker compose restart ingestion-service
```

### Issue: 503 Service Unavailable

```bash
# Check health endpoint
curl http://localhost:8000/health

# Verify spaCy model loaded
docker compose exec ingestion-service python -c "import spacy; spacy.load('en_core_web_trf')"
```

### Issue: Slow Response Times

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep http_request_duration

# Check container resources
docker stats ingestion-service

# Scale Celery workers
docker compose up -d --scale celery-worker=4
```

---

## API Versioning

Current version: **v1**

All endpoints are prefixed with `/v1/`:

- `/v1/preprocess`
- `/v1/preprocess/batch`
- `/v1/preprocess/batch-file`
- `/v1/preprocess/status/{task_id}`

Future versions will be accessible via `/v2/`, `/v3/`, etc.

---

## Security Considerations

### 1. Input Validation

All inputs are validated via Pydantic schemas. Invalid requests return `400` or `422` errors.

### 2. File Upload Safety

- Max file size: 50 MB
- Allowed content types: `text/plain`, `application/json`
- Files are processed in isolated containers

### 3. Rate Limiting

Configure in `config/settings.yaml`:

```yaml
celery:
  task_annotations:
    '*':
      rate_limit: '300/m'  # Adjust as needed
```

---

## Next Steps

- **CLI Usage**: See [CLI Usage Guide](./CLI_USAGE.md)
- **Configuration**: See [README.md](./README.md#configuration)
- **Examples**: Check `/examples` directory for complete code samples
