"""HiveBox app entry point."""
from datetime import datetime, timedelta, timezone  # tools to work with dates and times

import requests
import os
from flask import Flask, jsonify
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
VERSION = "v0.0.2"
BOX_IDS = os.getenv(
    "SENSEBOX_IDS",
    "5a905949bc2d4100199012b6"
).split(",")
API_URL = "https://api.opensensemap.org/boxes/"

app = Flask(__name__)


def get_temperature(box_id):
    """Get the temperature from the OpenSenseMap API for a given box ID."""
    response = requests.get(f"{API_URL}{box_id}", timeout=10)
    response.raise_for_status()
    box = response.json()
    for sensor in box["sensors"]:
        last = sensor.get("lastMeasurement")
        if sensor.get("unit") == "°C" and last:
            time = datetime.fromisoformat(last.get("createdAt").replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - time
            if age <= timedelta(hours=1):
                return float(last["value"])
    return None



@app.route("/version")  # this function answers requests to /version
def version():
    """Return the version of the app."""
    return VERSION  # send the version text back

def get_status(avg):
    avg = float(avg)

    if avg < 10:
        return "Too Cold"
    elif 11 <= avg <= 36:
        return "Good"
    elif avg > 37:
        return "Too Hot"

    return "Unknown"

@app.route("/temperature")  # this function answers requests to /temperature
def temperature():
    """Return the average temperature of all senseBoxes."""
    temps = []  # list that will hold the good temperatures
    for box_id in BOX_IDS:  # go through every box
        value = get_temperature(box_id)  # get this box's temperature
        if value is not None:  # skip boxes with no recent data
            temps.append(value)  # add the temperature to the list
    if not temps:  # if the list is empty
        return "No recent data", 503  # tell the caller no data is available
    
    avg =str(round(sum(temps) / len(temps), 2)) 
    return jsonify({"average": avg, "status": get_status(avg)}) # average, rounded to 2 decimals

@app.route("/metrics")
def metrics():
    """Return default Prometheus metrics."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":  # true only when you run this file directly
    app.run(host="0.0.0.0", port=5000)
