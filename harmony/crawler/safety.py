from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import parse_qs, urlparse


@lru_cache(maxsize=512)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile and cache regex patterns to avoid recursion issues."""
    return re.compile(pattern, re.IGNORECASE)


@dataclass
class SafetyConfig:
    """Configuration for crawler safety mechanisms."""

    allowed_methods: set[str] = field(default_factory=lambda: {"GET", "HEAD"})

    dangerous_url_patterns: list[str] = field(
        default_factory=lambda: [
            # Path segment boundaries prevent false positives
            # (?:^|/) = start of URL or after /
            # (?:/|$) = before / or end of URL
            # Destructive actions
            r"(?:^|/)delete(?:/|$)",
            r"(?:^|/)remove(?:/|$)",
            r"(?:^|/)destroy(?:/|$)",
            r"(?:^|/)purge(?:/|$)",
            r"(?:^|/)drop(?:/|$)",
            r"(?:^|/)truncate(?:/|$)",
            r"(?:^|/)erase(?:/|$)",
            # Mutation actions
            r"(?:^|/)edit(?:/|$)",
            r"(?:^|/)update(?:/|$)",
            r"(?:^|/)modify(?:/|$)",
            r"(?:^|/)change(?:/|$)",
            r"(?:^|/)save(?:/|$)",
            r"(?:^|/)create(?:/|$)",
            r"(?:^|/)add(?:/|$)",
            r"(?:^|/)insert(?:/|$)",
            # Submission
            r"(?:^|/)submit(?:/|$)",
            r"(?:^|/)submit$",
            r"(?:^|/)cancel$",
            r"[?&]submit=",
            r"[?&]cancel=",
            r"[?&]edit=",
            # Authentication
            r"(?:^|/)logout(?:/|$)",
            r"(?:^|/)signout(?:/|$)",
            r"(?:^|/)sign-out(?:/|$)",
            r"(?:^|/)logoff(?:/|$)",
            r"(?:^|/)disconnect(?:/|$)",
            # Admin/API paths - add end boundary only (start already covered)
            r"/admin/.*/delete(?:/|$)",
            r"/admin/.*/remove(?:/|$)",
            r"/admin/.*/edit(?:/|$)",
            r"/admin/.*/submit(?:/|$)",
            r"/api/.*/delete(?:/|$)",
            r"/api/.*/remove(?:/|$)",
            r"/api/.*/update(?:/|$)",
            # Confirmation
            r"(?:^|/)confirm(?:/|$)",
            r"(?:^|/)approval(?:/|$)",
            # Query param actions (already have proper boundaries)
            r"\?action=(delete|remove|edit|submit|cancel)",
            # Domain/protocol patterns (unchanged)
            r"javascript:",
            # End-anchored patterns
            r"(?:^|/)destroy$",
            r"(?:^|/)purge$",
            # Recursive path segments (buggy link extraction/CMS routing)
            # Matches segments like /index.php/index.php/ or /foo/foo/
            r"(?i)(?:^|/)([^/]+)/\1/",
        ]
    )

    dangerous_query_params: dict[str, list[str]] = field(
        default_factory=lambda: {
            "action": [
                "delete",
                "remove",
                "destroy",
                "purge",
                "edit",
                "update",
                "create",
                "submit",
                "cancel",
            ],
            "method": ["DELETE", "POST", "PUT", "PATCH"],
            "_method": ["delete", "post", "put", "patch"],
            "confirm": ["yes", "true", "1"],
            "confirmed": ["yes", "true", "1"],
            "force": ["yes", "true", "1"],
            "do": ["delete", "remove", "destroy", "submit", "edit"],
            "submit": ["yes", "true", "1"],
            "cancel": ["yes", "true", "1"],
        }
    )

    safe_mode: bool = False

    dry_run: bool = False

    allow_list_patterns: list[str] = field(default_factory=list)

    additional_deny_patterns: list[str] = field(default_factory=list)


def _check_pattern_list(
    url: str, patterns: list[str], match_message: str
) -> tuple[bool, str]:
    """Check if URL matches any pattern in the list."""
    for pattern in patterns:
        try:
            compiled = _compile_pattern(pattern)
            if compiled.search(url):
                return True, match_message.format(pattern=pattern)
        except (re.error, RecursionError):
            continue
    return False, ""


def is_url_safe(url: str, config: SafetyConfig) -> tuple[bool, str]:  # noqa: PLR0911
    """
    Check if a URL is safe to crawl.

    Args:
        url: URL to check
        config: Safety configuration

    Returns:
        Tuple of (is_safe, reason_if_blocked)
    """
    # Always allow robots.txt to avoid recursion issues
    if url.endswith("/robots.txt"):
        return True, ""

    # Check allow list first (highest priority)
    matched, _ = _check_pattern_list(url, config.allow_list_patterns, "")
    if matched:
        return True, ""

    # Check dangerous patterns
    matched, reason = _check_pattern_list(
        url, config.dangerous_url_patterns, "Matched dangerous pattern: {pattern}"
    )
    if matched:
        return False, reason

    # Check additional deny patterns
    matched, reason = _check_pattern_list(
        url, config.additional_deny_patterns, "Matched user deny pattern: {pattern}"
    )
    if matched:
        return False, reason

    is_safe, reason = _check_query_params(url, config)
    if not is_safe:
        return False, reason

    if config.safe_mode:
        is_safe, reason = _check_safe_mode(url)
        if not is_safe:
            return False, reason

    return True, ""


def _check_query_params(url: str, config: SafetyConfig) -> tuple[bool, str]:
    """Check query parameters for dangerous values."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    for param_name, dangerous_values in config.dangerous_query_params.items():
        if param_name in query_params:
            param_values = query_params[param_name]
            for param_value in param_values:
                if param_value.lower() in [v.lower() for v in dangerous_values]:
                    return False, f"Dangerous query param: {param_name}={param_value}"
    return True, ""


def _check_safe_mode(url: str) -> tuple[bool, str]:
    """Check safe mode restrictions (id + action words)."""
    if "id=" not in url.lower():
        return True, ""

    # Use path-segment boundaries but allow query params after action word
    # (?:[/?]|$) allows /, ?, or end of string after action word
    action_patterns = [
        r"(?:^|/)delete(?:[/?]|$)",
        r"(?:^|/)remove(?:[/?]|$)",
        r"(?:^|/)edit(?:[/?]|$)",
        r"(?:^|/)update(?:[/?]|$)",
        r"(?:^|/)change(?:[/?]|$)",
    ]

    url_lower = url.lower()
    for pattern in action_patterns:
        compiled = _compile_pattern(pattern)
        if compiled.search(url_lower):
            # Extract action word from pattern for error message
            action_word = pattern.split("/")[-2].replace("(?:", "").replace(")", "")
            return (
                False,
                f"Safe mode: URL contains 'id=' and action word '{action_word}'",
            )
    return True, ""
