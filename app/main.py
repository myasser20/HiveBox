
"""HiveBox application entry point."""

import json
import os
from datetime import datetime, timedelta, timezone

import boto3
import requests
import valkey
from botocore.client import Config
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

CACHE_KEY = "hivebox:temperature"
CACHE_TTL = 300
MAX_AGE = timedelta(minutes=10)

S3_BUCKET = os.getenv("S3_BUCKET", "hivebox-data")

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv(
        "S3_ENDPOINT",
        "http://localhost:9000"
    ),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv(
        "S3_SECRET_KEY",
        "HiveBoxStorage2026!"
    ),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

cache = valkey.Valkey(
    host=os.getenv("VALKEY_HOST", "localhost"),
    port=int(os.getenv("VALKEY_PORT", "6379")),
    decode_responses=True
)

app = Flask(__name__)


def get_temperature(box_id):
    """Get the latest temperature from a SenseBox."""
    response = requests.get(
        f"{API_URL}{box_id}",
        timeout=10
    )
    response.raise_for_status()

    box = response.json()

    for sensor in box.get("sensors", []):
        last = sensor.get("lastMeasurement")

        if sensor.get("unit") == "°C" and last:
            measurement_time = datetime.fromisoformat(
                last["createdAt"].replace("Z", "+00:00")
            )

            age = datetime.now(timezone.utc) - measurement_time

            if timedelta(0) <= age <= timedelta(hours=1):
                return float(last["value"])

    return None


def get_status(avg):
    """Return the temperature status."""
    avg = float(avg)

    if avg < 10:
        return "Too Cold"

    if avg <= 36:
        return "Good"

    return "Too Hot"


def update_cache():
    """Fetch temperatures and update Valkey."""
    temps = []

    for box_id in BOX_IDS:
        try:
            value = get_temperature(box_id)

            if value is not None:
                temps.append(value)

        except (requests.RequestException, ValueError, KeyError):
            continue

    if not temps:
        return None

    avg = round(sum(temps) / len(temps), 2)

    data = {
        "average": str(avg),
        "status": get_status(avg),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    cache.setex(
        CACHE_KEY,
        CACHE_TTL,
        json.dumps(data)
    )

    return data


def store_data():
    """Store the latest cached data in Silo."""
    data = cache.get(CACHE_KEY)

    if not data:
        updated_data = update_cache()

        if updated_data is None:
            return None

        data = json.dumps(updated_data)

    filename = (
        "temperature/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=filename,
        Body=data,
        ContentType="application/json"
    )

    return filename


def is_cache_fresh():
    """Check whether cached data is no older than 10 minutes."""
    data = cache.get(CACHE_KEY)

    if not data:
        return False

    try:
        cached = json.loads(data)
        updated_at = datetime.fromisoformat(
            cached["updated_at"]
        )

        age = datetime.now(timezone.utc) - updated_at

        return timedelta(0) <= age <= MAX_AGE

    except (ValueError, KeyError, TypeError):
        return False


def are_boxes_available():
    """Check how many configured SenseBoxes are accessible."""
    if not BOX_IDS:
        return False

    unavailable = 0

    for box_id in BOX_IDS:
        try:
            if get_temperature(box_id) is None:
                unavailable += 1

        except (
            requests.RequestException,
            ValueError,
            KeyError
        ):
            unavailable += 1

    # Fail when more than half of the boxes are unavailable.
    required_failure_count = len(BOX_IDS) // 2 + 1

    return unavailable < required_failure_count


def is_storage_fresh():
    """Check whether the latest Silo object is no older than 10 minutes."""
    try:
        paginator = s3.get_paginator("list_objects_v2")

        latest = None

        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix="temperature/"
        ):
            for obj in page.get("Contents", []):
                if latest is None or obj["LastModified"] > latest:
                    latest = obj["LastModified"]

        if latest is None:
            return False

        age = datetime.now(timezone.utc) - latest

        return timedelta(0) <= age <= MAX_AGE

    except Exception:
        return False


@app.route("/version")
def version():
    """Return the application version."""
    return VERSION


@app.route("/temperature")
def temperature():
    """Return cached temperature or refresh it."""
    cached_data = cache.get(CACHE_KEY)

    if cached_data:
        return jsonify(json.loads(cached_data))

    data = update_cache()

    if data is None:
        return "No recent data", 503

    return jsonify(data)


@app.route("/cache")
def refresh_cache():
    """Force an immediate cache update."""
    data = update_cache()

    if data is None:
        return "No recent data", 503

    return jsonify(data)


@app.route("/store")
def store():
    """Force an immediate upload to Silo."""
    filename = store_data()

    if filename is None:
        return "No recent data", 503

    return jsonify({
        "message": "Data stored successfully",
        "file": filename
    })


@app.route("/metrics")
def metrics():
    """Return Prometheus metrics."""
    return generate_latest(), 200, {
        "Content-Type": CONTENT_TYPE_LATEST
    }


@app.route("/readyz")
def readyz():
    """Check whether the application is ready."""
    checks = {
        "senseboxes": are_boxes_available(),
        "cache": is_cache_fresh(),
        "storage": is_storage_fresh()
    }

    if all(checks.values()):
        return jsonify({
            "status": "ready",
            "checks": checks
        }), 200

    return jsonify({
        "status": "not ready",
        "checks": checks
    }), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
