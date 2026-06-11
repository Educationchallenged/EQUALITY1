"""Application configuration.

Loads settings from environment variables with sensible defaults.
Raises clear errors on startup if required configuration is missing
rather than failing silently at runtime.
"""

import os


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = False
    TESTING = False
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration.

    Validates that required secrets are set rather than falling back to
    insecure defaults.
    """

    DEBUG = False

    def __init__(self):
        if self.SECRET_KEY == "dev-secret-change-in-production":
            raise EnvironmentError(
                "SECRET_KEY must be set to a secure value in production. "
                "Set the SECRET_KEY environment variable."
            )


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    """Get configuration class based on FLASK_ENV environment variable.

    Raises:
        ValueError: If FLASK_ENV is set to an unrecognized value.
    """
    env = os.environ.get("FLASK_ENV", "development").lower()
    config_class = CONFIG_MAP.get(env)
    if config_class is None:
        raise ValueError(
            f"Unknown FLASK_ENV value: '{env}'. "
            f"Must be one of: {', '.join(CONFIG_MAP.keys())}"
        )
    return config_class
