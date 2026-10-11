"""Serve the Artifact Factory dashboard.

The dashboard is now a frontend page (``frontend/artifactfactory.html``) that
talks to this daemon's JSON API, so all frontend code lives in one place. This
module locates and returns that page; if it is missing (for example when the
frontend was not mounted), a tiny fallback page points at the JSON API.

The JSON API is unchanged; the dashboard is served at ``GET /`` and the old
service-info payload lives at ``GET /info``.
"""

import os


def _fallback() -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        "<title>Artifact Factory</title></head><body>"
        "<h1>Artifact Factory</h1>"
        "<p>The dashboard page was not found. The JSON API is available at "
        '<a href="/info">/info</a>.</p>'
        "</body></html>\n"
    )


def dashboard_html(frontend_dir: str) -> str:
    """Return the Artifact Factory dashboard page from the frontend directory."""
    path = os.path.join(frontend_dir, "artifactfactory.html")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return _fallback()