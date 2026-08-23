"""Tests for static frontend serving and API-route precedence (FOUND-03)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@pytest.fixture
def empty_static_dir():
    """Temporarily empty backend/static/ (minus .gitkeep) and restore after."""
    backup = _STATIC_DIR.parent / "static.bak"
    if _STATIC_DIR.exists():
        shutil.move(str(_STATIC_DIR), str(backup))
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    try:
        yield _STATIC_DIR
    finally:
        shutil.rmtree(_STATIC_DIR, ignore_errors=True)
        if backup.exists():
            shutil.move(str(backup), str(_STATIC_DIR))


@pytest.fixture
def static_dir_with_index():
    """Temporarily replace backend/static/ with a single known index.html."""
    backup = _STATIC_DIR.parent / "static.bak"
    if _STATIC_DIR.exists():
        shutil.move(str(_STATIC_DIR), str(backup))
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    marker = "finally-test-marker-index"
    (_STATIC_DIR / "index.html").write_text(f"<html><body>{marker}</body></html>")
    try:
        yield marker
    finally:
        shutil.rmtree(_STATIC_DIR, ignore_errors=True)
        if backup.exists():
            shutil.move(str(backup), str(_STATIC_DIR))


class TestStaticFrontend:
    """FOUND-03: FastAPI serves the static export while /api/* keeps precedence."""

    def test_api_health_answers_when_static_has_no_index(self, empty_static_dir, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["market_source"] == "simulator"

    def test_root_serves_index_html_when_present(self, static_dir_with_index, client):
        marker = static_dir_with_index
        response = client.get("/")
        assert response.status_code == 200
        assert marker in response.text

    def test_api_health_returns_json_not_html_fallback(self, static_dir_with_index, client):
        response = client.get("/api/health")
        assert response.headers["content-type"].startswith("application/json")

    def test_unknown_path_is_not_a_json_api_response(self, static_dir_with_index, client):
        response = client.get("/definitely-not-a-route")
        # An unmatched path must never be silently routed to a real API
        # handler that answers 200 -- a 404 (JSON or HTML) is acceptable.
        is_200_json = (
            response.status_code == 200
            and response.headers.get("content-type", "").startswith("application/json")
        )
        assert not is_200_json
