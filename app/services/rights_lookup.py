"""Service for looking up legal rights information.

Demonstrates proper error propagation:
- Validates inputs and raises ValidationError for bad data.
- Wraps external/data errors in domain-specific exceptions with context.
- Never swallows exceptions silently.
"""

import logging
from typing import Optional

from app.errors.exceptions import (
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

RIGHTS_DATABASE: dict = {
    "amendment_1": {
        "id": "amendment_1",
        "title": "First Amendment",
        "summary": "Protects freedom of speech, religion, press, assembly, and petition.",
        "category": "constitutional",
    },
    "amendment_4": {
        "id": "amendment_4",
        "title": "Fourth Amendment",
        "summary": "Protects against unreasonable searches and seizures.",
        "category": "constitutional",
    },
    "amendment_5": {
        "id": "amendment_5",
        "title": "Fifth Amendment",
        "summary": "Protects the right to due process and against self-incrimination.",
        "category": "constitutional",
    },
    "amendment_6": {
        "id": "amendment_6",
        "title": "Sixth Amendment",
        "summary": "Guarantees the right to a speedy and public trial.",
        "category": "constitutional",
    },
    "amendment_14": {
        "id": "amendment_14",
        "title": "Fourteenth Amendment",
        "summary": "Guarantees equal protection under the law and due process.",
        "category": "constitutional",
    },
    "miranda": {
        "id": "miranda",
        "title": "Miranda Rights",
        "summary": "Right to remain silent and right to an attorney during custodial interrogation.",
        "category": "procedural",
    },
}

VALID_CATEGORIES = {"constitutional", "procedural", "statutory", "regulatory"}


def get_right_by_id(right_id: str) -> dict:
    """Retrieve a specific legal right by its identifier.

    Raises:
        ValidationError: If right_id is empty or malformed.
        NotFoundError: If the right does not exist.
    """
    if not right_id or not right_id.strip():
        raise ValidationError(
            message="Right ID must not be empty.",
            field_errors={"right_id": "This field is required."},
        )

    right_id = right_id.strip().lower()

    result = RIGHTS_DATABASE.get(right_id)
    if result is None:
        raise NotFoundError(
            message=f"No legal right found with ID '{right_id}'.",
            context={"right_id": right_id},
        )
    return result


def search_rights(query: Optional[str] = None, category: Optional[str] = None) -> list:
    """Search legal rights by keyword or category.

    Raises:
        ValidationError: If category is not one of the recognized values.
    """
    if category and category.lower() not in VALID_CATEGORIES:
        raise ValidationError(
            message=f"Invalid category '{category}'.",
            field_errors={
                "category": f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}."
            },
        )

    results = list(RIGHTS_DATABASE.values())

    if category:
        results = [r for r in results if r["category"] == category.lower()]

    if query:
        query_lower = query.lower()
        results = [
            r
            for r in results
            if query_lower in r["title"].lower() or query_lower in r["summary"].lower()
        ]

    return results


def fetch_external_legal_data(jurisdiction: str) -> dict:
    """Placeholder for fetching data from an external legal API.

    Demonstrates wrapping external failures in ExternalServiceError
    with context for logging, while keeping the client message generic.

    Raises:
        ValidationError: If jurisdiction is empty.
        ExternalServiceError: If the external API call fails.
    """
    if not jurisdiction or not jurisdiction.strip():
        raise ValidationError(
            message="Jurisdiction is required.",
            field_errors={"jurisdiction": "This field is required."},
        )

    try:
        # Placeholder: in production this would call an external API
        raise ConnectionError("External legal data API is not yet configured.")
    except ConnectionError as exc:
        logger.error(
            "Failed to reach external legal data API for jurisdiction '%s': %s",
            jurisdiction,
            exc,
        )
        raise ExternalServiceError(
            message="Unable to fetch legal data at this time. Please try again later.",
            context={"jurisdiction": jurisdiction, "original_error": str(exc)},
        ) from exc


def save_user_case(user_id: str, case_data: dict) -> dict:
    """Placeholder for saving a user's case to the database.

    Demonstrates wrapping database failures in DatabaseError.

    Raises:
        ValidationError: If required fields are missing.
        DatabaseError: If the database operation fails.
    """
    if not user_id:
        raise ValidationError(
            message="User ID is required.",
            field_errors={"user_id": "This field is required."},
        )
    if not case_data:
        raise ValidationError(
            message="Case data must not be empty.",
            field_errors={"case_data": "This field is required."},
        )

    required_fields = {"title", "description"}
    missing = required_fields - set(case_data.keys())
    if missing:
        raise ValidationError(
            message="Missing required case fields.",
            field_errors={field: "This field is required." for field in missing},
        )

    try:
        # Placeholder: in production this would write to a database
        raise RuntimeError("Database connection not configured.")
    except RuntimeError as exc:
        logger.error("Failed to save case for user '%s': %s", user_id, exc)
        raise DatabaseError(
            message="Unable to save your case at this time. Please try again later.",
            context={"user_id": user_id, "original_error": str(exc)},
        ) from exc
