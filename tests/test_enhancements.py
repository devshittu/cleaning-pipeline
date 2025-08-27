# tests/test_enhancements.py
"""
Unit tests for the enhanced data ingestion and preprocessing microservice.
"""

# Import ConfigManager to mock settings
from src.utils.config_manager import ConfigManager
from src.storage.backends import (
    StorageBackendFactory,
    JSONLStorageBackend,
    ElasticsearchStorageBackend,
    PostgreSQLStorageBackend,
    StorageBackend
)
from src.core.processor import TextPreprocessor
from src.schemas.data_models import ArticleInput, PreprocessSingleResponse, PreprocessSingleRequest
import pytest
from datetime import date, datetime
from pydantic import ValidationError, HttpUrl
from typing import Dict, Any, List
import json
import os
import shutil
from unittest.mock import patch, MagicMock

# Adjust sys.path to allow imports from src
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Mock the settings for consistent testing environment

@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    with patch('src.utils.config_manager.ConfigManager.get_settings') as mock_get_settings:
        mock_settings_obj = MagicMock()

        # Default ingestion_service settings
        mock_settings_obj.ingestion_service.model_name = "en_core_web_trf"
        mock_settings_obj.ingestion_service.model_cache_dir = "/tmp/spacy_cache"
        mock_settings_obj.ingestion_service.dateparser_languages = ["en"]

        # Default celery settings (not directly used by preprocessor tests, but for completeness)
        mock_settings_obj.celery.broker_url = "redis://localhost:6379/0"
        mock_settings_obj.celery.result_backend = "redis://localhost:6379/0"
        mock_settings_obj.celery.task_acks_late = True
        mock_settings_obj.celery.worker_prefetch_multiplier = 1
        mock_settings_obj.celery.worker_concurrency = 4
        mock_settings_obj.celery.task_annotations = {
            '*': {'rate_limit': '300/m'}}

        # Default storage settings
        mock_settings_obj.storage.backend = "jsonl"
        mock_settings_obj.storage.jsonl.output_path = "/tmp/processed_articles_test.jsonl"
        mock_settings_obj.storage.elasticsearch.host = "localhost"
        mock_settings_obj.storage.elasticsearch.port = 9200
        mock_settings_obj.storage.elasticsearch.index_name = "test_news_articles"
        mock_settings_obj.storage.elasticsearch.scheme = "http"
        mock_settings_obj.storage.elasticsearch.api_key = None
        mock_settings_obj.storage.postgresql.host = "localhost"
        mock_settings_obj.storage.postgresql.port = 5432
        mock_settings_obj.storage.postgresql.dbname = "testdb"
        mock_settings_obj.storage.postgresql.user = "testuser"
        mock_settings_obj.storage.postgresql.password = "testpassword"
        mock_settings_obj.storage.postgresql.table_name = "test_processed_articles"

        mock_get_settings.return_value = mock_settings_obj
        yield

# Fixture for TextPreprocessor singleton


@pytest.fixture(scope="session")
def preprocessor_instance():
    # Force re-initialization of the singleton with mocked settings
    TextPreprocessor._instance = None
    preprocessor = TextPreprocessor()
    # Ensure spacy model is mocked for tests not requiring actual NLP processing
    # For actual NLP tests, ensure 'en_core_web_trf' is downloaded in test environment or mock spacy.load
    with patch.object(preprocessor, 'nlp', autospec=True) as mock_nlp:
        # Mocking doc and entities for specific return values
        mock_doc = MagicMock()
        mock_nlp.return_value = mock_doc
        mock_doc.ents = []  # Default to no entities unless overridden
        yield preprocessor

# Fixture for a temporary JSONL output file for storage tests


@pytest.fixture
def temp_jsonl_output_file():
    temp_dir = "/tmp/test_storage"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, "test_output.jsonl")
    yield file_path
    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

### Test Schema Enhancements (data_models.py) ###


def test_article_input_schema_enrichment():
    """Test if ArticleInput accepts new optional fields."""
    data = {
        "document_id": "test-doc-123",
        "text": "This is a sample article text.",
        "title": "Sample Article",
        "categories": ["News", "Tech"],
        "tags": ["AI", "Machine Learning"],
        "geographical_data": {"city": "London", "country": "UK"},
        "embargo_date": "2025-08-01",
        "media_asset_urls": ["http://example.com/image.jpg", "https://example.com/video.mp4"],
        "sentiment": "neutral",
        "word_count": 10
    }
    article = ArticleInput(**data)
    assert article.document_id == "test-doc-123"
    assert "News" in article.categories
    assert article.geographical_data["country"] == "UK"
    assert article.embargo_date == date(2025, 8, 1)
    assert len(article.media_asset_urls) == 2
    assert isinstance(article.media_asset_urls[0], HttpUrl)
    assert article.sentiment == "neutral"
    assert article.word_count == 10


def test_article_input_missing_required_fields():
    """Test ArticleInput raises ValidationError for missing required fields."""
    with pytest.raises(ValidationError):
        ArticleInput(text="Missing ID")  # document_id is required
    with pytest.raises(ValidationError):
        ArticleInput(document_id="123")  # text is required


def test_preprocess_single_response_language_field():
    """Test PreprocessSingleResponse includes the new language field."""
    response_data = {
        "document_id": "resp-doc-456",
        "version": "1.0",
        "original_text": "Hello world.",
        "cleaned_text": "Hello world.",
        "language": "en"
    }
    response = PreprocessSingleResponse(**response_data)
    assert response.document_id == "resp-doc-456"
    assert response.language == "en"
    # Optional fields remain None if not provided
    assert response.cleaned_title is None


def test_preprocess_single_request_validation():
    """Test PreprocessSingleRequest wraps ArticleInput correctly."""
    article_data = {
        "document_id": "req-doc-789",
        "text": "Another article."
    }
    request = PreprocessSingleRequest(article=article_data)
    assert request.article.document_id == "req-doc-789"
    assert request.article.text == "Another article."


### Test Processor Enhancements (processor.py) ###

# Test Language Detection
@patch('src.core.processor.detect')
def test_language_detection_success(mock_detect, preprocessor_instance):
    mock_detect.return_value = "en"
    text = "This is an English text."
    detected_lang = preprocessor_instance._detect_language(text)
    assert detected_lang == "en"
    mock_detect.assert_called_once_with(text)


@patch('src.core.processor.detect')
def test_language_detection_failure(mock_detect, preprocessor_instance):
    from langdetect import LangDetectException
    mock_detect.side_effect = LangDetectException("No features in text")
    text = "..."
    detected_lang = preprocessor_instance._detect_language(text)
    assert detected_lang == "unknown"
    mock_detect.assert_called_once_with(text)

# Test Encoding Normalization


def test_encoding_normalization(preprocessor_instance):
    dirty_text = "This text has smart quotes—“like this” and ‘this’—and an euro symbol €."
    # ftfy should fix the smart quotes to straight quotes and handle euro
    fixed_text = preprocessor_instance._normalize_encoding(dirty_text)
    assert '"' in fixed_text
    assert "'" in fixed_text
    assert '€' in fixed_text  # ftfy preserves valid unicode, and ensures correct encoding
    # Should not be affected by _normalize_encoding, but by _normalize_punctuation
    assert '—' not in fixed_text

# Test Punctuation Normalization


def test_punctuation_normalization(preprocessor_instance):
    text_with_smart_punctuation = "“Hello,” he said—‘it’s great’."
    normalized_text = preprocessor_instance._normalize_punctuation(
        text_with_smart_punctuation)
    assert normalized_text == '"Hello," he said--\'it\'s great\'.'

# Test Typographical Error Correction


@patch.object(SpellChecker, 'correction', side_effect=lambda x: {'teh': 'the', 'appel': 'apple'}.get(x.lower(), x))
def test_typo_correction(mock_correction, preprocessor_instance):
    text_with_typos = "Teh quick brown fox ate an appel."
    corrected_text = preprocessor_instance._correct_typos(text_with_typos)
    assert corrected_text == "The quick brown fox ate an apple."
    assert mock_correction.call_count == 7  # For each word

# Test Unit and Currency Standardization


def test_unit_currency_standardization(preprocessor_instance):
    text = "The price is $10.50. It's 5m long and weighs 2kg. Also £20 and 3km."
    standardized_text = preprocessor_instance._standardize_units_currencies(
        text)
    assert "USD 10.50" in standardized_text
    assert "5 meters" in standardized_text
    assert "2 kilograms" in standardized_text
    assert "GBP 20" in standardized_text
    assert "3 kilometers" in standardized_text
    # Ensure symbols are replaced if covered by regex
    assert "$" not in standardized_text

# Test `clean_text` integrating all normalization steps


def test_integrated_clean_text(preprocessor_instance):
    html_text = "<p>Hello &amp; world. It's 5cm and costs $5.</p>"
    cleaned = preprocessor_instance.clean_text(html_text)
    # depends on exact punctuation handling and double space
    assert "Hello & world. Its 5 centimeters and costs USD 5." in cleaned or "Hello  world. Its 5 centimeters and costs USD 5." in cleaned
    assert "<p>" not in cleaned
    assert "USD 5" in cleaned
    assert "5 centimeters" in cleaned
    # depends on spelling correction context
    assert "It's" in cleaned or "Its" in cleaned

# Test Metadata Inference


@patch.object(TextPreprocessor, 'tag_entities')
@patch.object(TextPreprocessor, 'extract_temporal_metadata')
@patch.object(TextPreprocessor, '_detect_language', return_value="en")
@patch.object(TextPreprocessor, '_infer_author_from_text')
def test_infer_missing_publication_date_and_author(
    mock_infer_author, mock_detect_language, mock_extract_temporal_metadata, mock_tag_entities, preprocessor_instance
):
    # Mock spaCy entities for date and person inference
    mock_tag_entities.return_value = [
        MagicMock(text="January 1, 2023", type="DATE"),
        MagicMock(text="John Doe", type="PERSON")
    ]
    mock_extract_temporal_metadata.return_value = "2023-01-01"
    mock_infer_author.return_value = "John Doe"

    text = "On January 1, 2023, by John Doe, an important announcement was made."

    # Test case 1: No publication_date or author provided
    processed = preprocessor_instance.preprocess(text=text)
    assert processed["temporal_metadata"] == "2023-01-01"
    assert processed["cleaned_author"] == "John Doe"
    assert processed["language"] == "en"

    # Test case 2: Only publication_date provided, author missing
    processed = preprocessor_instance.preprocess(
        text=text, publication_date=date(2022, 12, 25))
    # Explicit date should be used
    assert processed["temporal_metadata"] == "2022-12-25"
    assert processed["cleaned_author"] == "John Doe"

    # Test case 3: Only author provided, publication_date missing
    processed = preprocessor_instance.preprocess(
        text=text, author="Jane Smith")
    assert processed["temporal_metadata"] == "2023-01-01"
    # Explicit author should be used
    assert processed["cleaned_author"] == "Jane Smith"


### Test Storage Options ###

@pytest.fixture
def mock_storage_settings():
    """Fixture to reset and provide mock settings for storage tests."""
    with patch('src.utils.config_manager.ConfigManager.get_settings') as mock_get_settings:
        mock_settings_obj = MagicMock()
        mock_settings_obj.storage.backend = "jsonl"  # Default
        mock_settings_obj.storage.jsonl.output_path = "/tmp/processed_articles_test.jsonl"
        mock_settings_obj.storage.elasticsearch.host = "localhost"
        mock_settings_obj.storage.elasticsearch.port = 9200
        mock_settings_obj.storage.elasticsearch.index_name = "test_news_articles"
        mock_settings_obj.storage.elasticsearch.scheme = "http"
        mock_settings_obj.storage.elasticsearch.api_key = None
        mock_settings_obj.storage.postgresql.host = "localhost"
        mock_settings_obj.storage.postgresql.port = 5432
        mock_settings_obj.storage.postgresql.dbname = "testdb"
        mock_settings_obj.storage.postgresql.user = "testuser"
        mock_settings_obj.storage.postgresql.password = "testpassword"
        mock_settings_obj.storage.postgresql.table_name = "test_processed_articles"
        mock_get_settings.return_value = mock_settings_obj
        yield mock_settings_obj


def _create_sample_response(doc_id: str) -> PreprocessSingleResponse:
    """Helper to create a sample PreprocessSingleResponse."""
    return PreprocessSingleResponse(
        document_id=doc_id,
        version="1.0",
        original_text=f"Original text for {doc_id}",
        cleaned_text=f"Cleaned text for {doc_id}",
        cleaned_title=f"Title for {doc_id}",
        cleaned_excerpt=None,
        cleaned_author="Test Author",
        temporal_metadata=date.today().isoformat(),
        entities=[],
        language="en"
    )


def test_jsonl_storage_backend_save(temp_jsonl_output_file, mock_storage_settings):
    mock_storage_settings.storage.backend = "jsonl"
    mock_storage_settings.storage.jsonl.output_path = temp_jsonl_output_file

    backend = StorageBackendFactory.get_backend()
    assert isinstance(backend, JSONLStorageBackend)

    sample_response = _create_sample_response("doc-jsonl-1")
    backend.save(sample_response)

    with open(temp_jsonl_output_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["document_id"] == "doc-jsonl-1"
        assert data["language"] == "en"


def test_jsonl_storage_backend_save_batch(temp_jsonl_output_file, mock_storage_settings):
    mock_storage_settings.storage.backend = "jsonl"
    mock_storage_settings.storage.jsonl.output_path = temp_jsonl_output_file

    backend = StorageBackendFactory.get_backend()
    assert isinstance(backend, JSONLStorageBackend)

    sample_responses = [_create_sample_response(
        f"doc-jsonl-batch-{i}") for i in range(3)]
    backend.save_batch(sample_responses)

    with open(temp_jsonl_output_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 3
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["document_id"] == f"doc-jsonl-batch-{i}"


@patch('src.storage.backends.Elasticsearch')
def test_elasticsearch_storage_backend(MockElasticsearch, mock_storage_settings):
    mock_storage_settings.storage.backend = "elasticsearch"

    mock_es_instance = MockElasticsearch.return_value
    # Index does not exist initially
    mock_es_instance.indices.exists.return_value = False

    backend = StorageBackendFactory.get_backend()
    assert isinstance(backend, ElasticsearchStorageBackend)
    MockElasticsearch.assert_called_once()
    mock_es_instance.indices.create.assert_called_once_with(
        index="test_news_articles")

    sample_response = _create_sample_response("doc-es-1")
    backend.save(sample_response)
    mock_es_instance.index.assert_called_once_with(
        index="test_news_articles", id="doc-es-1", document=sample_response.model_dump(mode='json')
    )

    mock_es_instance.index.reset_mock()
    sample_responses = [_create_sample_response(
        f"doc-es-batch-{i}") for i in range(2)]
    with patch('src.storage.backends.bulk') as mock_bulk:
        backend.save_batch(sample_responses)
        mock_bulk.assert_called_once()
        args, kwargs = mock_bulk.call_args
        assert args[0] == mock_es_instance  # First arg is the ES client
        assert len(list(args[1])) == 2  # Second arg is the list of actions


@patch('src.storage.backends.psycopg2')
def test_postgresql_storage_backend(MockPsycopg2, mock_storage_settings):
    mock_storage_settings.storage.backend = "postgresql"

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    MockPsycopg2.connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    backend = StorageBackendFactory.get_backend()
    assert isinstance(backend, PostgreSQLStorageBackend)
    MockPsycopg2.connect.assert_called_once()
    mock_cursor.execute.assert_called_once()  # For create table if not exists
    mock_conn.commit.assert_called_once()

    sample_response = _create_sample_response("doc-pg-1")
    backend.save(sample_response)
    assert mock_cursor.execute.call_count == 2  # One for create table, one for save
    # Check if the insert query was called with correct data
    args, _ = mock_cursor.execute.call_args_list[1]
    assert "INSERT INTO test_processed_articles" in args[0]
    assert "doc-pg-1" in args[1]
    mock_conn.commit.assert_called_once()  # Only one commit for single save

    mock_cursor.reset_mock()
    mock_conn.reset_mock()

    sample_responses = [_create_sample_response(
        f"doc-pg-batch-{i}") for i in range(2)]
    backend.save_batch(sample_responses)
    mock_cursor.executemany.assert_called_once()
    mock_conn.commit.assert_called_once()
    args, _ = mock_cursor.executemany.call_args
    assert "INSERT INTO test_processed_articles" in args[0]
    assert len(args[1]) == 2  # List of two tuples for batch insert


def test_storage_backend_factory_unsupported_type(mock_storage_settings):
    mock_storage_settings.storage.backend = "unsupported"
    with pytest.raises(ValueError, match="Unsupported storage backend type: unsupported"):
        StorageBackendFactory.get_backend()
