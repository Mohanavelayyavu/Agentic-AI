"""
utils.py
Helper functions shared across the app: unit conversion, fertilizer
quantity estimation, and free weather lookups (Open-Meteo, no API key
required) used to auto-fill temperature / humidity / rainfall fields.
"""

import requests

# Rough standard dosage guidance in kg per acre. These are general
# agronomy ballpark figures meant for illustration -- always defer to
# a local agricultural extension office / soil-testing lab for exact
# dosage on a real farm.
DOSAGE_PER_ACRE_KG = {
    "Urea": 45,
    "DAP": 40,
    "MOP / Potash": 20,
    "NPK fertilizer": 50,
    "Balanced NPK fertilizer": 50,
    "Urea + DAP": 60,
    "Compost + NPK fertilizer": 100,
    "Apply Lime (to increase soil pH)": 200,
    "Apply Gypsum or Organic Compost": 150,
}

ACRE_TO_HECTARE = 0.404686


def print_separator():
    print("-" * 60)


def normalize_area_to_acres(area_value, area_unit):
    """Convert a land-area value into acres."""
    if area_value is None:
        return None
    area_value = float(area_value)
    if area_unit == "hectare":
        return area_value / ACRE_TO_HECTARE
    return area_value  # already acres


def estimate_quantities(fertilizer_names, area_value, area_unit):
    """
    Given a list of fertilizer/amendment names and a land area,
    estimate how many kg of each are needed.
    Returns a list of dicts: {name, kg_per_acre, estimated_kg}
    """
    if not area_value:
        return []

    acres = normalize_area_to_acres(area_value, area_unit)
    estimates = []
    for name in fertilizer_names:
        per_acre = DOSAGE_PER_ACRE_KG.get(name)
        if per_acre is None:
            continue
        estimates.append(
            {
                "name": name,
                "kg_per_acre": per_acre,
                "estimated_kg": round(per_acre * acres, 1),
            }
        )
    return estimates


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# OSM tags that map to fertilizer / agricultural-supply / garden-supply shops.
SHOP_TAGS = ["agrarian", "garden_centre", "farm"]


def _format_osm_address(tags):
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:suburb"),
        tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
    ]
    address = " ".join(p for p in parts if p)
    return address or tags.get("addr:full") or ""


def fetch_nearby_shops(lat, lng, radius_m=8000, limit=20):
    """
    Find nearby fertilizer / agro-supply / garden-centre shops using the
    free OpenStreetMap Overpass API. No API key required.

    Returns a list of dicts: {name, address, lat, lng, shop_type, phone, website}
    or raises an exception if every mirror fails (caller handles the error).
    """
    tag_filter = "".join(
        f'  node["shop"="{t}"](around:{radius_m},{lat},{lng});\n'
        f'  way["shop"="{t}"](around:{radius_m},{lat},{lng});\n'
        for t in SHOP_TAGS
    )
    query = f"""
    [out:json][timeout:20];
    (
    {tag_filter}
    );
    out center tags;
    """

    last_error = None
    elements = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "agentic-ai-fertilizer-app/1.0"},
                timeout=20,
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
        except Exception as exc:
            last_error = exc
            elements = None
            continue

    if elements is None:
        raise last_error or RuntimeError("Overpass API unavailable")

    shops = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue  # skip unnamed nodes, not useful to show a user
        shop_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        shop_lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if shop_lat is None or shop_lng is None:
            continue
        shops.append(
            {
                "name": name,
                "address": _format_osm_address(tags),
                "lat": shop_lat,
                "lng": shop_lng,
                "shop_type": tags.get("shop"),
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "website": tags.get("website") or tags.get("contact:website"),
            }
        )

    # Sort roughly by proximity (planar approximation is fine at this scale)
    shops.sort(key=lambda s: (s["lat"] - lat) ** 2 + (s["lng"] - lng) ** 2)
    return shops[:limit]


def fetch_weather(lat, lng):
    """
    Free, no-key weather lookup via Open-Meteo, used to auto-fill
    temperature / humidity / rainfall on the form when the user shares
    their location. Returns None on any failure so the caller can fall
    back to manual entry gracefully.
    """
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lng,
                "current": "temperature_2m,relative_humidity_2m,precipitation",
                "timezone": "auto",
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json().get("current", {})
        if not data:
            return None
        return {
            "temperature_c": data.get("temperature_2m"),
            "humidity_pct": data.get("relative_humidity_2m"),
            "rainfall_mm": data.get("precipitation"),
        }
    except Exception:
        return None
