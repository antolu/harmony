from __future__ import annotations

from harmony.core.language_detection import LanguageDetector, language_detector


def test_language_detector_importable_from_core() -> None:
    assert isinstance(language_detector, LanguageDetector)


def test_detect_english() -> None:
    result = language_detector.detect_language(
        "The quick brown fox jumps over the lazy dog"
    )
    assert result == "en"


def test_detect_returns_none_or_str_on_garbage() -> None:
    result = language_detector.detect_language("xzqjk")
    assert result is None or isinstance(result, str)
