"""App assembly: health check and router wiring."""

from app.main import create_app


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stream_route_is_mounted():
    paths = {route.path for route in create_app().routes}
    assert "/api/stream/prices" in paths
    assert "/api/portfolio" in paths
    assert "/api/portfolio/trade" in paths
    assert "/api/portfolio/history" in paths
    assert "/api/watchlist" in paths


def test_missing_static_dir_does_not_break_the_app(client):
    """Backend-only dev: the frontend build may not exist yet."""
    assert client.get("/api/health").status_code == 200
