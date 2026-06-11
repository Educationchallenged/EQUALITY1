"""Custom exception classes and error handling utilities."""

from app.errors.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    ExternalServiceError,
    FileUploadError,
    NotFoundError,
    RateLimitError,
    StitchingError,
    TourNotFoundError,
    TourProcessingError,
    ValidationError,
    VideoProcessingError,
)
from app.errors.handlers import register_error_handlers

__all__ = [
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "DatabaseError",
    "ExternalServiceError",
    "FileUploadError",
    "NotFoundError",
    "RateLimitError",
    "StitchingError",
    "TourNotFoundError",
    "TourProcessingError",
    "ValidationError",
    "VideoProcessingError",
    "register_error_handlers",
]
