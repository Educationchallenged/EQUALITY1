"""Request logging middleware.

Logs every incoming request and outgoing response with timing information.
Assigns a unique request ID for tracing errors across log entries.
"""

import logging
import time
import uuid

from flask import Flask, g, request

logger = logging.getLogger(__name__)


def register_request_logging(app: Flask) -> None:
    """Attach before/after request hooks for structured logging."""

    @app.before_request
    def start_timer_and_assign_request_id():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.monotonic()
        logger.info(
            "Request started: %s %s [request_id=%s]",
            request.method,
            request.path,
            g.request_id,
        )

    @app.after_request
    def log_response(response):
        duration_ms = (time.monotonic() - g.start_time) * 1000
        logger.info(
            "Request completed: %s %s -> %d (%.1fms) [request_id=%s]",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            g.request_id,
        )
        response.headers["X-Request-ID"] = g.request_id
        return response
