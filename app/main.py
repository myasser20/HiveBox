
"""HiveBox app entry point."""

import os
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

VERSION = "v0.0.2"
API_URL = "https://api.opensensemap.org/boxes/"

BOX_IDS = [
    box_id.strip()
    for box_id in os.getenv(
        "SENSEBOX_IDS",
        "5a905949bc2d4100199012b6"
    ).split(",")
    if box_id.strip()
]

app = Flask(__name__)


def get_temperature(box_id):
    """Get the latest temperature from an OpenSenseMap box."""
    response = requests.get(f"{API_URL}{box_id}", timeout=10)
    response.raise_for_status()
    box = response.json()

    for sensor in box["sensors"]:
        last = sensor.get("lastMeasurement")

        if sensor.get("unit") == "°C" and last:
            measurement_time = datetime.fromisoformat(
                last["createdAt"].replace("Z", "+00:00")
            )

            age = datetime.now(timezone.utc) - measurement_time

            if timedelta(0) <= age <= timedelta(hours=1):
                return float(last["value"])

    return None


@app.route("/version")
def version():
    """Return the application version."""
    return VERSION


def get_status(avg):
    """Return the status based on the average temperature."""
    avg = float(avg)

    if avg < 10:
        return "Too Cold"

    if avg <= 36:
        return "Good"

    return "Too Hot"


@app.route("/temperature")
def temperature():
    """Return the average temperature of all senseBoxes."""
    temps = []

    for box_id in BOX_IDS:
        value = get_temperature(box_id)

        if value is not None:
            temps.append(value)

    if not temps:
        return "No recent data", 503

    avg = round(sum(temps) / len(temps), 2)

    return jsonify({
        "average": str(avg),
        "status": get_status(avg)
    })


@app.route("/metrics")
def metrics():
    """Return default Prometheus metrics."""
    return generate_latest(), 200, {
        "Content-Type": CONTENT_TYPE_LATEST
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
