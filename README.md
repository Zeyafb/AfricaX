# AfricaX 🍽️ — African Restaurant Passport

A small, local Streamlit app where our group logs African restaurant visits on a
clickable map of Africa — with **per-person + group ratings** — and bookmarks
places we still **want to try**.

Data lives in one file: **`data/restaurants.csv`** (no cloud, no accounts).

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Features

- **Clickable Africa map** with three states: **visited** (green), **want to go**
  (amber, dashed border), and **not visited yet** (light). Hover shows visit
  count + average rating.
- **Per-person ratings** (1–10) for each friend, with the **group average**
  computed automatically and shown everywhere.
- **Wishlist** — bookmark a spot with a Google Maps link before you go, then
  **“Mark as visited”** to add ratings later.
- **Leaderboard** — top restaurants, countries by average, and each person’s
  favorite.
- **Accessible by design** — see below.

## Accessibility

- States differ by **lightness + hue + border style** (wishlist is dashed), not
  colour alone, so they’re distinguishable with colour-vision differences.
- The **sidebar country picker** is a full keyboard-only alternative to clicking
  the map; the **All spots** tab is a sortable table of everything.
- Rating inputs are labelled with help text; the group average is stated in text.

## Data (`data/restaurants.csv`)

| Column | Notes |
|---|---|
| `Country`, `ISO_A3` | Country name + ISO-3166 alpha-3 (e.g. `GHA`) |
| `Restaurant` | Name |
| `Fayez`, `Muhammad`, `Seth`, `Ian`, `Shubham` | Per-person rating 1–10 (blank = absent) |
| `Group_Rating` | **Derived** — mean of present ratings (recomputed on load/save) |
| `Visit Date` | `MM/DD/YYYY` |
| `Notes`, `Dishes` | Free text; dishes comma-separated |
| `Status` | `visited` or `wishlist` |
| `Maps_URL` | Optional Google Maps link |

## Project layout

| File | Responsibility |
|---|---|
| `app.py` | Page composition + tabs (Map / Leaderboard / Wishlist / All) |
| `data_store.py` | CSV load/save, schema, group-rating math, CRUD — **the only thing that touches the file** |
| `mapview.py` | Folium map, 3-state styling, click hit-test, legend |
| `ui.py` | KPIs, country detail, add/edit/mark-visited forms, leaderboard |
| `tests/` | `pytest` for the data layer (ratings survive round-trips, schema migration) |

```bash
pytest        # run the tests
```

## History

Briefly migrated to Google Sheets (mid-2026), which dropped per-person ratings
and added a service-account key. Backed out to local CSV — simpler, no secrets,
and it matches how the group actually uses it. If any Google artifacts remain
(`*.json`, `.streamlit/secrets.toml`), they’re unused and safe to delete; revoke
the service-account key in Google Cloud as hygiene.
