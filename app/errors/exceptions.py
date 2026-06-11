"""Custom exception hierarchy for the EQUALITY1 application.

All application-specific errors inherit from AppError, which provides:
- Structured error codes for programmatic handling
- HTTP status code mapping
- Safe user-facing messages (no internal details leaked)
- Optional context for logging without exposing internals to clients
"""

from typing import Optional


class AppError(Exception):
    """Base application error.

    All custom exceptions inherit from this class so they can be caught
    uniformly by the error handler middleware.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        self.message = message or self.default_message
        if error_code:
            self.error_code = error_code
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Serialize error for API responses. Never includes internal context."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
            }
        }


class ValidationError(AppError):
    """Raised when request data fails validation."""

    status_code = 400
    error_code = "VALIDATION_ERROR"
    default_message = "The provided data is invalid."

    def __init__(
        self,
        message: Optional[str] = None,
        field_errors: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.field_errors = field_errors or {}

    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.field_errors:
            result["error"]["fields"] = self.field_errors
        return result


class AuthenticationError(AppError):
    """Raised when authentication fails or credentials are missing."""

    status_code = 401
    error_code = "AUTHENTICATION_ERROR"
    default_message = "Authentication is required."


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks permission for an action."""

    status_code = 403
    error_code = "AUTHORIZATION_ERROR"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_code = "NOT_FOUND"
    default_message = "The requested resource was not found."


class RateLimitError(AppError):
    """Raised when a client exceeds the allowed request rate."""

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests. Please try again later."

    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.retry_after = retry_after


class ExternalServiceError(AppError):
    """Raised when a call to an external service (API, database, etc.) fails.

    The original error details are stored in context for logging but never
    exposed to the client.
    """

    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"
    default_message = "An external service is temporarily unavailable."


class DatabaseError(AppError):
    """Raised when a database operation fails.

    Wraps underlying DB exceptions so that raw SQL errors or connection
    details are never leaked to clients.
    """

    status_code = 503
    error_code = "DATABASE_ERROR"
    default_message = "A database error occurred. Please try again later."
