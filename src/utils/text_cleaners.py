"""
src/utils/text_cleaners.py

Utility module for text cleaning operations.
Provides modular, configurable text cleaning functions with proper separation of concerns.

Each cleaning function can be enabled/disabled via configuration.
"""

import re
import string
import ftfy
import logging
from typing import List, Set, Optional
from spellchecker import SpellChecker

logger = logging.getLogger("ingestion_service")


class TextCleanerConfig:
    """Configuration object for text cleaning operations."""

    def __init__(self, config_dict: dict):
        """
        Initialize cleaner config from settings dictionary.
        
        Args:
            config_dict: Dictionary from settings.ingestion_service.cleaning_pipeline
        """
        self.remove_html_tags = config_dict.get('remove_html_tags', True)
        self.normalize_whitespace = config_dict.get(
            'normalize_whitespace', True)
        self.fix_encoding = config_dict.get('fix_encoding', True)
        self.normalize_punctuation = config_dict.get(
            'normalize_punctuation', True)
        self.normalize_unicode_dashes = config_dict.get(
            'normalize_unicode_dashes', True)
        self.normalize_smart_quotes = config_dict.get(
            'normalize_smart_quotes', True)
        self.remove_excessive_punctuation = config_dict.get(
            'remove_excessive_punctuation', True)
        self.add_space_after_punctuation = config_dict.get(
            'add_space_after_punctuation', True)
        self.standardize_units = config_dict.get('standardize_units', True)
        self.standardize_currency = config_dict.get(
            'standardize_currency', True)
        self.enable_typo_correction = config_dict.get(
            'enable_typo_correction', True)

        # Typo correction sub-config
        typo_config = config_dict.get('typo_correction', {})
        self.typo_min_length = typo_config.get('min_word_length', 3)
        self.typo_max_length = typo_config.get('max_word_length', 15)
        self.typo_skip_capitalized = typo_config.get(
            'skip_capitalized_words', True)
        self.typo_skip_mixed_case = typo_config.get('skip_mixed_case', True)
        self.typo_use_ner = typo_config.get('use_ner_entities', True)
        self.typo_confidence = typo_config.get('confidence_threshold', 0.7)


# Pre-compiled regex patterns for performance
class RegexPatterns:
    """Pre-compiled regex patterns for text cleaning."""

    HTML_TAGS = re.compile(r'<.*?>', re.DOTALL)
    WHITESPACE = re.compile(r'\s+', re.MULTILINE)
    UNICODE_DASHES = re.compile(r'[\u2010-\u2015\u2212]')
    SMART_QUOTES_DOUBLE = re.compile(r'[\u201c\u201d]')
    SMART_QUOTES_SINGLE = re.compile(r'[\u2018\u2019]')
    ELLIPSIS = re.compile(r'\.{2,}')
    REPEATED_COMMAS = re.compile(r',{2,}')
    REPEATED_EXCLAMATION = re.compile(r'!{2,}')
    REPEATED_QUESTION = re.compile(r'\?{2,}')
    REPEATED_DASHES = re.compile(r'-{2,}')
    PUNCTUATION_SPACING = re.compile(r'([.,?!])(?=[a-zA-Z0-9])')

    # Currency patterns
    CURRENCY_USD = re.compile(r'\$\s*(\d+(?:\.\d{1,2})?)')
    CURRENCY_EUR = re.compile(r'(\d+)\s*€')
    CURRENCY_GBP = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
    CURRENCY_WORD_USD = re.compile(r'\b(?:usd|us dollars?)\b', re.IGNORECASE)
    CURRENCY_WORD_EUR = re.compile(r'\b(?:eur|euros?)\b', re.IGNORECASE)
    CURRENCY_WORD_GBP = re.compile(
        r'\b(?:gbp|pounds?sterling)\b', re.IGNORECASE)

    # Unit patterns
    UNIT_PERCENT = re.compile(r'(\d+(?:\.\d+)?)\s*%')
    UNIT_METERS = re.compile(r'(\d+)\s*m\b')
    UNIT_KM = re.compile(r'(\d+)\s*km\b')
    UNIT_KG = re.compile(r'(\d+)\s*kg\b')
    UNIT_CM = re.compile(r'(\d+)\s*cm\b')
    UNIT_FEET = re.compile(r'(\d+)\s*ft\b')
    UNIT_POUNDS = re.compile(r'(\d+)\s*lbs\b')
    UNIT_MILES = re.compile(r'(\d+)\s*mi\b')
    UNIT_GRAMS = re.compile(r'(\d+)\s*g\b')


def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.
    
    Args:
        text: Input text with potential HTML tags
        
    Returns:
        Text with HTML tags removed
    """
    return RegexPatterns.HTML_TAGS.sub(' ', text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace by collapsing multiple spaces/tabs/newlines into single spaces.
    
    Args:
        text: Input text with irregular whitespace
        
    Returns:
        Text with normalized whitespace
    """
    return RegexPatterns.WHITESPACE.sub(' ', text).strip()


def fix_encoding(text: str) -> str:
    """
    Fix common encoding issues using ftfy library.
    Handles mojibake and mixed encodings.
    
    Args:
        text: Text with potential encoding issues
        
    Returns:
        Text with fixed encoding
    """
    return ftfy.fix_text(text)


def normalize_unicode_dashes(text: str) -> str:
    """
    Convert unicode dashes to ASCII hyphens.
    
    Args:
        text: Text with unicode dashes
        
    Returns:
        Text with ASCII hyphens
    """
    return RegexPatterns.UNICODE_DASHES.sub('-', text)


def normalize_smart_quotes(text: str) -> str:
    """
    Convert smart/curly quotes to straight quotes.
    
    Args:
        text: Text with smart quotes
        
    Returns:
        Text with straight quotes
    """
    text = RegexPatterns.SMART_QUOTES_DOUBLE.sub('"', text)
    text = RegexPatterns.SMART_QUOTES_SINGLE.sub("'", text)
    return text


def remove_non_printable(text: str) -> str:
    """
    Remove non-printable characters from text.
    
    Args:
        text: Text with potential non-printable characters
        
    Returns:
        Text with only printable characters
    """
    printable = set(string.printable)
    return ''.join(filter(lambda x: x in printable, text))


def remove_excessive_punctuation(text: str) -> str:
    """
    Remove repeated punctuation marks (!!!!, ????, etc).
    
    Args:
        text: Text with excessive punctuation
        
    Returns:
        Text with normalized punctuation
    """
    text = RegexPatterns.ELLIPSIS.sub('.', text)
    text = RegexPatterns.REPEATED_COMMAS.sub(',', text)
    text = RegexPatterns.REPEATED_EXCLAMATION.sub('!', text)
    text = RegexPatterns.REPEATED_QUESTION.sub('?', text)
    text = RegexPatterns.REPEATED_DASHES.sub('-', text)
    return text


def add_space_after_punctuation(text: str) -> str:
    """
    Ensure space after punctuation marks.
    
    Args:
        text: Text potentially missing spaces after punctuation
        
    Returns:
        Text with proper spacing after punctuation
    """
    return RegexPatterns.PUNCTUATION_SPACING.sub(r'\1 ', text)


def standardize_currency(text: str) -> str:
    """
    Standardize currency representations.
    
    Examples:
        $100 -> USD 100
        €50 -> 50 EUR
        £20 -> GBP 20
    
    Args:
        text: Text with various currency formats
        
    Returns:
        Text with standardized currency
    """
    text = RegexPatterns.CURRENCY_USD.sub(r'USD \1', text)
    text = RegexPatterns.CURRENCY_EUR.sub(r'\1 EUR', text)
    text = RegexPatterns.CURRENCY_GBP.sub(r'GBP \1', text)
    text = RegexPatterns.CURRENCY_WORD_USD.sub('USD', text)
    text = RegexPatterns.CURRENCY_WORD_EUR.sub('EUR', text)
    text = RegexPatterns.CURRENCY_WORD_GBP.sub('GBP', text)
    return text


def standardize_units(text: str) -> str:
    """
    Standardize unit representations.
    
    Examples:
        5m -> 5 meters
        10kg -> 10 kilograms
        3% -> 3 percent
    
    Args:
        text: Text with various unit formats
        
    Returns:
        Text with standardized units
    """
    text = RegexPatterns.UNIT_PERCENT.sub(r'\1 percent', text)
    text = RegexPatterns.UNIT_METERS.sub(r'\1 meters', text)
    text = RegexPatterns.UNIT_KM.sub(r'\1 kilometers', text)
    text = RegexPatterns.UNIT_KG.sub(r'\1 kilograms', text)
    text = RegexPatterns.UNIT_CM.sub(r'\1 centimeters', text)
    text = RegexPatterns.UNIT_FEET.sub(r'\1 feet', text)
    text = RegexPatterns.UNIT_POUNDS.sub(r'\1 pounds', text)
    text = RegexPatterns.UNIT_MILES.sub(r'\1 miles', text)
    text = RegexPatterns.UNIT_GRAMS.sub(r'\1 grams', text)
    return text


def correct_typos(
    text: str,
    config: TextCleanerConfig,
    ner_entities: Optional[Set[str]] = None,
    spell_checker: Optional[SpellChecker] = None
) -> str:
    """
    Correct typographical errors using PySpellChecker.
    
    CRITICAL: Uses NER entities to avoid correcting proper nouns like "San Francisco".
    
    Args:
        text: Text to check for typos
        config: Cleaning configuration with typo settings
        ner_entities: Set of entity words from spaCy NER (prevents correcting proper nouns)
        spell_checker: Optional pre-initialized spell checker (for performance)
        
    Returns:
        Text with typos corrected
    """
    if not config.enable_typo_correction:
        return text

    if spell_checker is None:
        spell_checker = SpellChecker()

    # Extract NER entity words for lookup
    entity_words = set()
    if ner_entities and config.typo_use_ner:
        for entity_text in ner_entities:
            # Split multi-word entities (e.g., "San Francisco" -> {"San", "Francisco"})
            entity_words.update(word.lower() for word in entity_text.split())

    words = text.split()
    corrected_words = []

    for word in words:
        # Skip non-alphabetic words
        if not word.isalpha():
            corrected_words.append(word)
            continue

        # Skip words outside length range
        if len(word) < config.typo_min_length or len(word) > config.typo_max_length:
            corrected_words.append(word)
            continue

        # CRITICAL: Skip if word is part of a recognized entity
        if config.typo_use_ner and word.lower() in entity_words:
            corrected_words.append(word)
            logger.debug(f"Skipping '{word}' - recognized as NER entity")
            continue

        # Skip capitalized words (proper nouns)
        if config.typo_skip_capitalized and word[0].isupper() and len(word) > 5:
            corrected_words.append(word)
            continue

        # Skip mixed-case words (e.g., "iPhone", "McDonald's")
        if config.typo_skip_mixed_case and word[0].isupper() and any(c.isupper() for c in word[1:]):
            corrected_words.append(word)
            continue

        # Check if word is misspelled
        word_lower = word.lower()
        correction = spell_checker.correction(word_lower)

        if correction and correction != word_lower:
            # Only apply if length difference is small (high confidence)
            length_diff = abs(len(correction) - len(word_lower))
            if length_diff <= (1.0 - config.typo_confidence) * 10:  # Scale threshold
                # Preserve original capitalization
                if word[0].isupper():
                    correction = correction.capitalize()
                corrected_words.append(correction)
                logger.debug(f"Corrected typo: '{word}' -> '{correction}'")
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)

    return ' '.join(corrected_words)


def clean_text_pipeline(
    text: str,
    config: TextCleanerConfig,
    ner_entities: Optional[Set[str]] = None,
    spell_checker: Optional[SpellChecker] = None
) -> str:
    """
    Execute the full text cleaning pipeline based on configuration.
    
    Args:
        text: Raw input text
        config: Cleaning configuration
        ner_entities: Optional set of NER entity texts to protect from typo correction
        spell_checker: Optional pre-initialized spell checker
        
    Returns:
        Cleaned text
    """
    logger.debug("Starting text cleaning pipeline")

    # Step 1: HTML removal
    if config.remove_html_tags:
        text = remove_html_tags(text)
        logger.debug("HTML tags removed")

    # Step 2: Initial whitespace normalization
    if config.normalize_whitespace:
        text = normalize_whitespace(text)
        logger.debug("Whitespace normalized")

    # Step 3: Encoding fixes
    if config.fix_encoding:
        text = fix_encoding(text)
        logger.debug("Encoding fixed")

    # Step 4: Currency standardization
    if config.standardize_currency:
        text = standardize_currency(text)
        logger.debug("Currency standardized")

    # Step 5: Unit standardization
    if config.standardize_units:
        text = standardize_units(text)
        logger.debug("Units standardized")

    # Step 6: Punctuation normalization
    if config.normalize_punctuation:
        if config.normalize_unicode_dashes:
            text = normalize_unicode_dashes(text)
        if config.normalize_smart_quotes:
            text = normalize_smart_quotes(text)
        text = remove_non_printable(text)
        logger.debug("Punctuation normalized")

    # Step 7: Excessive punctuation removal
    if config.remove_excessive_punctuation:
        text = remove_excessive_punctuation(text)
        logger.debug("Excessive punctuation removed")

    # Step 8: Space after punctuation
    if config.add_space_after_punctuation:
        text = add_space_after_punctuation(text)
        logger.debug("Spacing after punctuation ensured")

    # Step 9: Typo correction (uses NER entities if provided)
    if config.enable_typo_correction:
        text = correct_typos(text, config, ner_entities, spell_checker)
        logger.debug("Typo correction completed")

    # Step 10: Final whitespace normalization
    if config.normalize_whitespace:
        text = normalize_whitespace(text)
        logger.debug("Final whitespace normalized")

    logger.debug("Text cleaning pipeline completed")
    return text


# src/utils/text_cleaners.py
