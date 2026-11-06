"""Tests for the HiveBox endpoints."""  # describes the test file
from unittest.mock import patch  # lets us fake functions during a test

from app.main import app, VERSION  # the app and the version we test


def test_version():  # test 1
    """/version returns the version."""
    response = app.test_client().get("/version")  # call the endpoint like a browser would
    assert response.status_code == 200  # the call must succeed
    assert response.get_data(as_text=True) == VERSION  # the text must equal the version


@patch("app.main.BOX_IDS", ["a", "b"])  # pretend there are two boxes
@patch("app.main.get_temperature", side_effect=[10.0, 20.0])  # fake temperatures: 10 and 20
def test_temperature(_mock):  # test 2
    """/temperature returns the average."""
    response = app.test_client().get("/temperature")  # call the endpoint
    assert response.status_code == 200  # the call must succeed
    assert response.get_data(as_text=True) == "15.0"  # the average of 10 and 20 is 15


@patch("app.main.BOX_IDS", ["a"])  # pretend there is one box
@patch("app.main.get_temperature", return_value=None)  # fake: the box has no recent data
def test_temperature_no_data(_mock):  # test 3
    """/temperature returns 503 when there is no recent data."""
    response = app.test_client().get("/temperature")  # call the endpoint
    assert response.status_code == 503  # we expect "no data" status
    
    

