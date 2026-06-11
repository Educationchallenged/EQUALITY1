"""Health check endpoint.

Provides a simple liveness probe. In production, this would also check
database connectivity and external service availability, propagating any
errors as structured responses rather than swallowing them.
"""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Return application health status."""
    checks = {
        "status": "healthy",
        "checks": {
            "app": "ok",
        },
    }
    return jsonify(checks)
