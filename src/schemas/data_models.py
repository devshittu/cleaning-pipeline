# src/schemas/data_models.py
"""
src/schemas/data_models.py

Defines Pydantic models for API request and response payloads.

UPDATED: Added support for custom cleaning configuration via API/CLI.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, HttpUrl
from datetime import date

# --- Common Models ---


class TextSpan(BaseModel):
    """Represents a span of text within a larger string."""
    text: str = Field(..., description="The detected text span.")
    start_char: int = Field(..., description="Starting character index.")
    end_char: int = Field(...,
                          description="Ending character index (exclusive).")


class Entity(BaseModel):
    """Represents a named entity recognized in text."""
    text: str = Field(..., description="The detected entity text.")
    type: str = Field(...,
                      description="Entity type (e.g., PERSON, ORG, GPE, LOC, DATE).")
    start_char: int = Field(..., description="Starting character index.")
    end_char: int = Field(...,
                          description="Ending character index (exclusive).")


class CleaningConfigOverride(BaseModel):
    """
    Optional cleaning configuration override for per-request customization.
    Any field not specified will use the default from settings.yaml.
    """
    remove_html_tags: Optional[bool] = Field(
        None, description="Remove HTML tags.")
    normalize_whitespace: Optional[bool] = Field(
        None, description="Normalize whitespace.")
    fix_encoding: Optional[bool] = Field(
        None, description="Fix encoding issues.")
    normalize_punctuation: Optional[bool] = Field(
        None, description="Normalize punctuation.")
    standardize_units: Optional[bool] = Field(
        None, description="Standardize units.")
    standardize_currency: Optional[bool] = Field(
        None, description="Standardize currency.")
    enable_typo_correction: Optional[bool] = Field(
        None, description="Enable typo correction.")

    # Typo correction sub-settings
    typo_min_length: Optional[int] = Field(
        None, description="Min word length for typo check.")
    typo_max_length: Optional[int] = Field(
        None, description="Max word length for typo check.")
    typo_use_ner: Optional[bool] = Field(
        None, description="Use NER to protect proper nouns.")
    typo_confidence: Optional[float] = Field(
        None, description="Typo correction confidence (0.0-1.0).")


class ArticleInput(BaseModel):
    """
    Input model for an article with optional cleaning configuration override.
    """
    document_id: str = Field(...,
                             description="Unique identifier for the document.")
    text: str = Field(..., description="Raw, unstructured text content.")
    title: Optional[str] = Field(None, description="Article title.")
    excerpt: Optional[str] = Field(
        None, description="Brief summary or excerpt.")
    author: Optional[str] = Field(None, description="Author's name.")
    publication_date: Optional[date] = Field(
        None, description="Publication date.")
    revision_date: Optional[date] = Field(
        None, description="Last revision date.")
    source_url: Optional[HttpUrl] = Field(None, description="Source URL.")
    categories: Optional[List[str]] = Field(None, description="Categories.")
    tags: Optional[List[str]] = Field(None, description="Tags.")
    media_asset_urls: Optional[List[HttpUrl]] = Field(
        None, description="Media URLs.")
    geographical_data: Optional[Dict[str, Any]] = Field(
        None, description="Geographical metadata.")
    embargo_date: Optional[date] = Field(None, description="Embargo date.")
    sentiment: Optional[str] = Field(None, description="Sentiment.")
    word_count: Optional[int] = Field(None, description="Word count.")
    publisher: Optional[str] = Field(None, description="Publisher.")
    additional_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata.")


class PreprocessSingleRequest(BaseModel):
    """Request model for processing a single article."""
    article: ArticleInput = Field(..., description="Article to process.")
    persist_to_backends: Optional[List[str]] = Field(
        None, description="Storage backends to persist to (e.g., ['jsonl', 'postgresql']).")
    cleaning_config: Optional[CleaningConfigOverride] = Field(
        None, description="Optional cleaning configuration override for this request.")


class PreprocessSingleResponse(BaseModel):
    """Response model for a single preprocessed article."""
    document_id: str = Field(..., description="Document unique identifier.")
    version: str = Field("1.0", description="Schema version.")
    original_text: str = Field(..., description="Original input text.")
    cleaned_text: str = Field(..., description="Cleaned and normalized text.")

    # Cleaned metadata fields
    cleaned_title: Optional[str] = Field(None, description="Cleaned title.")
    cleaned_excerpt: Optional[str] = Field(
        None, description="Cleaned excerpt.")
    cleaned_author: Optional[str] = Field(None, description="Cleaned author.")
    cleaned_publication_date: Optional[date] = Field(
        None, description="Cleaned publication date.")
    cleaned_revision_date: Optional[date] = Field(
        None, description="Cleaned revision date.")
    cleaned_source_url: Optional[HttpUrl] = Field(
        None, description="Cleaned source URL.")
    cleaned_categories: Optional[List[str]] = Field(
        None, description="Cleaned categories.")
    cleaned_tags: Optional[List[str]] = Field(
        None, description="Cleaned tags.")
    cleaned_media_asset_urls: Optional[List[HttpUrl]] = Field(
        None, description="Cleaned media URLs.")
    cleaned_geographical_data: Optional[Dict[str, Any]] = Field(
        None, description="Cleaned geographical data.")
    cleaned_embargo_date: Optional[date] = Field(
        None, description="Cleaned embargo date.")
    cleaned_sentiment: Optional[str] = Field(
        None, description="Cleaned sentiment.")
    cleaned_word_count: Optional[int] = Field(
        None, description="Cleaned/computed word count.")
    cleaned_publisher: Optional[str] = Field(
        None, description="Cleaned publisher.")

    temporal_metadata: Optional[str] = Field(
        None, description="Normalized date (YYYY-MM-DD).")
    entities: List[Entity] = Field(
        default_factory=list, description="Tagged entities.")
    cleaned_additional_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Cleaned additional metadata.")


class PreprocessBatchRequest(BaseModel):
    """Request model for batch processing."""
    articles: List[ArticleInput] = Field(...,
                                         description="List of articles to process.")
    persist_to_backends: Optional[List[str]] = Field(
        None, description="Storage backends.")
    cleaning_config: Optional[CleaningConfigOverride] = Field(
        None, description="Optional cleaning configuration override for entire batch.")


class PreprocessBatchResponse(BaseModel):
    """Response model for batch processing."""
    processed_articles: List[PreprocessSingleResponse] = Field(
        ..., description="Processed articles.")


class PreprocessFileResult(BaseModel):
    """Model for CLI batch processing output."""
    document_id: str = Field(..., description="Document unique identifier.")
    version: str = Field("1.0", description="Schema version.")
    processed_data: PreprocessSingleResponse

# src/schemas/data_models.py
