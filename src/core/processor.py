"""
src/core/processor.py

Contains the core business logic for text cleaning, temporal metadata
extraction, and basic entity tagging.
"""

from src.utils.config_manager import ConfigManager, JsonlStorageConfig, ElasticsearchStorageConfig, PostgreSQLStorageConfig
from src.schemas.data_models import PreprocessSingleResponse
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
import json
import atexit
import logging
import re
import spacy
import ftfy
from typing import Optional, List, Dict, Any, Union
import dateparser
from src.schemas.data_models import Entity
from datetime import date, datetime, timedelta
import os
from langdetect import detect, DetectorFactory, LangDetectException
from pydantic import HttpUrl
from pydantic_core import Url
import string

# Ensure reproducibility for langdetect
DetectorFactory.seed = 0

logger = logging.getLogger("ingestion_service")


class TextPreprocessor:
    """
    A class for ingesting, cleaning, and preprocessing unstructured text.
    It uses spaCy for NER and dateparser for temporal metadata.
    This class is now designed to be instantiated directly (no longer a singleton).
    """

    def __init__(self):
        """
        Initializes the TextPreprocessor and loads the spaCy model.
        This constructor is now called whenever a new TextPreprocessor instance is created.
        """
        self.nlp = None
        self.settings = ConfigManager.get_settings()
        self._load_models()
        # Note: atexit.register(self.close) has been removed here.
        # This is now handled by the Celery worker process lifecycle for a more robust solution.

    def _load_models(self):
        """
        Loads the spaCy model for NER.
        The spaCy model is expected to be pre-installed in the Docker image.
        """
        try:
            model_name = self.settings.ingestion_service.model_name
            cache_dir = self.settings.ingestion_service.model_cache_dir
            logger.info(
                f"Loading spaCy model '{model_name}' with cache directory: {cache_dir}...")

            os.environ["SPACY_DATA"] = cache_dir

            if self.settings.general.gpu_enabled:
                try:
                    spacy.require_gpu()
                    logger.info("SpaCy detected and is attempting to use GPU.")
                except Exception as e:
                    logger.warning(
                        f"SpaCy GPU not available or failed to require: {e}. Falling back to CPU if necessary.", exc_info=True)
            else:
                logger.info("GPU is disabled in settings. SpaCy will use CPU.")

            self.nlp = spacy.load(model_name)
            logger.info(f"SpaCy model '{model_name}' loaded successfully.")

        except Exception as e:
            logger.critical(f"Failed to load spaCy model: {e}", exc_info=True)
            raise RuntimeError(
                f"Failed to load spaCy model. Ensure it is pre-installed in the Docker image. Error: {e}")

    def close(self):
        """
        Frees up any resources. This is particularly important for models
        loaded with atexit, in case of graceful shutdown.
        """
        if self.nlp:
            logger.info("Closing spaCy model...")
            self.nlp = None

    def _standardize_units_and_currency(self, text: str) -> str:
        """
        Standardizes common unit and currency representations to a consistent format.
        This is a basic implementation and can be extended with more complex rules,
        lookup tables, or a dedicated library for robust unit/currency parsing.
        """
        logger.debug("Starting unit and currency standardization.")
        text = re.sub(r'\$\s*(\d+(\.\d{1,2})?)',
                      r'USD \1', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*€', r'\1 EUR', text, flags=re.IGNORECASE)
        text = re.sub(r'£\s*(\d+(\.\d{1,2})?)',
                      r'GBP \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:usd|us dollars?)\b',
                      'USD', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:eur|euros?)\b', 'EUR', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:gbp|pounds?sterling)\b',
                      'GBP', text, flags=re.IGNORECASE)

        text = re.sub(r'(\d+(\.\d+)?)\s*%', r'\1 percent',
                      text, flags=re.IGNORECASE)

        text = re.sub(r'(\d+)\s*m\b', r'\1 meters', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*km\b', r'\1 kilometers',
                      text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*kg\b', r'\1 kilograms',
                      text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*cm\b', r'\1 centimeters',
                      text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*ft\b', r'\1 feet', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*lbs\b', r'\1 pounds',
                      text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*mi\b', r'\1 miles', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*g\b', r'\1 grams', text, flags=re.IGNORECASE)
        logger.debug("Finished unit and currency standardization.")
        return text

    def clean_text(self, text: str) -> str:
        """
        Performs robust text cleaning and advanced normalization:
        1. HTML tag replacement with spaces to preserve word boundaries.
        2. Initial whitespace normalization.
        3. Encoding Normalization (ftfy): Handles various character encodings and garbled text.
        4. Unit and Currency Standardization: Converts varied unit/currency representations to standard formats.
        5. Punctuation Normalization: Standardizes and cleans up punctuation, removes non-printable characters.
        6. Final whitespace normalization.
        Args:
            text: The raw text string.
        Returns:
            The cleaned and normalized text.
        """
        logger.debug("Starting text cleaning process.")
        cleaned_text = re.sub(r'<.*?>', ' ', text)
        logger.debug("HTML tags removed.")

        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        logger.debug("Initial whitespace normalized.")

        cleaned_text = ftfy.fix_text(cleaned_text)
        logger.debug("Encoding normalized with ftfy.")

        cleaned_text = self._standardize_units_and_currency(cleaned_text)
        logger.debug("Units and currency standardized.")

        cleaned_text = re.sub(r'[\u2010-\u2015\u2212]', '-', cleaned_text)
        printable = set(string.printable)
        cleaned_text = ''.join(filter(lambda x: x in printable, cleaned_text))
        logger.debug("Punctuation and non-printable characters normalized.")

        cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
        cleaned_text = re.sub(r',{2,}', ',', cleaned_text)
        cleaned_text = re.sub(r'!{2,}', '!', cleaned_text)
        cleaned_text = re.sub(r'\?{2,}', '?', cleaned_text)
        cleaned_text = re.sub(r'-{2,}', '-', cleaned_text)
        logger.debug("Punctuation repetition removed.")

        cleaned_text = re.sub(r'([.,?!])(?=[a-zA-Z0-9])', r'\1 ', cleaned_text)
        logger.debug("Space after punctuation ensured.")

        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        logger.debug("Final whitespace normalized. Text cleaning finished.")

        return cleaned_text

    def _clean_field(self, field_value: Any) -> Any:
        """
        Recursively cleans various types of metadata fields.
        - Strings: Apply clean_text logic.
        - Lists of strings/HttpUrl: Clean each string/HttpUrl in the list.
        - Dictionaries: Clean string values within the dictionary.
        - HttpUrl, bool, int, date, datetime: Pass through unchanged.
        - None: Pass through unchanged.
        Args:
            field_value: The value of the metadata field (can be str, list, dict, HttpUrl, etc.).
        Returns:
            The cleaned value or None if the input was None or empty after cleaning.
        """
        logger.debug(f"Cleaning field of type: {type(field_value)}")
        if field_value is None:
            return None

        if isinstance(field_value, str):
            cleaned = self.clean_text(field_value)
            logger.debug(
                f"Cleaned string field: '{field_value[:20]}...' -> '{cleaned[:20]}...'")
            return cleaned if cleaned else None
        elif isinstance(field_value, list):
            cleaned_list = []
            for item in field_value:
                if isinstance(item, str):
                    cleaned_item = self.clean_text(item)
                    if cleaned_item:
                        cleaned_list.append(cleaned_item)
                elif isinstance(item, Url):
                    cleaned_list.append(item)
                else:
                    logger.warning(
                        f"Unsupported list item type in metadata cleaning: {type(item)}. Skipping.")
            logger.debug(
                f"Cleaned list field. Original length: {len(field_value) if field_value else 0}, Cleaned length: {len(cleaned_list)}")
            return cleaned_list if cleaned_list else None
        elif isinstance(field_value, dict):
            cleaned_dict = {}
            for key, value in field_value.items():
                if isinstance(value, str):
                    cleaned_value = self.clean_text(value)
                    if cleaned_value:
                        cleaned_dict[key] = cleaned_value
                else:
                    cleaned_dict[key] = value
            logger.debug(
                f"Cleaned dictionary field. Original keys: {list(field_value.keys())}, Cleaned keys: {list(cleaned_dict.keys())}")
            return cleaned_dict if cleaned_dict else None
        elif isinstance(field_value, Url):
            logger.debug("URL field - no cleaning applied.")
            return field_value
        elif isinstance(field_value, (bool, int, date, datetime)):
            logger.debug(
                f"Numeric/Date/Boolean field '{field_value}' - no cleaning applied.")
            return field_value
        else:
            logger.warning(
                f"Unsupported metadata field type for cleaning: {type(field_value)}. Passing through unchanged.")
            return field_value

    def _get_last_weekday(self, weekday_name: str, reference_date: datetime) -> Optional[date]:
        """
        Calculates the date of the most recent occurrence of a specific weekday
        prior to or on the reference_date.
        """
        logger.debug(
            f"Calculating last weekday for '{weekday_name}' relative to {reference_date}.")
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        weekday_name_lower = weekday_name.lower()

        if weekday_name_lower not in weekdays:
            logger.warning(f"Invalid weekday name provided: {weekday_name}")
            return None

        target_weekday = weekdays[weekday_name_lower]
        days_ago = (reference_date.weekday() - target_weekday + 7) % 7
        if days_ago == 0:
            days_ago = 7

        last_weekday_date = reference_date - timedelta(days=days_ago)
        logger.debug(f"Calculated last weekday as: {last_weekday_date.date()}")
        return last_weekday_date.date()

    def extract_temporal_metadata(self, text_to_parse: str, reference_date: Optional[date] = None) -> Optional[str]:
        """
        Extracts and normalizes temporal metadata (dates) from the text, using
        a reference date to resolve ambiguity.
        This function is now designed to receive a more specific date string (e.g., from an NER entity).
        Args:
            text_to_parse: The specific text string to parse for a date (e.g., "last Friday").
            reference_date: The date to use as a context for relative expressions
                            (e.g., 'yesterday' becomes a concrete date relative to this date).
                            Expected to be a datetime.date object.
        Returns:
            The normalized date in ISO 8601 format (YYYY-MM-DD), or None if not found.
        """
        settings = ConfigManager.get_settings()
        languages = settings.ingestion_service.dateparser_languages

        parsed_reference_date = None
        if reference_date:
            if isinstance(reference_date, date) and not isinstance(reference_date, datetime):
                parsed_reference_date = datetime(
                    reference_date.year, reference_date.month, reference_date.day)
            elif isinstance(reference_date, datetime):
                parsed_reference_date = reference_date
            else:
                logger.warning(
                    f"Unexpected type for reference_date: {type(reference_date)}. Expected datetime.date or datetime.datetime. Skipping as reference.")

        logger.debug(
            f"Attempting to parse date: '{text_to_parse}' with reference_date: {parsed_reference_date}")

        match = re.match(r'last\s+([a-zA-Z]+)', text_to_parse, re.IGNORECASE)
        if match and parsed_reference_date:
            weekday_name = match.group(1)
            calculated_date = self._get_last_weekday(
                weekday_name, parsed_reference_date)
            if calculated_date:
                logger.debug(
                    f"Custom logic for 'last {weekday_name}' returned: {calculated_date}")
                return calculated_date.strftime('%Y-%m-%d')
            else:
                logger.debug(
                    f"Custom logic for 'last {weekday_name}' failed to calculate date, falling back to dateparser.")

        try:
            date_obj = dateparser.parse(
                text_to_parse,
                languages=languages,
                settings={
                    'RELATIVE_BASE': parsed_reference_date,
                    'PREFER_DATES_FROM': 'past',
                    'STRICT_PARSING': True
                }
            )
            logger.debug(f"dateparser.parse returned: {date_obj}")
            if date_obj:
                return date_obj.strftime('%Y-%m-%d')
            logger.debug(f"Date parsing for '{text_to_parse}' returned None.")
            return None
        except Exception as e:
            logger.warning(
                f"Failed to parse date from text: '{text_to_parse[:50]}...'. Error: {e}", exc_info=True)
            return None

    def tag_entities(self, text: str) -> List[Entity]:
        """
        Performs Named Entity Recognition (NER) using spaCy's loaded model.
        Args:
            text: The cleaned text to tag for entities.
        Returns:
            A list of Entity Pydantic models, each representing a recognized named entity
            with its text, type (label), start character offset, and end character offset.
        """
        logger.debug("Starting entity tagging with spaCy.")
        if self.nlp is None:
            logger.error(
                "Attempted to tag entities, but spaCy model is not loaded. Returning empty list.")
            return []

        try:
            logger.debug(
                f"Calling self.nlp(text) for text length: {len(text)}. First 50 chars: '{text[:50]}'")
            doc = self.nlp(text)
            logger.debug("self.nlp(text) call completed.")
            entities = []
            for ent in doc.ents:
                entities.append(Entity(text=ent.text, type=ent.label_,
                                start_char=ent.start_char, end_char=ent.end_char))
            logger.debug(
                f"Finished entity tagging. Found {len(entities)} entities.")
            return entities
        except Exception as e:
            logger.error(
                f"Error during spaCy entity tagging: {e}", exc_info=True)
            return []

    def _detect_language(self, text: str) -> Optional[str]:
        """
        Detects the language of the provided text using the 'langdetect' library.
        Returns the ISO 639-1 language code (e.g., 'en', 'fr') or None if detection fails
        or if the text is too short for reliable detection.
        """
        logger.debug("Starting language detection.")
        if not text or len(text.strip()) < 10:
            logger.debug(
                "Text too short or empty for reliable language detection. Returning None.")
            return None
        try:
            detected_lang = detect(text)
            logger.debug(f"Detected language: {detected_lang}")
            return detected_lang
        except LangDetectException as e:
            logger.warning(
                f"Language detection failed: {e}. Text snippet: '{text[:100]}...'. Returning None.")
            return None

    def preprocess(self,
                   text: str,
                   document_id: str,
                   title: Optional[str] = None,
                   excerpt: Optional[str] = None,
                   author: Optional[str] = None,
                   publication_date: Optional[date] = None,
                   revision_date: Optional[date] = None,
                   source_url: Optional[HttpUrl] = None,
                   categories: Optional[List[str]] = None,
                   tags: Optional[List[str]] = None,
                   media_asset_urls: Optional[List[HttpUrl]] = None,
                   additional_metadata: Optional[Dict[str, Any]] = None
                   ) -> Dict[str, Any]:
        """
        Performs the complete preprocessing pipeline on a single text string
        and its associated metadata.
        The pipeline includes:
        - Text cleaning (encoding, HTML, whitespace, punctuation, unit/currency)
        - Metadata field cleaning
        - Dynamic field computation (word count, reading time, language detection)
        - Named Entity Recognition (NER)
        - Temporal metadata extraction

        Args:
            text: The main content text of the article.
            document_id: A unique identifier for the document.
            title: The title of the article.
            excerpt: A short summary or excerpt of the article.
            author: The author(s) of the article.
            publication_date: The original publication date of the article.
            revision_date: The last revision date of the article.
            source_url: The URL where the article was originally published.
            categories: A list of categories associated with the article.
            tags: A list of tags associated with the article.
            media_asset_urls: A list of URLs to media assets (images, videos) in the article.
            additional_metadata: A dictionary for any other arbitrary metadata.

        Returns:
            A dictionary containing the original and cleaned text, extracted entities,
            temporal metadata, and cleaned/computed additional metadata.
        """
        logger.info(
            f"Starting preprocessing pipeline for document_id={document_id}.")

        processed_data = {
            "document_id": document_id,
            "original_text": text,
            "entities": [],
            "temporal_metadata": None,
            "cleaned_additional_metadata": {}
        }

        logger.debug(
            f"Step 1: Cleaning main text for document_id={document_id}.")
        cleaned_text = self.clean_text(text)
        processed_data["cleaned_text"] = cleaned_text
        logger.debug(f"Step 1 complete for document_id={document_id}.")

        logger.debug(
            f"Step 2: Cleaning top-level metadata fields for document_id={document_id}.")
        processed_data["cleaned_title"] = self._clean_field(title)
        processed_data["cleaned_excerpt"] = self._clean_field(excerpt)
        processed_data["cleaned_author"] = self._clean_field(author)
        processed_data["cleaned_publication_date"] = self._clean_field(
            publication_date)
        processed_data["cleaned_revision_date"] = self._clean_field(
            revision_date)
        processed_data["cleaned_source_url"] = self._clean_field(source_url)
        processed_data["cleaned_categories"] = self._clean_field(categories)
        processed_data["cleaned_tags"] = self._clean_field(tags)
        processed_data["cleaned_media_asset_urls"] = self._clean_field(
            media_asset_urls)
        logger.debug(f"Step 2 complete for document_id={document_id}.")

        logger.debug(
            f"Step 3: Processing additional_metadata for document_id={document_id}.")
        if additional_metadata:
            for key, value in additional_metadata.items():
                cleaned_value = self._clean_field(value)
                if cleaned_value is not None:
                    processed_data["cleaned_additional_metadata"][f"cleaned_{key}"] = cleaned_value
        logger.debug(f"Step 3 complete for document_id={document_id}.")

        logger.debug(
            f"Step 4: Performing dynamic field computation for document_id={document_id}.")
        original_word_count = additional_metadata.get(
            'word_count') if additional_metadata else None
        if original_word_count is None and cleaned_text:
            word_count = len(cleaned_text.split())
            processed_data["cleaned_additional_metadata"]["cleaned_word_count"] = word_count
        elif original_word_count is not None:
            processed_data["cleaned_additional_metadata"]["cleaned_word_count"] = self._clean_field(
                original_word_count)

        original_reading_time = additional_metadata.get(
            'reading_time') if additional_metadata else None
        if original_reading_time is None and "cleaned_word_count" in processed_data["cleaned_additional_metadata"]:
            reading_time = max(1, round(
                processed_data["cleaned_additional_metadata"]["cleaned_word_count"] / 200))
            processed_data["cleaned_additional_metadata"]["cleaned_reading_time"] = reading_time
        elif original_reading_time is not None:
            processed_data["cleaned_additional_metadata"]["cleaned_reading_time"] = self._clean_field(
                original_reading_time)

        original_language = additional_metadata.get(
            'language') if additional_metadata else None
        if original_language is None and cleaned_text:
            language = self._detect_language(cleaned_text)
            if language:
                processed_data["cleaned_additional_metadata"]["cleaned_language"] = language
        elif original_language is not None:
            processed_data["cleaned_additional_metadata"]["cleaned_language"] = self._clean_field(
                original_language)
        logger.debug(f"Step 4 complete for document_id={document_id}.")

        logger.debug(
            f"Step 5: Starting basic entity tagging for document_id={document_id}.")
        entities = self.tag_entities(cleaned_text)
        processed_data["entities"] = entities
        logger.debug(
            f"Step 5 complete for document_id={document_id}. Found {len(entities)} entities.")

        logger.debug(
            f"Step 6: Starting temporal metadata extraction for document_id={document_id}.")
        date_text_for_parsing = None
        for ent in entities:
            if ent.type == "DATE":
                date_text_for_parsing = ent.text
                break
        if date_text_for_parsing is None:
            date_text_for_parsing = cleaned_text

        reference_date_for_temporal = publication_date if publication_date else date.today()
        temporal_metadata = self.extract_temporal_metadata(
            date_text_for_parsing, reference_date=reference_date_for_temporal)
        processed_data["temporal_metadata"] = temporal_metadata
        logger.debug(
            f"Step 6 complete for document_id={document_id}. Normalized date: {temporal_metadata}.")

        logger.info(
            f"Preprocessing complete for document_id={document_id}. Found {len(entities)} entities and normalized date: {temporal_metadata}.")
        return processed_data

# src/core/processor.py
