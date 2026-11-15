
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
def test_temperature(_mock):
    """/temperature returns the average and its status."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert float(response.json["average"]) == 15.0
    assert response.json["status"] == "Good"

@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=None)
def test_temperature_no_data(_mock):
    """/temperature returns 503 when there is no recent data."""
    response = client().get("/temperature")

    assert response.status_code == 503


@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=5.0)
def test_temperature_cold(_mock):
    """Temperature below 10 returns Too Cold."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert response.json["status"] == "Too Cold"


@patch("app.main.BOX_IDS", ["a"])
@patch("app.main.get_temperature", return_value=40.0)
def test_temperature_hot(_mock):
    """Temperature above 37 returns Too Hot."""
    response = client().get("/temperature")

    assert response.status_code == 200
    assert response.json["status"] == "Too Hot"


def test_metrics():
    """/metrics returns default Prometheus metrics."""
    response = client().get("/metrics")

    assert response.status_code == 200
    assert b"python_info" in response.data
