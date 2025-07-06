"""
schemas/data_models.py

Defines Pydantic models for API request and response payloads,
ensuring data validation and clear documentation.
"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
import uuid
from datetime import date
from enum import Enum

# --- Common Models ---


class TextSpan(BaseModel):
    """Represents a span of text within a larger string."""
    text: str = Field(..., description="The detected text span.")
    start_char: int = Field(...,
                            description="Starting character index in the original text.")
    end_char: int = Field(
        ..., description="Ending character index in the original text (exclusive).")


class Entity(BaseModel):
    """Represents a named entity recognized in text."""
    text: str = Field(..., description="The detected entity text.")
    type: str = Field(...,
                      description="The type of the entity (e.g., PERSON, ORG, LOC, DATE).")
    start_char: int = Field(
        ..., description="Starting character index of the entity in the original text.")
    end_char: int = Field(
        ..., description="Ending character index of the entity in the original text (exclusive).")


class ArticleInput(BaseModel):
    """
    A comprehensive model for an input article or block of text, designed
    for robustness and traceability.
    """
    document_id: str = Field(
        ..., description="A unique identifier for the document, provided by the upstream service for traceability.")
    text: str = Field(...,
                      description="The raw, unstructured text content of the article.")
    title: Optional[str] = Field(None, description="The title of the article.")
    excerpt: Optional[str] = Field(
        None, description="A brief summary or excerpt of the article.")
    author: Optional[str] = Field(None, description="The author's name.")
    publication_date: Optional[date] = Field(
        None, description="The publication date of the article. Crucial for resolving relative temporal expressions.")
    revision_date: Optional[date] = Field(
        None, description="The last revision date of the article.")
    source_url: Optional[HttpUrl] = Field(
        None, description="The URL from which the article was retrieved.")
    # Add any other fields here in the future without breaking the API contract.

# --- Ingestion Service Models ---
# The single and batch request models now wrap the ArticleInput model.


class PreprocessSingleRequest(BaseModel):
    """Request model for processing a single text input as a structured article."""
    article: ArticleInput = Field(
        ..., description="The structured input containing the text and its metadata.")


class PreprocessSingleResponse(BaseModel):
    """
    Response model for a single preprocessed text.
    Includes a unique document ID and a schema version for traceability and versioning.
    """
    document_id: str = Field(
        ..., description="A unique identifier for the processed document, carried from the input payload.")
    version: str = Field("1.0", description="Schema version for this output.")
    original_text: str = Field(..., description="The original input text.")
    cleaned_text: str = Field(...,
                              description="The cleaned and normalized text.")
    temporal_metadata: Optional[str] = Field(
        None, description="The normalized date in ISO 8601 format (YYYY-MM-DD), if found.")
    entities: List[Entity] = Field(
        default_factory=list, description="A list of tagged entities.")


class PreprocessBatchRequest(BaseModel):
    """Request model for processing a list of structured article inputs (batch)."""
    articles: List[ArticleInput] = Field(
        ..., description="A list of structured article inputs to process in batch.")


class PreprocessBatchResponse(BaseModel):
    """Response model for the result of a batch processing job."""
    processed_articles: List[PreprocessSingleResponse] = Field(
        ..., description="A list of processed outputs for each article in the batch.")


class PreprocessFileResult(BaseModel):
    """
    Model for a single line in the output JSONL file.
    Includes the unique document ID to ensure traceability in offline processing.
    """
    document_id: str = Field(...,
                             description="A unique identifier for the processed document.")
    version: str = Field("1.0", description="Schema version for this output.")
    original_text: str
    processed_data: PreprocessSingleResponse
