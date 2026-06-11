"""Routes for 360 virtual tour creation and viewing.

All routes validate input and propagate errors through the centralized
error handler. No bare except blocks, no silent swallowing.
"""

import json
import logging
import os
import threading
import uuid

from flask import Blueprint, jsonify, request, send_file

from app.errors.exceptions import (
    FileUploadError,
    TourNotFoundError,
    TourProcessingError,
    ValidationError,
)
from app.services.tour_processing import (
    TOURS_FOLDER,
    UPLOAD_FOLDER,
    allowed_file,
    process_tour_job,
    slugify,
)
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

tours_bp = Blueprint("tours", __name__)


def _safe_tour_path(*segments: str) -> str:
    """Build a path under TOURS_FOLDER and verify it doesn't escape via traversal.

    Raises:
        ValidationError: If any segment contains path traversal characters.
    """
    for seg in segments:
        cleaned = secure_filename(seg)
        if not cleaned or cleaned != seg:
            raise ValidationError(
                message="Invalid path segment.",
                context={"segment": seg},
            )

    result = os.path.join(TOURS_FOLDER, *segments)
    abs_result = os.path.realpath(result)
    abs_base = os.path.realpath(TOURS_FOLDER)

    if not abs_result.startswith(abs_base + os.sep) and abs_result != abs_base:
        raise ValidationError(message="Invalid tour path.")

    return result


@tours_bp.route("/create-tour", methods=["POST"])
def create_tour():
    """Handle multi-bucket media upload and kick off tour processing.

    Validates all required fields before starting the background job.
    """
    realtor_name = request.form.get("realtorName", "").strip()
    address = request.form.get("address", "").strip()
    brokerage = request.form.get("brokerage", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()

    # --- Validate required fields (don't silently default) ---
    field_errors = {}
    if not realtor_name:
        field_errors["realtorName"] = "Realtor name is required."
    if not address:
        field_errors["address"] = "Property address is required."
    if not phone:
        field_errors["phone"] = "Phone number is required."
    if not email:
        field_errors["email"] = "Email is required."

    if field_errors:
        raise ValidationError(
            message="Missing required fields.",
            field_errors=field_errors,
        )

    # --- Process file uploads ---
    job_id = str(uuid.uuid4())[:8]
    upload_base = os.path.join(UPLOAD_FOLDER, job_id)
    total_files = 0

    buckets = ["int_photos", "int_video", "ext_photos", "ext_video"]
    for bucket_name in buckets:
        files = request.files.getlist(bucket_name)
        if not files or files[0].filename == "":
            continue

        bucket_path = os.path.join(upload_base, bucket_name)
        os.makedirs(bucket_path, exist_ok=True)

        for f in files:
            if not f.filename:
                continue

            # Validate file type for photo buckets
            if "photo" in bucket_name and not allowed_file(f.filename):
                raise FileUploadError(
                    message=f"File '{f.filename}' is not a supported image format.",
                    context={"filename": f.filename, "bucket": bucket_name},
                )

            safe_name = secure_filename(f.filename)
            if not safe_name:
                raise FileUploadError(
                    message=f"File '{f.filename}' has an invalid filename.",
                    context={"filename": f.filename},
                )

            f.save(os.path.join(bucket_path, safe_name))
            total_files += 1

    if total_files == 0:
        raise FileUploadError(
            message="No files were uploaded. Please upload at least one photo or video.",
        )

    # --- Save realtor photo ---
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename and photo.filename != "":
            os.makedirs(upload_base, exist_ok=True)
            photo.save(os.path.join(upload_base, "realtor_photo.jpg"))

    realtor_data = {
        "name": realtor_name,
        "brokerage": brokerage,
        "phone": phone,
        "email": email,
        "member_id": slugify(realtor_name),
    }

    # --- Start background processing ---
    thread = threading.Thread(
        target=process_tour_job,
        args=(job_id, upload_base, realtor_data, address),
        daemon=True,
    )
    thread.start()

    tour_url = f"/tour/{slugify(realtor_name)}/{job_id}"
    logger.info("Tour job started: job_id=%s, tour_url=%s", job_id, tour_url)

    return jsonify({
        "success": True,
        "job_id": job_id,
        "tour_url": tour_url,
    })


@tours_bp.route("/tour/<realtor>/<job_id>")
def serve_tour(realtor: str, job_id: str):
    """Serve the Pannellum viewer page for a completed tour."""
    tour_folder = _safe_tour_path(realtor, job_id)
    index_path = os.path.join(tour_folder, "index.html")

    if os.path.exists(index_path):
        return send_file(index_path)

    # Check processing status
    status_path = os.path.join(tour_folder, "status.json")
    if os.path.exists(status_path):
        try:
            with open(status_path, "r") as f:
                status = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read status.json for tour %s/%s: %s", realtor, job_id, exc)
            raise TourProcessingError(
                message="Unable to read tour status.",
                context={"realtor": realtor, "job_id": job_id},
            ) from exc

        if status.get("status") == "failed":
            raise TourProcessingError(
                message=status.get("error", "Tour processing failed."),
                context={"realtor": realtor, "job_id": job_id},
            )

        if status.get("status") == "completed" and os.path.exists(index_path):
            return send_file(index_path)

    # If no status file exists, the tour folder doesn't exist at all
    if not os.path.exists(tour_folder):
        raise TourNotFoundError(
            message=f"Tour '{realtor}/{job_id}' does not exist.",
            context={"realtor": realtor, "job_id": job_id},
        )

    # Still processing — return 202 Accepted
    return jsonify({
        "status": "processing",
        "message": "Tour is still being processed. Please refresh in a few moments.",
    }), 202


@tours_bp.route("/tour/<realtor>/<job_id>/<filename>")
def serve_asset(realtor: str, job_id: str, filename: str):
    """Serve tour assets (images, videos) to the Pannellum player."""
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValidationError(message="Invalid filename.")

    file_path = _safe_tour_path(realtor, job_id, safe_name)

    if not os.path.exists(file_path):
        raise TourNotFoundError(
            message=f"Asset '{filename}' not found for this tour.",
            context={"realtor": realtor, "job_id": job_id, "filename": filename},
        )

    return send_file(file_path)


@tours_bp.route("/tour/<realtor>/<job_id>/status")
def tour_status(realtor: str, job_id: str):
    """Check the processing status of a tour."""
    tour_folder = _safe_tour_path(realtor, job_id)
    status_path = os.path.join(tour_folder, "status.json")

    if not os.path.exists(status_path):
        if not os.path.exists(tour_folder):
            raise TourNotFoundError(
                message=f"Tour '{realtor}/{job_id}' does not exist.",
            )
        return jsonify({"status": "processing"})

    try:
        with open(status_path, "r") as f:
            status = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read status for %s/%s: %s", realtor, job_id, exc)
        raise TourProcessingError(
            message="Unable to read tour status.",
        ) from exc

    return jsonify(status)
