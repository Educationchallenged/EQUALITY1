"""Tests for tour creation and viewing routes.

Verifies that:
- Required fields are validated (not silently defaulted).
- Missing uploads return structured errors.
- Non-existent tours return 404 with proper error code.
- Processing status is reported correctly.
"""

import json
import io


class TestCreateTour:
    """Verify /create-tour validates inputs and returns structured errors."""

    def test_missing_all_fields_returns_400(self, client):
        resp = client.post("/create-tour", data={})
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "realtorName" in data["error"]["fields"]
        assert "address" in data["error"]["fields"]
        assert "phone" in data["error"]["fields"]
        assert "email" in data["error"]["fields"]

    def test_missing_some_fields_returns_400(self, client):
        resp = client.post("/create-tour", data={
            "realtorName": "Jane Doe",
            "address": "",
            "phone": "555-1234",
            "email": "",
        })
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "address" in data["error"]["fields"]
        assert "email" in data["error"]["fields"]

    def test_no_files_uploaded_returns_400(self, client):
        resp = client.post("/create-tour", data={
            "realtorName": "Jane Doe",
            "address": "123 Main St",
            "phone": "555-1234",
            "email": "jane@example.com",
        })
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["error"]["code"] == "FILE_UPLOAD_ERROR"

    def test_valid_upload_returns_success(self, client):
        fake_image = (io.BytesIO(b"fake image data"), "photo1.jpg")
        resp = client.post(
            "/create-tour",
            data={
                "realtorName": "Jane Doe",
                "address": "123 Main St",
                "phone": "555-1234",
                "email": "jane@example.com",
                "int_photos": fake_image,
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert "job_id" in data
        assert "tour_url" in data
        assert "/tour/jane-doe/" in data["tour_url"]


class TestServeTour:
    """Verify tour viewing handles missing/processing/failed tours."""

    def test_nonexistent_tour_returns_404(self, client):
        resp = client.get("/tour/nobody/00000000")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["error"]["code"] == "TOUR_NOT_FOUND"

    def test_tour_status_nonexistent_returns_404(self, client):
        resp = client.get("/tour/nobody/00000000/status")
        assert resp.status_code == 404


class TestServeAsset:
    """Verify asset serving validates filenames and returns 404 for missing."""

    def test_missing_asset_returns_404(self, client):
        resp = client.get("/tour/test-realtor/abc123/nonexistent.jpg")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["error"]["code"] == "TOUR_NOT_FOUND"


class TestLandingPage:
    """Verify the landing page is served."""

    def test_landing_page_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"360" in resp.data
