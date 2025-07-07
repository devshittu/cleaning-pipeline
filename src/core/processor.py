"""
core/processor.py

Contains the core business logic for text cleaning, temporal metadata
extraction, and basic entity tagging.
"""

import logging
import re
import spacy
from typing import Optional, List, Dict, Any
import dateparser
from src.utils.config_manager import ConfigManager
from src.schemas.data_models import Entity
from datetime import date, datetime, timedelta  # Import timedelta
import os

logger = logging.getLogger("ingestion_service")


class TextPreprocessor:
    """
    A class for ingesting, cleaning, and preprocessing unstructured text.
    It uses spaCy for NER and dateparser for temporal metadata.
    """

    _instance: Optional['TextPreprocessor'] = None

    def __new__(cls):
        """
        Implements the singleton pattern to ensure only one instance
        of the spaCy model is loaded.
        """
        if cls._instance is None:
            cls._instance = super(TextPreprocessor, cls).__new__(cls)
            cls._instance.nlp = None
            cls._instance.settings = ConfigManager.get_settings()
            cls._instance._load_models()
        return cls._instance

    def _load_models(self):
        """
        Loads the spaCy model for NER, using the cache directory specified in settings.
        The model is expected to be pre-installed in the Docker image.
        """
        try:
            model_name = self.settings.ingestion_service.model_name
            cache_dir = self.settings.ingestion_service.model_cache_dir
            logger.info(
                f"Loading spaCy model '{model_name}' with cache directory: {cache_dir}...")

            # Ensure the cache directory is in spaCy's model path
            os.environ["SPACY_DATA"] = cache_dir
            self.nlp = spacy.load(model_name)
            logger.info(f"SpaCy model '{model_name}' loaded successfully.")

        except Exception as e:
            logger.critical(
                f"Failed to load spaCy model '{model_name}': {e}", exc_info=True)
            raise RuntimeError(
                f"Failed to load spaCy model '{model_name}'. Ensure it is pre-installed in the Docker image.")

    def clean_text(self, text: str) -> str:
        """
        Performs robust text cleaning.

        Args:
            text: The raw text string.

        Returns:
            The cleaned and normalized text.
        """
        # Remove HTML tags
        cleaned_text = re.sub(r'<.*?>', '', text)
        # Normalize whitespace (remove extra spaces, tabs, newlines)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        # Handle special characters (simple approach)
        # Keep basic punctuation
        # This regex removes characters that are NOT word characters (\w), whitespace (\s),
        # or common punctuation (.,?!-). This is a more permissive approach.
        # If stricter cleaning is needed, this regex can be adjusted.
        cleaned_text = re.sub(r'[^\w\s.,?!-]', '', cleaned_text)
        return cleaned_text

    def clean_metadata_field(self, field_value: Optional[str]) -> Optional[str]:
        """
        Applies the same cleaning logic to optional metadata fields like title, excerpt, author.
        Ensures consistency in cleaning across all text-based fields.

        Args:
            field_value: The string value of the metadata field (e.g., title, excerpt).

        Returns:
            The cleaned string or None if the input was None or empty after cleaning.
        """
        if field_value is None:
            return None
        cleaned = self.clean_text(field_value)
        return cleaned if cleaned else None  # Return None if cleaned string is empty

    def _get_last_weekday(self, weekday_name: str, reference_date: datetime) -> Optional[date]:
        """
        Calculates the date of the most recent occurrence of a specific weekday
        prior to or on the reference_date.

        Args:
            weekday_name: The name of the weekday (e.g., "Monday", "Friday").
            reference_date: The datetime object to use as the reference point.

        Returns:
            A datetime.date object for the last occurrence of the weekday, or None if invalid.
        """
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        weekday_name_lower = weekday_name.lower()

        if weekday_name_lower not in weekdays:
            logger.warning(f"Invalid weekday name provided: {weekday_name}")
            return None

        target_weekday = weekdays[weekday_name_lower]
        # Calculate days to subtract to get to the last occurrence of the target weekday
        # (reference_date.weekday() - target_weekday + 7) % 7 gives the number of days
        # to go back to find the *most recent* target weekday, including today if it is that weekday.
        # If we want strictly *last* (not including today), we need to adjust.
        # For "last Friday" relative to a Friday, we want the Friday of the previous week.
        days_ago = (reference_date.weekday() - target_weekday + 7) % 7
        if days_ago == 0:  # If reference_date is the target weekday, go back a full week
            days_ago = 7

        last_weekday_date = reference_date - timedelta(days=days_ago)
        return last_weekday_date.date()  # Return as date object

    def extract_temporal_metadata(self, text_to_parse: str, reference_date: Optional[date] = None) -> Optional[str]:
        """
        Extracts and normalizes temporal metadata (dates) from the text, using
        a reference date to resolve ambiguity. This function is now designed to
        receive a more specific date string (e.g., from an NER entity).

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

        # Convert reference_date to datetime if it's a date object
        # This addresses the "RELATIVE_BASE" must be "datetime", not "date" error.
        parsed_reference_date = None
        if reference_date:
            if isinstance(reference_date, date) and not isinstance(reference_date, datetime):
                # Convert date to datetime, setting time to midnight
                parsed_reference_date = datetime(
                    reference_date.year, reference_date.month, reference_date.day)
            elif isinstance(reference_date, datetime):
                parsed_reference_date = reference_date
            else:
                logger.warning(
                    f"Unexpected type for reference_date: {type(reference_date)}. Expected datetime.date or datetime.datetime.")

        logger.debug(
            f"Attempting to parse date: '{text_to_parse}' with reference_date: {parsed_reference_date}")

        # --- Custom logic for "last [weekday]" pattern ---
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
                    f"Custom logic for 'last {weekday_name}' failed to calculate date.")

        # --- Fallback to dateparser for other patterns ---
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
                # Format toYYYY-MM-DD as requested
                return date_obj.strftime('%Y-%m-%d')
            logger.debug(f"Date parsing for '{text_to_parse}' returned None.")
            return None
        except Exception as e:
            logger.warning(
                f"Failed to parse date from text: '{text_to_parse[:50]}...'. Error: {e}", exc_info=True)
            return None

    def tag_entities(self, text: str) -> List[Entity]:
        """
        Performs basic Named Entity Recognition using spaCy's pre-trained model.

        Args:
            text: The cleaned text to tag.

        Returns:
            A list of Entity Pydantic models.

        Note on Entity Tagging Challenges:
        The current implementation uses a pre-trained transformer model. While powerful,
        NER models can be ambiguous (e.g., "Apple" as a company or fruit) and
        may not generalize well to domain-specific text or new languages. For a
        robust production system, consider fine-tuning this model on domain-specific
        data or implementing a custom NER component if needed.
        """
        if self.nlp is None:
            logger.error(
                "Attempted to tag entities, but spaCy model is not loaded.")
            return []

        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            # We are using `ent.start_char` and `ent.end_char` which are precise character spans
            entities.append(Entity(text=ent.text, type=ent.label_,
                            start_char=ent.start_char, end_char=ent.end_char))

        return entities

    def preprocess(self,
                   text: str,
                   title: Optional[str] = None,
                   excerpt: Optional[str] = None,
                   author: Optional[str] = None,
                   reference_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Performs the complete preprocessing pipeline on a single text string
        and its associated metadata.

        Args:
            text: The raw, unstructured text.
            title: Optional title of the article.
            excerpt: Optional excerpt/summary of the article.
            author: Optional author of the article.
            reference_date: Optional date to use as a context for relative temporal expressions.

        Returns:
            A dictionary with the cleaned text, temporal metadata, tagged entities,
            and cleaned metadata fields.
        """
        if not isinstance(text, str) or not text.strip():
            logger.warning(
                "Received empty or non-string input for preprocessing text content.")
            # Return cleaned metadata even if main text is empty
            return {
                "original_text": text,
                "cleaned_text": "",
                "cleaned_title": self.clean_metadata_field(title),
                "cleaned_excerpt": self.clean_metadata_field(excerpt),
                "cleaned_author": self.clean_metadata_field(author),
                "temporal_metadata": None,
                "entities": []
            }

        logger.info(f"Starting preprocessing for text of length {len(text)}.")

        # 1. Text Cleaning for main content
        cleaned_text = self.clean_text(text)

        # 2. Clean additional metadata fields
        cleaned_title = self.clean_metadata_field(title)
        cleaned_excerpt = self.clean_metadata_field(excerpt)
        cleaned_author = self.clean_metadata_field(author)

        # 3. Basic Entity Tagging (do this before temporal extraction for better context)
        entities = self.tag_entities(cleaned_text)

        # 4. Temporal Metadata Extraction with context
        # Prioritize parsing from a specific DATE entity if found, otherwise use the full cleaned text
        date_text_for_parsing = None
        for ent in entities:
            if ent.type == "DATE":
                date_text_for_parsing = ent.text
                break  # Take the first DATE entity found

        if date_text_for_parsing is None:
            # Fallback: if no DATE entity found, try parsing from the cleaned text (less precise)
            date_text_for_parsing = cleaned_text

        temporal_metadata = self.extract_temporal_metadata(
            date_text_for_parsing, reference_date=reference_date)

        processed_data = {
            "original_text": text,
            "cleaned_text": cleaned_text,
            "cleaned_title": cleaned_title,
            "cleaned_excerpt": cleaned_excerpt,
            "cleaned_author": cleaned_author,
            "temporal_metadata": temporal_metadata,
            "entities": entities
        }

        logger.info(
            f"Preprocessing complete. Found {len(entities)} entities and date: {temporal_metadata}.")

        return processed_data


# Ensure the singleton instance is created on import
# This is a safe way to handle singleton initialization in a module
preprocessor = TextPreprocessor()
