"""Shared test fixtures."""

import pytest

from app.create_app import create_app


@pytest.fixture
def app():
    """Create application for testing."""
    import os

    os.environ["FLASK_ENV"] = "testing"
    app = create_app()
    yield app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()
