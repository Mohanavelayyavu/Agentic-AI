"""
app.py
Flask web app for the AI Fertilizer Recommender.

Routes:
  GET  /                   -> the web UI
  POST /api/recommend      -> run the recommendation engine
  GET  /api/weather        -> auto-fill temperature/humidity/rainfall from lat/lng (Open-Meteo, free)
  GET  /api/nearby-shops   -> nearby fertilizer / agro shops via OpenStreetMap Overpass API (free, no key)

Map rendering (Leaflet + OpenStreetMap tiles) and shop lookup (Overpass API)
both require no API key and no billing account, so there's no /api/config
route or key handling needed anywhere in this app.
"""

import os
from flask import Flask, jsonify, render_template, request

from graph_builder import recommend_fertilizer
from utils import fetch_weather, fetch_nearby_shops

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommend", methods=["POST"])
def recommend():
    data = request.get_json(force=True, silent=True) or {}

    required = ["crop", "nitrogen", "phosphorus", "potassium", "ph"]
    missing = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    try:
        ph = float(data["ph"])
        if not (1 <= ph <= 14):
            return jsonify({"error": "Soil pH must be between 1 and 14."}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Soil pH must be a number."}), 400

    try:
        result = recommend_fertilizer(
            crop=data["crop"],
            nitrogen=data["nitrogen"],
            phosphorus=data["phosphorus"],
            potassium=data["potassium"],
            ph=ph,
            soil_moisture=data.get("soil_moisture"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            rainfall=data.get("rainfall"),
            season=data.get("season"),
            farming_type=data.get("farming_type", "chemical"),
            land_area=data.get("land_area"),
            area_unit=data.get("area_unit", "acre"),
        )
        return jsonify(result)
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": f"Could not generate a recommendation: {exc}"}), 500


@app.route("/api/weather")
def weather():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    if not lat or not lng:
        return jsonify({"error": "lat and lng query params are required."}), 400

    result = fetch_weather(lat, lng)
    if result is None:
        return jsonify({"error": "Weather lookup failed. Please enter values manually."}), 502
    return jsonify(result)


@app.route("/api/nearby-shops")
def nearby_shops():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    radius = request.args.get("radius", "8000")  # meters, ~5 miles default

    if not lat or not lng:
        return jsonify({"error": "lat and lng query params are required."}), 400

    try:
        radius = int(float(radius))
    except (TypeError, ValueError):
        radius = 8000

    try:
        shops = fetch_nearby_shops(float(lat), float(lng), radius_m=radius)
    except Exception as exc:
        return jsonify({
            "error": "Couldn't reach OpenStreetMap's shop directory right now "
                     f"({exc}). Please try again in a moment."
        }), 502

    return jsonify({"shops": shops})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
