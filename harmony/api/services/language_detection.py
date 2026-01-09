from __future__ import annotations

from functools import lru_cache

from langdetect import LangDetectException, detect, detect_langs


class LanguageDetector:
    """Detect language of text queries."""

    @staticmethod
    @lru_cache(maxsize=1000)
    def detect_language(text: str) -> str | None:
        """
        Detect language of text.

        Args:
            text: Input text

        Returns:
            ISO 639-1 language code (en, fr, de, etc.) or None if detection fails
        """
        try:
            return detect(text)
        except LangDetectException:
            return None

    @staticmethod
    def detect_with_confidence(text: str) -> tuple[str | None, float]:
        """
        Detect language with confidence score.

        Returns:
            (language_code, confidence) tuple
        """
        try:
            results = detect_langs(text)
            if results:
                best = results[0]
                return best.lang, best.prob
        except LangDetectException:
            return None, 0.0
        else:
            return None, 0.0


language_detector = LanguageDetector()
