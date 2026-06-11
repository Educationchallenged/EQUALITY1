"""Routes for legal rights lookup and search.

Demonstrates proper error propagation in route handlers:
- Input parsing errors raise ValidationError immediately.
- Service-layer exceptions propagate to the centralized error handlers.
- No bare except clauses or silent error swallowing.
"""

import logging

from flask import Blueprint, jsonify, request

from app.errors.exceptions import ValidationError
from app.services.rights_lookup import (
    fetch_external_legal_data,
    get_right_by_id,
    save_user_case,
    search_rights,
)

logger = logging.getLogger(__name__)

rights_bp = Blueprint("rights", __name__, url_prefix="/api/rights")


@rights_bp.route("/", methods=["GET"])
def list_rights():
    """Search rights by optional query and category filters."""
    query = request.args.get("q")
    category = request.args.get("category")
    results = search_rights(query=query, category=category)
    return jsonify({"data": results, "count": len(results)})


@rights_bp.route("/<right_id>", methods=["GET"])
def get_right(right_id: str):
    """Retrieve a single right by ID."""
    result = get_right_by_id(right_id)
    return jsonify({"data": result})


@rights_bp.route("/external/<jurisdiction>", methods=["GET"])
def get_external_data(jurisdiction: str):
    """Fetch legal data from an external source for a given jurisdiction."""
    result = fetch_external_legal_data(jurisdiction)
    return jsonify({"data": result})


@rights_bp.route("/cases", methods=["POST"])
def create_case():
    """Submit a new legal case for a user."""
    body = request.get_json(silent=True)
    if body is None:
        raise ValidationError(
            message="Request body must be valid JSON.",
            field_errors={"body": "Expected a JSON object."},
        )

    user_id = body.get("user_id")
    case_data = body.get("case_data")

    result = save_user_case(user_id=user_id, case_data=case_data)
    return jsonify({"data": result}), 201
