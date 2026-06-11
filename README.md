# EQUALITY1 — 360 House Videos

A legal rights application and 360° virtual tour platform for real estate professionals. Cinematic, branded virtual tours with proper error handling throughout.

## Architecture

```
app/
  config.py                — Environment-aware configuration with startup validation
  create_app.py            — Application factory
  logging_config.py        — Centralized logging setup
  errors/
    exceptions.py          — Custom exception hierarchy (AppError base class)
    handlers.py            — Flask error handler registration
  middleware/
    request_logging.py     — Request/response logging with request ID tracing
  routes/
    health.py              — Health check endpoint
    pages.py               — Landing page and static pages
    rights.py              — Legal rights lookup API
    tours.py               — Tour creation, viewing, and asset serving
  services/
    rights_lookup.py       — Legal rights business logic
    tour_processing.py     — Panorama stitching, video generation, viewer creation
  templates/
    landing.html           — 360 House Videos landing page
main.py                    — Application entry point
app.yaml                   — Google App Engine deployment config
```

## Error Handling Design

Every layer follows these principles:

1. **No silent swallowing** — Exceptions are always logged before being converted to responses.
2. **Structured error responses** — All errors return `{"error": {"code": "...", "message": "..."}}` with the appropriate HTTP status code.
3. **Exception hierarchy** — All app errors extend `AppError`, caught by a single centralized handler.
4. **No internal leakage** — Stack traces, file paths, and system details are logged server-side but never sent to clients.
5. **Request tracing** — Every request gets a unique ID (`X-Request-ID` header) for correlating logs to errors.
6. **Startup validation** — Missing configuration raises errors at boot time, not at first request.
7. **XSS prevention** — User-supplied data is HTML-escaped before embedding in generated viewer pages.

### Tour-Specific Error Types

| Exception | HTTP | When |
|-----------|------|------|
| `ValidationError` | 400 | Missing form fields, invalid input |
| `FileUploadError` | 400 | Bad file type, no files uploaded |
| `StitchingError` | 422 | Not enough photos, insufficient overlap |
| `VideoProcessingError` | 422 | FFmpeg missing/failed, corrupted panorama |
| `TourNotFoundError` | 404 | Tour or asset doesn't exist |
| `TourProcessingError` | 500 | Background job failure |

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
| GET | `/` | Landing page |
| GET | `/health` | Health check |
| POST | `/create-tour` | Upload media and start tour processing |
| GET | `/tour/<realtor>/<job_id>` | View a completed tour |
| GET | `/tour/<realtor>/<job_id>/status` | Check tour processing status |
| GET | `/tour/<realtor>/<job_id>/<filename>` | Serve tour assets |
| GET | `/api/rights/` | List/search rights |
| GET | `/api/rights/<id>` | Get a specific right |

## Deployment

The frontend landing page runs on **Cloudflare Pages**. The backend API requires a server with FFmpeg and OpenCV:

```bash
# Google App Engine
gcloud app deploy app.yaml

# Or run with gunicorn
gunicorn -b :$PORT main:app
```

Set the `SECRET_KEY` environment variable in production.
