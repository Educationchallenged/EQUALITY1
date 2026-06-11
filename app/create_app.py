"""Application factory.

Creates and configures the Flask application with:
- Centralized error handling (no silent swallowing)
- Request logging middleware
- Route blueprints
"""

import logging

from flask import Flask

from app.config import get_config
from app.errors.handlers import register_error_handlers
from app.logging_config import setup_logging
from app.middleware.request_logging import register_request_logging
from app.routes.health import health_bp
from app.routes.rights import rights_bp

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application.

    Raises:
        EnvironmentError: If required configuration is missing in production.
        ValueError: If FLASK_ENV has an invalid value.
    """
    setup_logging()

    app = Flask(__name__)

    config_class = get_config()
    app.config.from_object(config_class)

    register_error_handlers(app)
    register_request_logging(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(rights_bp)

    logger.info("Application created successfully with config: %s", config_class.__name__)
    return app
