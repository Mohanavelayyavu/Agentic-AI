"""
graph_builder.py
Core recommendation logic. Builds on the original nutrient / pH / crop
rules and layers in extra agronomic parameters (soil moisture,
temperature, humidity, rainfall, season, organic vs chemical
preference) plus land-area based quantity estimates.
"""

from memory_store import FertilizerMemory
from utils import estimate_quantities

memory = FertilizerMemory()

CROP_RULES = {
    "rice": ["NPK fertilizer"],
    "wheat": ["Balanced NPK fertilizer"],
    "maize": ["Urea + DAP"],
    "vegetables": ["Compost + NPK fertilizer"],
    "sugarcane": ["NPK fertilizer", "Urea"],
    "cotton": ["Balanced NPK fertilizer"],
    "groundnut": ["Gypsum or Organic Compost", "DAP"],
    "pulses": ["DAP", "Compost + NPK fertilizer"],
    "banana": ["MOP / Potash", "Compost + NPK fertilizer"],
    "tomato": ["Balanced NPK fertilizer", "Compost + NPK fertilizer"],
    "potato": ["Balanced NPK fertilizer", "MOP / Potash"],
    "onion": ["Balanced NPK fertilizer"],
    "chili": ["Compost + NPK fertilizer"],
    "tea": ["Urea", "Compost + NPK fertilizer"],
    "coffee": ["Compost + NPK fertilizer"],
}

ORGANIC_ALTERNATIVES = {
    "Urea": "Vermicompost or Jeevamrutha (organic nitrogen source)",
    "DAP": "Bone meal or Rock phosphate (organic phosphorus source)",
    "MOP / Potash": "Wood ash or Banana-peel compost (organic potassium source)",
    "NPK fertilizer": "Well-rotted farmyard manure + compost blend",
    "Balanced NPK fertilizer": "Compost + vermicompost blend",
    "Urea + DAP": "Vermicompost + bone meal blend",
    "Compost + NPK fertilizer": "Compost + green manure",
    "Apply Lime (to increase soil pH)": "Wood ash (mild liming effect)",
    "Apply Gypsum or Organic Compost": "Organic compost only",
}


def _apply_organic_substitution(recommendations, farming_type):
    if farming_type != "organic":
        return recommendations
    return [ORGANIC_ALTERNATIVES.get(item, item) for item in recommendations]


def _environmental_tips(soil_moisture, temperature, humidity, rainfall, season):
    """Extra agronomic advice driven by the new environmental parameters."""
    tips = []

    if soil_moisture:
        sm = soil_moisture.lower()
        if sm == "low":
            tips.append("Soil moisture is low — irrigate before applying fertilizer so nutrients can dissolve and reach the root zone.")
        elif sm == "high":
            tips.append("Soil moisture is high — avoid heavy nitrogen doses right now, waterlogged soil increases nutrient runoff and root disease risk.")

    if temperature is not None:
        try:
            t = float(temperature)
            if t >= 35:
                tips.append("High temperature — apply fertilizer in the early morning or evening to reduce nitrogen loss through volatilization.")
            elif t <= 10:
                tips.append("Low temperature — nutrient uptake slows in cold soil; consider splitting the dose into smaller, more frequent applications.")
        except (TypeError, ValueError):
            pass

    if humidity is not None:
        try:
            h = float(humidity)
            if h >= 80:
                tips.append("High humidity — monitor for fungal disease, since excess nitrogen in humid conditions promotes leaf and stem fungal growth.")
        except (TypeError, ValueError):
            pass

    if rainfall is not None:
        try:
            r = float(rainfall)
            if r >= 50:
                tips.append("Heavy rainfall expected/received — split fertilizer into smaller doses to reduce leaching, especially for Urea.")
            elif r <= 5:
                tips.append("Low rainfall — pair fertilizer with organic compost or mulching to help the soil retain moisture.")
        except (TypeError, ValueError):
            pass

    if season:
        s = season.lower()
        if s == "kharif":
            tips.append("Kharif (monsoon) season — apply phosphorus and potassium at sowing, and top-dress nitrogen in split doses to survive heavy rain.")
        elif s == "rabi":
            tips.append("Rabi (winter) season — ensure adequate irrigation alongside fertilizer, since winter crops rely on irrigation rather than rain.")
        elif s == "zaid":
            tips.append("Zaid (summer) season — irrigate frequently and apply fertilizer in split doses to counter fast evaporation and heat stress.")

    return tips


def recommend_fertilizer(
    crop,
    nitrogen,
    phosphorus,
    potassium,
    ph,
    soil_moisture=None,
    temperature=None,
    humidity=None,
    rainfall=None,
    season=None,
    farming_type="chemical",
    land_area=None,
    area_unit="acre",
):
    recommendations = []

    # nutrient based recommendations
    if nitrogen.lower() == "low":
        recommendations.append("Urea")
    if phosphorus.lower() == "low":
        recommendations.append("DAP")
    if potassium.lower() == "low":
        recommendations.append("MOP / Potash")

    # pH recommendations
    ph = float(ph)
    if ph < 6:
        recommendations.append("Apply Lime (to increase soil pH)")
    if ph > 7.5:
        recommendations.append("Apply Gypsum or Organic Compost")

    # crop based suggestions
    crop_key = crop.lower().strip()
    recommendations.extend(CROP_RULES.get(crop_key, []))

    # if nothing matched
    if not recommendations:
        recommendations.append(memory.default_recommendation())

    # remove duplicates while preserving order
    unique_recommendations = list(dict.fromkeys(recommendations))

    # organic vs chemical preference
    unique_recommendations = _apply_organic_substitution(unique_recommendations, farming_type)
    unique_recommendations = list(dict.fromkeys(unique_recommendations))

    fertilizers_text = ", ".join(unique_recommendations)

    # quantity estimate based on land area (only meaningful for chemical dosage table)
    quantities = []
    if farming_type != "organic":
        quantities = estimate_quantities(unique_recommendations, land_area, area_unit)

    # environmental / seasonal tips
    tips = _environmental_tips(soil_moisture, temperature, humidity, rainfall, season)

    # Hugging Face + FAISS retrieval
    query = (
        f"Crop: {crop_key}, Nitrogen: {nitrogen}, Phosphorus: {phosphorus}, "
        f"Potassium: {potassium}, pH: {ph}, Season: {season}, "
        f"Farming type: {farming_type}"
    )
    context = memory.retrieve_context(query)

    # GPT-2 (or rule-based fallback) explanation
    advice = memory.generate_advice(
        crop=crop_key,
        nitrogen=nitrogen,
        phosphorus=phosphorus,
        potassium=potassium,
        ph=ph,
        fertilizers=fertilizers_text,
        context=context,
    )

    return {
        "fertilizers": fertilizers_text,
        "fertilizer_list": unique_recommendations,
        "quantities": quantities,
        "tips": tips,
        "context": context,
        "advice": advice,
    }
