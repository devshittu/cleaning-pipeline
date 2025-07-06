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
from datetime import date
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
        cleaned_text = re.sub(r'[^\w\s.,?!-]', '', cleaned_text)
        return cleaned_text

    def extract_temporal_metadata(self, text: str, reference_date: Optional[date] = None) -> Optional[str]:
        """
        Extracts and normalizes temporal metadata (dates) from the text, using
        a reference date to resolve ambiguity.

        Args:
            text: The text to parse.
            reference_date: The date to use as a context for relative expressions
                            (e.g., 'yesterday' becomes a concrete date relative to this date).

        Returns:
            The normalized date in ISO 8601 format (YYYY-MM-DD), or None if not found.
        """
        settings = ConfigManager.get_settings()
        languages = settings.ingestion_service.dateparser_languages

        try:
            date_obj = dateparser.parse(text, languages=languages, settings={
                                        'RELATIVE_BASE': reference_date})
            if date_obj:
                return date_obj.strftime('%Y-%m-DD')
            return None
        except Exception as e:
            logger.warning(
                f"Failed to parse date from text: '{text[:50]}...'. Error: {e}")
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

    def preprocess(self, text: str, reference_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Performs the complete preprocessing pipeline on a single text string.

        Args:
            text: The raw, unstructured text.
            reference_date: Optional date to use as a context for relative temporal expressions.

        Returns:
            A dictionary with the cleaned text, temporal metadata, and tagged entities.
        """
        if not isinstance(text, str) or not text.strip():
            logger.warning(
                "Received empty or non-string input for preprocessing.")
            return {
                "original_text": text,
                "cleaned_text": "",
                "temporal_metadata": None,
                "entities": []
            }

        logger.info(f"Starting preprocessing for text of length {len(text)}.")

        # 1. Text Cleaning
        cleaned_text = self.clean_text(text)

        # 2. Temporal Metadata Extraction with context
        temporal_metadata = self.extract_temporal_metadata(
            cleaned_text, reference_date=reference_date)

        # 3. Basic Entity Tagging
        entities = self.tag_entities(cleaned_text)

        processed_data = {
            "original_text": text,
            "cleaned_text": cleaned_text,
            "temporal_metadata": temporal_metadata,
            "entities": entities
        }

        logger.info(
            f"Preprocessing complete. Found {len(entities)} entities and date: {temporal_metadata}.")

        return processed_data


# Ensure the singleton instance is created on import
# This is a safe way to handle singleton initialization in a module
preprocessor = TextPreprocessor()
