"""HiveBox app entry point."""
from datetime import datetime, timedelta, timezone  # tools to work with dates and times

import requests
from flask import Flask# the web framework we use to make the app
VERSION = "v0.0.2"
BOX_IDS=["5a905949bc2d4100199012b6"]
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
    return str(round(sum(temps) / len(temps), 2))  # average, rounded to 2 decimals


if __name__ == "__main__":  # true only when you run this file directly
    app.run(host="0.0.0.0", port=5000)
