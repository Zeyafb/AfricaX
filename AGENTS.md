# AfricaX Guide

Local, CSV-backed Streamlit app for logging African restaurant visits + ratings
on a clickable Folium map, plus a "want to go" wishlist.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
pytest                      # data-layer tests
```

## Layout

- `app.py` — page composition + tabs. Streamlit only; no data logic.
- `data_store.py` — **the only module that touches `data/restaurants.csv`**.
  Schema, `RATERS`, `group_rating()`, load/save, CRUD, `visited()/wishlist()`.
- `mapview.py` — Folium map (3 states), click hit-test, legend, `load_geo()`.
- `ui.py` — KPIs, country detail, add/edit/mark-visited forms, leaderboard.
- `data/restaurants.csv` — visit + wishlist data.
- `data/ne_110m_admin_0_countries.*` — Natural Earth map geometry.

## Data schema (canonical order)

`Country, ISO_A3, Restaurant, Fayez, Muhammad, Seth, Ian, Shubham,
Group_Rating, Visit Date, Notes, Dishes, Status, Maps_URL`

- Per-person ratings are 1–10; blank means that person was absent.
- `Group_Rating` is **derived** (mean of present ratings) — never hand-edit it;
  `data_store` recomputes it on every load and save.
- `Status` is `visited` or `wishlist`. Wishlist rows have blank ratings/date and
  usually a `Maps_URL`.
- Dates are `MM/DD/YYYY`.

## Conventions

- Change data through `data_store` functions, not by rewriting the CSV by hand.
- African countries only; use the ISO-3 code from the shapefile (`GHA`, `SOM`, `SLE`, …).
- Keep the `Status`/ratings columns intact — the Sheets migration once dropped
  ratings; `tests/` guards against that regression.
- Do not commit or print secrets. There is **no** Google backend anymore; any
  leftover `*.json` key or `.streamlit/secrets.toml` is unused — delete it and
  revoke the key in Google Cloud.
