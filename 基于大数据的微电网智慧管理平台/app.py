from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from microgrid.service import DataService

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")
service = DataService(raw_path=BASE_DIR / "data" / "raw_microgrid.csv", rows=180_000)
service.refresh(regenerate_raw=False)


def ok(data):
    return jsonify({"ok": True, "data": data})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return ok({"status": "running"})


@app.route("/api/stations")
def stations():
    return ok(service.stations())


@app.route("/api/overview")
def overview():
    return ok(service.overview())


@app.route("/api/trend")
def trend():
    station_id = request.args.get("station", "ALL")
    points = int(request.args.get("points", 2400))
    return ok(service.trend(station_id=station_id, points=points))


@app.route("/api/hourly-mix")
def hourly_mix():
    station_id = request.args.get("station", "ALL")
    return ok(service.hourly_mix(station_id=station_id))


@app.route("/api/alerts")
def alerts():
    station_id = request.args.get("station", "ALL")
    limit = int(request.args.get("limit", 12))
    return ok(service.alerts(station_id=station_id, limit=limit))


@app.route("/api/preprocess-report")
def preprocess_report():
    return ok(service.report)


@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    regenerate_raw = bool(request.args.get("regenerate", "").lower() in {"1", "true", "yes"})
    return ok(service.refresh(regenerate_raw=regenerate_raw))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
