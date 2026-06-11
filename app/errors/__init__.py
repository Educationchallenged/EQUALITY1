"""Custom exception classes and error handling utilities."""

from app.errors.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ExternalServiceError,
    RateLimitError,
    DatabaseError,
)
from app.errors.handlers import register_error_handlers

__all__ = [
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ExternalServiceError",
    "RateLimitError",
    "DatabaseError",
    "register_error_handlers",
]
