# AfricaX 🍴 — African Restaurant Passport

A small, local Streamlit app where our group logs African restaurant visits on a
clickable map of Africa, **ranks** the places we've been, and bookmarks spots we
still **want to try**. Group standing is by **consensus ranking** — not 1–10
ratings — using the median-of-normalised-orders method borrowed from our Movie
Ranks project.

Data lives in one file: **`data/restaurants.csv`** (no cloud, no accounts).

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## How ranking works

There are **no star ratings**. Instead, each member puts the places they've been
in **order** (favourite first) on the **My Rankings** page. The app then:

1. Turns each person's rank into a 0–100 percentile *within their own list*
   (`100 × (size − rank) / (size − 1)`), so a list of 3 and a list of 20 compare fairly.
2. Scores each restaurant by the **median** of those percentiles (median, so one
   contrarian can't sink a group favourite).
3. Orders restaurants by that median → the **overall rank**.

For a familiar read, the median is shown as an **X/10 star** (median ÷ 10).

## Features

- **Clickable Africa map** — three states: **visited** (green), **wishlist**
  (purple), **not visited** (grey), with a permanent name label on every lit
  country and a light-blue ocean.
- **My Rankings** — the built-in input where each member numbers their visited
  spots (1 = favourite); saving rebuilds the group consensus live.
- **Leaderboard** — the consensus overall ranking + each person's #1.
- **Wishlist** — bookmark a spot with a Google Maps link, then **Mark as visited**.
- **Dashboard** — sidebar nav, KPI cards (countries/places/wishlist/group score),
  member avatars, and a tabbed country detail panel.
- **Accessible by design** — see below.

## Accessibility

- Map states differ by **lightness + hue** and every lit country is **labelled in
  text**, so nothing relies on colour alone.
- The **sidebar country filter** is a full keyboard-only alternative to clicking
  the map; **All Spots** is a sortable table of everything with overall ranks.
- Inputs are labelled; the consensus score and overall rank are stated in text.

## Data (`data/restaurants.csv`)

| Column | Notes |
|---|---|
| `Country`, `ISO_A3` | Country name + ISO-3166 alpha-3 (e.g. `GHA`) |
| `Restaurant` | Name |
| `Fayez`, `Muhammad`, `Seth`, `Ian`, `Shubham` | Each member's **rank** (1 = favourite). Blank = not ranked. |
| `Visit Date` | `MM/DD/YYYY` |
| `Notes`, `Dishes` | Free text; dishes comma-separated |
| `Status` | `visited` or `wishlist` |
| `Maps_URL` | Optional Google Maps link |

There is **no `Group_Rating` column** — consensus is computed on the fly in `rankings.py`.

## Project layout

| File | Responsibility |
|---|---|
| `app.py` | Sidebar-nav routing + header + KPI row + page dispatch |
| `data_store.py` | CSV load/save, schema, `set_ranking()`, CRUD — **the only thing that touches the file** |
| `rankings.py` | Consensus scoring (normalise → median → overall rank), ported from Movie Ranks |
| `mapview.py` | Folium map, 3-state styling, country labels, click hit-test, legend |
| `ui.py` | Header/avatars, KPI cards, sidebar, detail panel, My Rankings, leaderboard, forms |
| `tests/` | `pytest` for the data layer + the consensus method |

```bash
pytest        # run the tests
```

## History

Briefly migrated to Google Sheets (mid-2026), which dropped per-person data and
added a service-account key; backed out to local CSV. Then moved from 1–10 group
ratings to **consensus rankings** (this version). If any Google artifacts remain
(`*.json`, `.streamlit/secrets.toml`), they're unused and safe to delete; revoke
the service-account key in Google Cloud as hygiene.
