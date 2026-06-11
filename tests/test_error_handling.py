"""Tests verifying that errors are properly handled and propagated.

Each test confirms that:
- The correct HTTP status code is returned.
- The response body is structured JSON with error code and message.
- Internal details (stack traces, DB errors, etc.) are never leaked.
"""

import json


class TestErrorHandling:
    """Verify centralized error handling works correctly."""

    def test_404_returns_structured_json(self, client):
        resp = client.get("/nonexistent-route")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_405_method_not_allowed(self, client):
        resp = client.delete("/health")
        assert resp.status_code == 405
        data = json.loads(resp.data)
        assert data["error"]["code"] == "HTTP_405"

    def test_health_check_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "healthy"


class TestRightsEndpoints:
    """Verify rights routes propagate errors correctly."""

    def test_list_rights_returns_data(self, client):
        resp = client.get("/api/rights/")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "data" in data
        assert "count" in data
        assert data["count"] > 0

    def test_get_right_by_valid_id(self, client):
        resp = client.get("/api/rights/amendment_1")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["title"] == "First Amendment"

    def test_get_right_by_invalid_id_returns_404(self, client):
        resp = client.get("/api/rights/nonexistent")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["error"]["code"] == "NOT_FOUND"

    def test_search_by_invalid_category_returns_400(self, client):
        resp = client.get("/api/rights/?category=invalid_cat")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "fields" in data["error"]

    def test_search_by_valid_category(self, client):
        resp = client.get("/api/rights/?category=constitutional")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert all(r["category"] == "constitutional" for r in data["data"])

    def test_external_service_error_returns_502(self, client):
        resp = client.get("/api/rights/external/california")
        assert resp.status_code == 502
        data = json.loads(resp.data)
        assert data["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
        # Verify internal error details are NOT leaked
        assert "ConnectionError" not in data["error"]["message"]
        assert "traceback" not in json.dumps(data).lower()

    def test_create_case_without_json_returns_400(self, client):
        resp = client.post("/api/rights/cases", data="not json")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_create_case_missing_fields_returns_400(self, client):
        resp = client.post(
            "/api/rights/cases",
            json={"user_id": "user123", "case_data": {"title": "Test"}},
        )
        assert resp.status_code == 400  # missing description
        data = json.loads(resp.data)
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_create_case_database_error_returns_503(self, client):
        resp = client.post(
            "/api/rights/cases",
            json={
                "user_id": "user123",
                "case_data": {"title": "Test", "description": "Test case"},
            },
        )
        assert resp.status_code == 503
        data = json.loads(resp.data)
        assert data["error"]["code"] == "DATABASE_ERROR"
        # Verify internal DB error details are NOT leaked
        assert "RuntimeError" not in data["error"]["message"]


class TestRequestIdPropagation:
    """Verify that every response includes a request ID for tracing."""

    def test_success_response_has_request_id(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers
        # UUID format check
        request_id = resp.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID length

    def test_error_response_has_request_id(self, client):
        resp = client.get("/api/rights/nonexistent")
        assert "X-Request-ID" in resp.headers
