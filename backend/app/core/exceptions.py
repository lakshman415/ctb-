"""
Custom exception hierarchy.

All application-specific exceptions inherit from CTBBaseException.
This allows centralized error handling in middleware or exception handlers.
"""


class CTBBaseException(Exception):
    """Base exception for the CTB application."""

    def __init__(self, message: str = "An unexpected error occurred"):
        self.message = message
        super().__init__(self.message)


class ExternalAPIError(CTBBaseException):
    """Raised when an external API call fails (e.g., DexScreener timeout)."""

    def __init__(self, source: str, message: str = "External API request failed"):
        self.source = source
        super().__init__(f"[{source}] {message}")


class DatabaseError(CTBBaseException):
    """Raised when a database operation fails."""

    pass


class FilterError(CTBBaseException):
    """Raised when a filter encounters invalid data or configuration."""

    pass


class ScoringError(CTBBaseException):
    """Raised when the scoring engine encounters an issue."""

    pass


class ConfigurationError(CTBBaseException):
    """Raised when application configuration is invalid or missing."""

    pass
