"""Entry point for the EQUALITY1 application.

For local development: python main.py
For Google App Engine: gunicorn -b :$PORT main:app
"""

import sys

from app.create_app import create_app

app = create_app()

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=8080, debug=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        # Log fatal startup errors clearly rather than swallowing them
        import logging

        logging.critical("Failed to start application: %s", exc, exc_info=True)
        sys.exit(1)
