# EQUALITY1

A legal rights application ensuring citizens of the United States know their rights and are protected under the law. This interactive app provides law-based facts, detailed suggestions for your unique situation, and helps prepare paperwork necessary for court.

## Architecture

```
app/
  config.py            — Environment-aware configuration with startup validation
  create_app.py        — Application factory
  logging_config.py    — Centralized logging setup
  errors/
    exceptions.py      — Custom exception hierarchy (AppError base class)
    handlers.py        — Flask error handler registration
  middleware/
    request_logging.py — Request/response logging with request ID tracing
  routes/
    health.py          — Health check endpoint
    rights.py          — Legal rights lookup and case submission API
  services/
    rights_lookup.py   — Business logic with proper error propagation
tests/
  test_error_handling.py — Verifies errors are structured, propagated, and safe
main.py                — Application entry point
app.yaml               — Google App Engine deployment config
```

## Error Handling Design

Every layer follows these principles:

1. **No silent swallowing** — Exceptions are always logged before being converted to responses.
2. **Structured error responses** — All errors return `{"error": {"code": "...", "message": "..."}}` with the appropriate HTTP status code.
3. **Exception hierarchy** — All app errors extend `AppError`, caught by a single centralized handler.
4. **No internal leakage** — Stack traces, database errors, and connection details are logged server-side but never sent to clients.
5. **Request tracing** — Every request gets a unique ID (`X-Request-ID` header) for correlating logs to errors.
6. **Startup validation** — Missing configuration raises errors at boot time, not at first request.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py

# Run tests
pip install pytest
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/rights/` | List/search rights (`?q=...&category=...`) |
| GET | `/api/rights/<id>` | Get a specific right |
| GET | `/api/rights/external/<jurisdiction>` | Fetch external legal data |
| POST | `/api/rights/cases` | Submit a new case |

## Deployment

Configured for Google App Engine (Python 3.12):

```bash
gcloud app deploy app.yaml
```

Set the `SECRET_KEY` environment variable in production.
