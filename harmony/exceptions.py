from __future__ import annotations


class HarmonyError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class PermissionDeniedError(HarmonyError):
    """Raised when a caller lacks permission to perform an action."""


class ResourceNotFoundError(HarmonyError):
    """Raised when a requested resource does not exist."""
