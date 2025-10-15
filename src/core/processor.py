"""
src/core/processor.py

Contains the core business logic for text cleaning, temporal metadata
extraction, and basic entity tagging.

REFACTORED:
- Separated cleaning logic to src/utils/text_cleaners.py
- Fully configurable pipeline via settings.yaml
- NER-aware typo correction (fixes "San Francisco" issue)
- Proper separation of concerns
"""

from src.utils.config_manager import ConfigManager
from src.utils.text_cleaners import TextCleanerConfig, clean_text_pipeline
from src.schemas.data_models import PreprocessSingleResponse, Entity
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Set
import json
import atexit
import logging
import re
import spacy
import os
from pydantic import HttpUrl
from pydantic_core import Url
from spellchecker import SpellChecker

# Language detection imports with proper error handling
try:
    from langdetect import detect, DetectorFactory
    # Warm up langdetect on module load
    try:
        _ = detect("Initialize language detection profiles.")
    except:
        pass
    DetectorFactory.seed = 0
except ImportError:
    detect = None

logger = logging.getLogger("ingestion_service")


class TextPreprocessor:
    """
    A class for ingesting, cleaning, and preprocessing unstructured text.
    Uses spaCy for NER and modular text cleaners from utils.
    
    IMPROVEMENTS:
    - Modular, configurable cleaning pipeline
    - NER-aware typo correction
    - Proper separation of concerns
    - All cleaning steps configurable via settings.yaml or API
    """
    
    # Class-level cache for spaCy models
    _nlp_cache: Dict[str, Any] = {}

    def __init__(self, custom_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the TextPreprocessor.
        
        Args:
            custom_config: Optional custom cleaning configuration to override settings
        """
        self.nlp = None
        self.settings = ConfigManager.get_settings()
        self.spell_checker = None  # Lazy initialization
        
        # Initialize cleaning configuration
        if custom_config:
            self.cleaning_config = TextCleanerConfig(custom_config)
        else:
            pipeline_config = self.settings.ingestion_service.cleaning_pipeline.model_dump()
            self.cleaning_config = TextCleanerConfig(pipeline_config)
        
        self._load_models()

    def _load_models(self):
        """Load spaCy model with class-level caching."""
        try:
            model_name = self.settings.ingestion_service.model_name
            cache_dir = self.settings.ingestion_service.model_cache_dir
            
            # Reuse cached model
            if model_name in TextPreprocessor._nlp_cache:
                self.nlp = TextPreprocessor._nlp_cache[model_name]
                logger.info(f"Reusing cached spaCy model '{model_name}'")
                return
            
            logger.info(f"Loading spaCy model '{model_name}' with cache directory: {cache_dir}...")
            os.environ["SPACY_DATA"] = cache_dir

            if self.settings.general.gpu_enabled:
                try:
                    spacy.require_gpu()
                    logger.info("SpaCy using GPU.")
                except Exception as e:
                    logger.warning(f"SpaCy GPU unavailable: {e}. Using CPU.")
            else:
                logger.info("GPU disabled. SpaCy using CPU.")

            nlp = spacy.load(model_name)
            TextPreprocessor._nlp_cache[model_name] = nlp
            self.nlp = nlp
            
            logger.info(f"SpaCy model '{model_name}' loaded and cached.")

        except Exception as e:
            logger.critical(f"Failed to load spaCy model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to load spaCy model. Error: {e}")

    def _get_spell_checker(self) -> SpellChecker:
        """Lazy initialization of spell checker."""
        if self.spell_checker is None:
            self.spell_checker = SpellChecker()
            logger.debug("Spell checker initialized")
        return self.spell_checker

    def close(self):
        """Free up resources."""
        if self.nlp:
            logger.info("Closing TextPreprocessor instance")
            self.nlp = None
        if self.spell_checker:
            self.spell_checker = None

    def tag_entities(self, text: str) -> List[Entity]:
        """
        Perform Named Entity Recognition using spaCy.
        
        Args:
            text: Cleaned text to tag
            
        Returns:
            List of Entity objects
        """
        logger.debug("Starting entity tagging")
        if self.nlp is None:
            logger.error("spaCy model not loaded")
            return []

        try:
            doc = self.nlp(text)
            entities = []
            
            # Filter by configured entity types
            entity_types = self.settings.ingestion_service.entity_recognition.entity_types_to_extract
            
            for ent in doc.ents:
                if ent.label_ in entity_types:
                    entities.append(Entity(
                        text=ent.text,
                        type=ent.label_,
                        start_char=ent.start_char,
                        end_char=ent.end_char
                    ))
            
            logger.debug(f"Found {len(entities)} entities")
            return entities
        except Exception as e:
            logger.error(f"Error during entity tagging: {e}", exc_info=True)
            return []

    def clean_text(
        self,
        text: str,
        ner_entities: Optional[Set[str]] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Clean text using modular cleaning pipeline.
        
        CRITICAL: Can pass NER entities to protect proper nouns from typo correction.
        
        Args:
            text: Raw input text
            ner_entities: Optional set of entity texts to protect (e.g., {"San Francisco", "Apple Inc."})
            custom_config: Optional custom configuration to override instance config
            
        Returns:
            Cleaned text
        """
        config = self.cleaning_config
        if custom_config:
            config = TextCleanerConfig(custom_config)
        
        spell_checker = self._get_spell_checker() if config.enable_typo_correction else None
        
        return clean_text_pipeline(
            text=text,
            config=config,
            ner_entities=ner_entities,
            spell_checker=spell_checker
        )

    def clean_text_with_ner_protection(self, text: str) -> tuple[str, List[Entity]]:
        """
        Clean text while protecting NER entities from typo correction.
        
        This method first extracts entities, then uses them to protect proper nouns
        during cleaning. This solves the "San Francisco" -> "Can Francisco" issue.
        
        Args:
            text: Raw input text
            
        Returns:
            Tuple of (cleaned_text, entities)
        """
        # Step 1: Do a quick NER pass on original text to identify entities
        if self.cleaning_config.typo_use_ner and self.nlp:
            logger.debug("Extracting entities for typo protection")
            doc = self.nlp(text)
            entity_texts = {ent.text for ent in doc.ents}
        else:
            entity_texts = None
        
        # Step 2: Clean text with entity protection
        cleaned_text = self.clean_text(text, ner_entities=entity_texts)
        
        # Step 3: Extract entities from cleaned text
        entities = self.tag_entities(cleaned_text)
        
        return cleaned_text, entities

    def _clean_field(self, field_value: Any) -> Any:
        """
        Recursively clean metadata fields.
        
        Args:
            field_value: Field value to clean
            
        Returns:
            Cleaned value
        """
        if field_value is None:
            return None

        if isinstance(field_value, str):
            return self.clean_text(field_value) or None
        elif isinstance(field_value, list):
            cleaned_list = []
            for item in field_value:
                if isinstance(item, str):
                    cleaned = self.clean_text(item)
                    if cleaned:
                        cleaned_list.append(cleaned)
                elif isinstance(item, Url):
                    cleaned_list.append(item)
            return cleaned_list or None
        elif isinstance(field_value, dict):
            cleaned_dict = {}
            for key, value in field_value.items():
                if isinstance(value, str):
                    cleaned = self.clean_text(value)
                    if cleaned:
                        cleaned_dict[key] = cleaned
                else:
                    cleaned_dict[key] = value
            return cleaned_dict or None
        elif isinstance(field_value, (Url, bool, int, date, datetime)):
            return field_value
        else:
            logger.warning(f"Unsupported field type: {type(field_value)}")
            return field_value

    def _get_last_weekday(self, weekday_name: str, reference_date: datetime) -> Optional[date]:
        """Calculate the most recent occurrence of a weekday."""
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        weekday_name_lower = weekday_name.lower()

        if weekday_name_lower not in weekdays:
            return None

        target_weekday = weekdays[weekday_name_lower]
        days_ago = (reference_date.weekday() - target_weekday + 7) % 7
        if days_ago == 0:
            days_ago = 7

        last_weekday_date = reference_date - timedelta(days=days_ago)
        return last_weekday_date.date()

    def extract_temporal_metadata(self, text_to_parse: str, reference_date: Optional[date] = None) -> Optional[str]:
        """Extract and normalize temporal metadata from text."""
        import dateparser
        
        languages = self.settings.ingestion_service.dateparser_languages

        parsed_reference_date = None
        if reference_date:
            if isinstance(reference_date, date) and not isinstance(reference_date, datetime):
                parsed_reference_date = datetime(
                    reference_date.year, reference_date.month, reference_date.day)
            elif isinstance(reference_date, datetime):
                parsed_reference_date = reference_date

        match = re.match(r'last\s+([a-zA-Z]+)', text_to_parse, re.IGNORECASE)
        if match and parsed_reference_date:
            weekday_name = match.group(1)
            calculated_date = self._get_last_weekday(weekday_name, parsed_reference_date)
            if calculated_date:
                return calculated_date.strftime('%Y-%m-%d')

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
            if date_obj:
                return date_obj.strftime('%Y-%m-%d')
            return None
        except Exception as e:
            logger.warning(f"Failed to parse date: {e}")
            return None

    def _detect_language(self, text: str) -> Optional[str]:
        """Detect language using langdetect."""
        if not text or len(text.strip()) < 10:
            return None
        
        if detect is None:
            return None
        
        try:
            return detect(text)
        except Exception:
            return None

    def preprocess(
        self,
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
        geographical_data: Optional[Dict[str, Any]] = None,
        embargo_date: Optional[date] = None,
        sentiment: Optional[str] = None,
        word_count: Optional[int] = None,
        publisher: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
        custom_cleaning_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform complete preprocessing pipeline.
        
        Args:
            text: Main content text
            document_id: Unique document identifier
            ... (other metadata fields)
            custom_cleaning_config: Optional custom cleaning configuration
            
        Returns:
            Dictionary with processed data
        """
        logger.info(f"Starting preprocessing for document_id={document_id}")

        processed_data = {
            "document_id": document_id,
            "original_text": text,
            "entities": [],
            "temporal_metadata": None,
            "cleaned_additional_metadata": {}
        }

        # Use custom config if provided
        if custom_cleaning_config:
            temp_config = self.cleaning_config
            self.cleaning_config = TextCleanerConfig(custom_cleaning_config)

        # Step 1: Clean text with NER protection
        logger.debug("Cleaning main text with NER protection")
        cleaned_text, entities = self.clean_text_with_ner_protection(text)
        processed_data["cleaned_text"] = cleaned_text
        processed_data["entities"] = entities

        # Restore original config if temp was used
        if custom_cleaning_config:
            self.cleaning_config = temp_config

        # Step 2: Clean metadata fields
        logger.debug("Cleaning metadata fields")
        processed_data["cleaned_title"] = self._clean_field(title)
        processed_data["cleaned_excerpt"] = self._clean_field(excerpt)
        processed_data["cleaned_author"] = self._clean_field(author)
        processed_data["cleaned_publication_date"] = self._clean_field(publication_date)
        processed_data["cleaned_revision_date"] = self._clean_field(revision_date)
        processed_data["cleaned_source_url"] = self._clean_field(source_url)
        processed_data["cleaned_categories"] = self._clean_field(categories)
        processed_data["cleaned_tags"] = self._clean_field(tags)
        processed_data["cleaned_media_asset_urls"] = self._clean_field(media_asset_urls)
        processed_data["cleaned_geographical_data"] = self._clean_field(geographical_data)
        processed_data["cleaned_embargo_date"] = self._clean_field(embargo_date)
        processed_data["cleaned_sentiment"] = self._clean_field(sentiment)
        processed_data["cleaned_word_count"] = self._clean_field(word_count)
        processed_data["cleaned_publisher"] = self._clean_field(publisher)

        # Step 3: Process additional metadata
        if additional_metadata:
            for key, value in additional_metadata.items():
                cleaned_value = self._clean_field(value)
                if cleaned_value is not None:
                    processed_data["cleaned_additional_metadata"][f"cleaned_{key}"] = cleaned_value

        # Step 4: Compute dynamic fields
        if word_count is None and cleaned_text:
            computed_word_count = len(cleaned_text.split())
            processed_data["cleaned_word_count"] = computed_word_count
        elif word_count is not None:
            processed_data["cleaned_word_count"] = self._clean_field(word_count)

        original_reading_time = additional_metadata.get('reading_time') if additional_metadata else None
        if original_reading_time is None and processed_data.get("cleaned_word_count"):
            reading_time = max(1, round(processed_data["cleaned_word_count"] / 200))
            processed_data["cleaned_additional_metadata"]["cleaned_reading_time"] = reading_time
        elif original_reading_time is not None:
            processed_data["cleaned_additional_metadata"]["cleaned_reading_time"] = self._clean_field(original_reading_time)

        original_language = additional_metadata.get('language') if additional_metadata else None
        if original_language is None and cleaned_text:
            language = self._detect_language(cleaned_text)
            if language:
                processed_data["cleaned_additional_metadata"]["cleaned_language"] = language
        elif original_language is not None:
            processed_data["cleaned_additional_metadata"]["cleaned_language"] = self._clean_field(original_language)

        # Step 5: Extract temporal metadata
        logger.debug("Extracting temporal metadata")
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

        logger.info(
            f"Preprocessing complete for document_id={document_id}. "
            f"Found {len(entities)} entities, normalized date: {temporal_metadata}")
        
        return processed_data

# src/core/processor.py
