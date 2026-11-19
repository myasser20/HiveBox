
"""Tests for the HiveBox endpoints."""

from unittest.mock import patch

from app.main import app, VERSION


def client():
    """Create a Flask test client."""
    return app.test_client()


def test_version():
    """/version returns the application version."""
    response = client().get("/version")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == VERSION


@patch("app.main.BOX_IDS", ["a", "b"])
@patch("app.main.get_temperature", side_effect=[10.0, 20.0])
@patch("app.main.cache.get", return_value=None)
def test_temperature(_mock):
    """/temperature returns the average and its status."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert float(response.json["average"]) == 15.0
    assert response.json["status"] == "Good"

@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=None)
@patch("app.main.cache.get", return_value=None)
def test_temperature_no_data(_mock,_cache_mock):
    """/temperature returns 503 when there is no recent data."""
    response = client().get("/temperature")

    assert response.status_code == 503


@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=5.0)
@patch("app.main.cache.get", return_value=None)
def test_temperature_cold(_mock,_cache_mock):
    """Temperature below 10 returns Too Cold."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert response.json["status"] == "Too Cold"


@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=40.0)
@patch("app.main.cache.get", return_value=None)
def test_temperature_hot(_mock,_cache_mock):
    """Temperature above 37 returns Too Hot."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert response.json["status"] == "Too Hot"


def test_metrics():
    """/metrics returns default Prometheus metrics."""
    response = client().get("/metrics")

    assert response.status_code == 200
    assert b"python_info" in response.data

@patch("app.main.update_cache")
def test_cache(mock_update):
    """/cache forces an immediate cache update."""
    mock_update.return_value = {
        "average": "25.0",
        "status": "Good",
        "updated_at": "2026-11-20T00:00:00+00:00"
    }

    response = client().get("/cache")

    assert response.status_code == 200
    assert response.json["average"] == "25.0"
    mock_update.assert_called_once()


@patch("app.main.store_data", return_value="temperature/test.json")
def test_store(mock_store):
    """/store uploads data to Silo."""
    response = client().get("/store")

    assert response.status_code == 200
    assert response.json["file"] == "temperature/test.json"
    mock_store.assert_called_once()
@patch("app.main.are_boxes_available", return_value=True)
@patch("app.main.is_cache_fresh", return_value=True)
@patch("app.main.is_storage_fresh", return_value=True)
def test_readyz():
    """Ready endpoint returns 200 when all checks pass."""
    response = client().get("/readyz")

    assert response.status_code == 200
    assert response.json["status"] == "ready"


@patch("app.main.are_boxes_available", return_value=False)
@patch("app.main.is_cache_fresh", return_value=True)
@patch("app.main.is_storage_fresh", return_value=True)
def test_readyz_not_ready():
    """Ready endpoint returns 503 when a check fails."""
    response = client().get("/readyz")

    assert response.status_code == 503
    assert response.json["status"] == "not ready"
