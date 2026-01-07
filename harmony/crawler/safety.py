from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


@dataclass
class SafetyConfig:
    """Configuration for crawler safety mechanisms."""

    allowed_methods: set[str] = field(default_factory=lambda: {"GET", "HEAD"})

    dangerous_url_patterns: list[str] = field(
        default_factory=lambda: [
            r"/delete/",
            r"/remove/",
            r"/destroy/",
            r"/purge/",
            r"/drop/",
            r"/truncate/",
            r"/erase/",
            r"/edit/",
            r"/update/",
            r"/modify/",
            r"/change/",
            r"/save/",
            r"/create/",
            r"/add/",
            r"/insert/",
            r"/submit/",
            r"[?&]submit=",
            r"[?&]cancel=",
            r"[?&]edit=",
            r"/submit$",
            r"/cancel$",
            r"/logout",
            r"/signout",
            r"/sign-out",
            r"/logoff",
            r"/disconnect",
            r"/admin/.*/delete",
            r"/admin/.*/remove",
            r"/admin/.*/edit",
            r"/admin/.*/submit",
            r"/confirm",
            r"/approval",
            r"/api/.*/delete",
            r"/api/.*/remove",
            r"/api/.*/update",
            r"/destroy$",
            r"/purge$",
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


def is_url_safe(url: str, config: SafetyConfig) -> tuple[bool, str]:
    """
    Check if a URL is safe to crawl.

    Args:
        url: URL to check
        config: Safety configuration

    Returns:
        Tuple of (is_safe, reason_if_blocked)
    """
    for pattern in config.allow_list_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True, ""

    for pattern in config.dangerous_url_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"Matched dangerous pattern: {pattern}"

    for pattern in config.additional_deny_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"Matched user deny pattern: {pattern}"

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

    action_words = ["delete", "remove", "edit", "update", "change"]
    for word in action_words:
        if word in url.lower():
            return False, f"Safe mode: URL contains 'id=' and action word '{word}'"
    return True, ""
