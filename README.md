# AI Fertilizer Recommender — Web Edition

A web app version of the original CLI fertilizer recommender: enter your
soil readings and conditions, get a fertilizer plan with estimated
quantities for your land size, and find nearby fertilizer/agro shops on a
map.

## What's new vs. the original CLI project

- **Web app** (Flask backend + HTML/CSS/JS frontend) instead of a terminal prompt.
- **More parameters**: soil moisture, temperature, humidity, rainfall, season (kharif/rabi/zaid), organic vs. chemical preference, and land area.
- **Quantity calculator** — estimates kg needed per fertilizer based on your land area (acres or hectares).
- **Organic mode** — swaps chemical recommendations (Urea, DAP, MOP) for organic equivalents (vermicompost, bone meal, wood ash, etc.).
- **Weather auto-fill** — one tap uses your location + Open-Meteo (free, no key) to fill in temperature/humidity/rainfall.
- **Map + "shops near me"** — uses your device location, a Leaflet map with OpenStreetMap tiles, and the free Overpass API to find and map nearby fertilizer/agro shops. No API key, no billing account, no signup required anywhere in this feature.
- **More crops** — rice, wheat, maize, vegetables, sugarcane, cotton, groundnut, pulses, banana, tomato, potato, onion, chili, tea, coffee.
- **Deploy-ready** for Render (Procfile, render.yaml, gunicorn).

The original rule-based logic (nutrient levels, pH thresholds, crop rules) is preserved and extended in `graph_builder.py`.

## Project structure

```
app.py                  Flask app: routes + API endpoints
graph_builder.py         Recommendation engine (rules + new parameters)
memory_store.py          Knowledge base + advice generator
utils.py                  Quantity calculator + free weather lookup
templates/index.html     Web UI
static/css/style.css      Styling
static/js/app.js          Frontend logic (form, map, geolocation)
requirements.txt          Core dependencies (lightweight, for deploy)
requirements-ai.txt       Optional: original FAISS + GPT-2 pipeline
Procfile / render.yaml    Deployment config for Render
.env.example                Environment variable template
```

## Note on the original FAISS + GPT-2 pipeline

GPT-2 + sentence-transformer embeddings + FAISS are heavy dependencies
(large downloads, real RAM/CPU use) and will likely fail to build or run
on free hosting tiers. By default the app runs on a fast rule-based
fallback for the "advice" text and a lightweight keyword-matching
fallback for the knowledge notes, so it works reliably out of the box.

If you want the full original AI pipeline, set `ENABLE_AI_ADVICE=true`
and install the extra dependencies:

```bash
pip install -r requirements.txt -r requirements-ai.txt
```

This needs more RAM than Render's free tier offers — use a paid instance
(or a host like Railway/Fly.io with more memory) if you enable it.

## Local setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Visit http://localhost:5000

## Map + nearby shops — how it works (no API key needed)

The map and shop search now run entirely on free, open infrastructure:

- **Map rendering**: [Leaflet.js](https://leafletjs.com/) (open-source JS library) loaded from a CDN, drawing standard [OpenStreetMap](https://www.openstreetmap.org/) tiles. No key, no signup, no billing account.
- **Shop search**: the [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) — OpenStreetMap's free query service. The backend (`utils.fetch_nearby_shops`) queries it for places tagged `shop=agrarian` (agricultural supply stores), `shop=garden_centre`, and `shop=farm` within an 8km radius, with a fallback mirror if the primary Overpass server is busy.

Trade-offs versus the earlier Google Places version, worth knowing:

- **Coverage depends on OpenStreetMap's data** in your area. In regions with an active OSM mapping community, results are excellent; in others, fewer shops may be tagged than would show up on Google Maps. Missing shops can be added by anyone at [openstreetmap.org](https://www.openstreetmap.org/) — a small nudge there benefits your app's results for everyone.
- **No star ratings or "open now" status** — that data isn't part of OpenStreetMap. The shop cards show name, address, and phone/website where mapped instead.
- **Overpass's public servers are shared and rate-limited.** Fine for normal personal/demo use; if you expect heavy traffic, consider adding a caching layer or self-hosting an Overpass instance.

If you'd rather use Mapbox instead of plain Leaflet+OSM (e.g. for nicer default styling or higher-volume geocoding), swap the tile layer URL in `static/js/app.js`'s `initMap()` for a Mapbox Static Tiles URL and add `NEXT_PUBLIC_MAPBOX_TOKEN`-style key handling back into `app.py`/`.env.example` — Mapbox's free tier (50k map loads/month) is generous, but it does require a signup and a key, which is why this build defaults to the fully keyless Leaflet+OSM path.

## Deploying to Render

1. Push this project to a GitHub repo.
2. In Render, click **New → Web Service**, connect the repo. Render will detect `render.yaml` automatically (or set Build Command `pip install -r requirements.txt` and Start Command `gunicorn app:app` manually).
3. `ENABLE_AI_ADVICE` is already set to `false` in `render.yaml` — leave it unless you've upgraded past the free tier. No other environment variables or API keys are required for this deploy.
4. Deploy. That's it — the map and nearby-shops feature work immediately on the live URL, no further key setup needed.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/` | Web UI |
| POST | `/api/recommend` | Run the recommendation engine |
| GET  | `/api/weather?lat=&lng=` | Auto-fill weather from location |
| GET  | `/api/nearby-shops?lat=&lng=&radius=` | Nearby fertilizer/agro shops (via Overpass API) |

## Disclaimer

Fertilizer dosage figures are general agronomy guidance for illustration.
Always confirm exact quantities with a local agricultural extension
office or accredited soil-testing lab before applying fertilizer on a
real farm.
