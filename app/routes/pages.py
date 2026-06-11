"""Page routes serving HTML templates."""

import logging

from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def landing():
    """Serve the 360 House Videos landing page."""
    return render_template("landing.html")
