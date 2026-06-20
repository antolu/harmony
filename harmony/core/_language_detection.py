from __future__ import annotations

from functools import lru_cache

from langdetect import LangDetectException, detect, detect_langs  # type: ignore


class LanguageDetector:
    @staticmethod
    @lru_cache(maxsize=1000)
    def detect_language(text: str) -> str | None:
        try:
            return detect(text)
        except LangDetectException:
            return None

    @staticmethod
    def detect_with_confidence(text: str) -> tuple[str | None, float]:
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
