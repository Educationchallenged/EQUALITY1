"""Database service layer for the 360 House Videos application.

Wraps all SQLite operations with proper error handling:
- Connection failures raise DatabaseError (never silently ignored).
- Constraint violations (duplicate email, missing FK) raise ValidationError.
- All queries are parameterized to prevent SQL injection.
- Context managers ensure connections are always closed.
"""

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from app.errors.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "equality1.db")


@contextmanager
def get_connection():
    """Context manager for database connections.

    Ensures the connection is always closed, even if an error occurs.
    Enables WAL mode and foreign keys on every connection.

    Raises:
        DatabaseError: If the connection cannot be established.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error as exc:
        logger.error("Failed to connect to database at '%s': %s", DATABASE_PATH, exc)
        raise DatabaseError(
            message="Unable to connect to the database.",
            context={"db_path": DATABASE_PATH, "original_error": str(exc)},
        ) from exc

    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        error_msg = str(exc).lower()
        if "unique" in error_msg:
            raise ValidationError(
                message="A record with this value already exists.",
                context={"original_error": str(exc)},
            ) from exc
        if "foreign key" in error_msg:
            raise ValidationError(
                message="Referenced record does not exist.",
                context={"original_error": str(exc)},
            ) from exc
        raise DatabaseError(
            message="A database constraint was violated.",
            context={"original_error": str(exc)},
        ) from exc
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error("Database error: %s", exc)
        raise DatabaseError(
            message="A database error occurred.",
            context={"original_error": str(exc)},
        ) from exc
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema from schema.sql.

    Raises:
        DatabaseError: If schema cannot be applied.
    """
    schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "schema.sql")

    if not os.path.exists(schema_path):
        logger.warning("schema.sql not found at '%s', skipping DB init.", schema_path)
        return

    try:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
    except OSError as exc:
        raise DatabaseError(
            message="Failed to read database schema file.",
            context={"path": schema_path, "original_error": str(exc)},
        ) from exc

    with get_connection() as conn:
        conn.executescript(schema_sql)

    logger.info("Database initialized from schema.sql")


# ─── User Operations ─────────────────────────────────────────────────────────


def create_user(email: str, name: str = "", slug: Optional[str] = None) -> dict:
    """Create a new user.

    Raises:
        ValidationError: If email is empty or already exists.
        DatabaseError: On connection/write failure.
    """
    if not email or not email.strip():
        raise ValidationError(
            message="Email is required.",
            field_errors={"email": "This field is required."},
        )

    user_id = str(uuid.uuid4())
    api_key = str(uuid.uuid4())

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO users (id, email, name, slug, api_key)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, email.strip().lower(), name.strip(), slug, api_key),
        )

    logger.info("User created: id=%s, email=%s", user_id, email)
    return {"id": user_id, "email": email, "name": name, "api_key": api_key}


def get_user_by_email(email: str) -> dict:
    """Retrieve a user by email.

    Raises:
        NotFoundError: If no user exists with this email.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()

    if row is None:
        raise NotFoundError(
            message=f"No user found with email '{email}'.",
            context={"email": email},
        )

    return dict(row)


def get_user_by_api_key(api_key: str) -> dict:
    """Retrieve a user by API key (for Worker auth).

    Raises:
        NotFoundError: If the API key is invalid.
    """
    if not api_key:
        raise ValidationError(message="API key is required.")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE api_key = ?", (api_key,)
        ).fetchone()

    if row is None:
        raise NotFoundError(message="Invalid API key.")

    return dict(row)


def update_user_membership(user_id: str, member_status: int) -> None:
    """Update a user's membership status.

    Raises:
        ValidationError: If member_status is not valid.
        NotFoundError: If user doesn't exist.
    """
    if member_status not in (0, 1, 2):
        raise ValidationError(
            message="Invalid membership status. Must be 0, 1, or 2.",
            field_errors={"member_status": "Must be 0 (none), 1 (trial), or 2 (member)."},
        )

    with get_connection() as conn:
        result = conn.execute(
            "UPDATE users SET member_status = ? WHERE id = ?",
            (member_status, user_id),
        )
        if result.rowcount == 0:
            raise NotFoundError(message="User not found.")


# ─── Listing Operations ──────────────────────────────────────────────────────


def create_listing(
    user_id: str,
    address: str,
    price: Optional[int] = None,
    beds: Optional[int] = None,
    baths: Optional[float] = None,
    mls_number: Optional[str] = None,
    is_trial: bool = False,
) -> dict:
    """Create a new property listing.

    Raises:
        ValidationError: If required fields are missing or user_id is invalid.
        DatabaseError: On write failure.
    """
    field_errors = {}
    if not user_id:
        field_errors["user_id"] = "User ID is required."
    if not address or not address.strip():
        field_errors["address"] = "Property address is required."

    if field_errors:
        raise ValidationError(
            message="Missing required listing fields.",
            field_errors=field_errors,
        )

    listing_id = str(uuid.uuid4())

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO listings (id, user_id, address, price, beds, baths, mls_number, is_trial)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (listing_id, user_id, address.strip(), price, beds, baths, mls_number, int(is_trial)),
        )

    logger.info("Listing created: id=%s, address=%s", listing_id, address)
    return {"id": listing_id, "user_id": user_id, "address": address}


def get_listing(listing_id: str) -> dict:
    """Retrieve a listing by ID.

    Raises:
        NotFoundError: If listing doesn't exist.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()

    if row is None:
        raise NotFoundError(message="Listing not found.")

    return dict(row)


def get_user_listings(user_id: str) -> list:
    """Get all listings for a user."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def update_listing_panorama(
    listing_id: str,
    exterior_panorama: Optional[str] = None,
    interior_panorama: Optional[str] = None,
) -> None:
    """Update panorama paths on a listing.

    Raises:
        NotFoundError: If listing doesn't exist.
    """
    updates = []
    params = []

    if exterior_panorama is not None:
        updates.append("exterior_panorama = ?")
        params.append(exterior_panorama)
    if interior_panorama is not None:
        updates.append("interior_panorama = ?")
        params.append(interior_panorama)

    if not updates:
        return

    params.append(listing_id)

    with get_connection() as conn:
        result = conn.execute(
            f"UPDATE listings SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        if result.rowcount == 0:
            raise NotFoundError(message="Listing not found.")


# ─── Job Operations ──────────────────────────────────────────────────────────


VALID_JOB_STATUSES = {"pending", "partial", "completed", "failed"}


def create_job(user_id: str, listing_id: str, job_type: str) -> dict:
    """Create a processing job.

    Raises:
        ValidationError: If required fields are missing.
    """
    field_errors = {}
    if not user_id:
        field_errors["user_id"] = "Required."
    if not listing_id:
        field_errors["listing_id"] = "Required."
    if not job_type:
        field_errors["job_type"] = "Required."

    if field_errors:
        raise ValidationError(
            message="Missing required job fields.",
            field_errors=field_errors,
        )

    job_id = str(uuid.uuid4())

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO jobs (id, user_id, listing_id, job_type)
               VALUES (?, ?, ?, ?)""",
            (job_id, user_id, listing_id, job_type),
        )

    logger.info("Job created: id=%s, type=%s", job_id, job_type)
    return {"id": job_id, "status": "pending"}


def update_job_status(job_id: str, status: str) -> None:
    """Update a job's status.

    Raises:
        ValidationError: If status is not a valid value.
        NotFoundError: If job doesn't exist.
    """
    if status not in VALID_JOB_STATUSES:
        raise ValidationError(
            message=f"Invalid job status '{status}'.",
            field_errors={"status": f"Must be one of: {', '.join(sorted(VALID_JOB_STATUSES))}"},
        )

    completed_at = datetime.utcnow().isoformat() if status in ("completed", "failed") else None

    with get_connection() as conn:
        result = conn.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, job_id),
        )
        if result.rowcount == 0:
            raise NotFoundError(message="Job not found.")


def get_job(job_id: str) -> dict:
    """Retrieve a job by ID.

    Raises:
        NotFoundError: If job doesn't exist.
    """
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if row is None:
        raise NotFoundError(message="Job not found.")

    return dict(row)


# ─── Free Token Operations ───────────────────────────────────────────────────


def create_free_token(email: str, address: str, expires_hours: int = 72) -> dict:
    """Generate a free trial token.

    Raises:
        ValidationError: If email or address is empty.
    """
    field_errors = {}
    if not email or not email.strip():
        field_errors["email"] = "Email is required."
    if not address or not address.strip():
        field_errors["address"] = "Address is required."

    if field_errors:
        raise ValidationError(
            message="Missing required fields for free token.",
            field_errors=field_errors,
        )

    token = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO free_tokens (token, email, address, expires_at)
               VALUES (?, ?, ?, ?)""",
            (token, email.strip().lower(), address.strip(), expires_at),
        )

    logger.info("Free token created for email=%s", email)
    return {"token": token, "expires_at": expires_at}


def redeem_free_token(token: str) -> dict:
    """Redeem a free trial token.

    Raises:
        NotFoundError: If token doesn't exist.
        ValidationError: If token is expired or already used.
    """
    if not token:
        raise ValidationError(message="Token is required.")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM free_tokens WHERE token = ?", (token,)
        ).fetchone()

        if row is None:
            raise NotFoundError(message="Invalid or expired token.")

        token_data = dict(row)

        if token_data["used"]:
            raise ValidationError(message="This token has already been used.")

        if datetime.fromisoformat(token_data["expires_at"]) < datetime.utcnow():
            raise ValidationError(message="This token has expired.")

        conn.execute(
            "UPDATE free_tokens SET used = 1 WHERE token = ?", (token,)
        )

    logger.info("Free token redeemed: token=%s", token)
    return token_data
