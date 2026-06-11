"""Flask error handler registration.

Centralizes all error handling so that:
1. Known AppErrors return structured JSON with the correct status code.
2. Unexpected exceptions are logged with full tracebacks but return a
   generic 500 response (no internal details leaked).
3. Standard HTTP errors (404, 405, etc.) are converted to structured JSON.
"""

import logging
import traceback

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.errors.exceptions import AppError, RateLimitError

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """Register all error handlers on the Flask app."""

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        """Handle known application errors with structured responses."""
        log_context = {
            "error_code": error.error_code,
            "path": request.path,
            "method": request.method,
        }
        if error.context:
            log_context["context"] = error.context

        logger.warning("Application error: %s — %s", error.error_code, error.message, extra=log_context)

        response = jsonify(error.to_dict())
        response.status_code = error.status_code

        if isinstance(error, RateLimitError) and error.retry_after:
            response.headers["Retry-After"] = str(error.retry_after)

        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Convert Werkzeug HTTP exceptions to structured JSON."""
        logger.info(
            "HTTP %d on %s %s: %s",
            error.code,
            request.method,
            request.path,
            error.description,
        )
        response = jsonify({
            "error": {
                "code": f"HTTP_{error.code}",
                "message": error.description,
            }
        })
        response.status_code = error.code or 500
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Catch-all for unhandled exceptions.

        Logs the full traceback for debugging but returns a generic message
        to the client — never expose stack traces or internal state.
        """
        logger.error(
            "Unhandled exception on %s %s: %s\n%s",
            request.method,
            request.path,
            str(error),
            traceback.format_exc(),
        )
        response = jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            }
        })
        response.status_code = 500
        return response
