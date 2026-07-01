# AfricaX Guide

Local, CSV-backed Streamlit app for logging African restaurant visits on a
clickable Folium map, **ranking** them by group consensus, plus a "want to go"
wishlist. Consensus uses the Movie Ranks median-of-percentiles method.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
pytest                      # data-layer + consensus tests
```

## Layout

- `app.py` — sidebar-nav routing + header + KPI row + page dispatch. Streamlit only.
- `data_store.py` — **the only module that touches `data/restaurants.csv`**.
  Schema, `RATERS`, `set_ranking()`, load/save, CRUD, `visited()/wishlist()`.
- `rankings.py` — consensus: `normalize_rank()`, `consensus()`, `consensus_table()`,
  `rankings_from_df()`. Ported from `Movie Ranks/2026/calculate_rankings.py`.
- `mapview.py` — Folium map (3 states, country labels), click hit-test, legend, `load_geo()`.
- `ui.py` — header/avatars, KPI cards, sidebar, country detail, **My Rankings** editor,
  leaderboard, add/edit/mark-visited forms.
- `data/restaurants.csv` — visit + wishlist data.
- `data/ne_110m_admin_0_countries.*` — Natural Earth map geometry.

## Data schema (canonical order)

`Country, ISO_A3, Restaurant, Fayez, Muhammad, Seth, Ian, Shubham,
Visit Date, Notes, Dishes, Status, Maps_URL`

- Per-person columns hold that member's **rank** of the restaurant (1 = favourite);
  **blank = not ranked**. They are integers, not 1–10 scores.
- **No `Group_Rating` column.** Consensus (median of normalised ranks → overall rank)
  is computed in `rankings.py` and shown as `median ÷ 10` = an X/10 star.
- `Status` is `visited` or `wishlist`. Wishlist rows have blank ranks/date, usually a `Maps_URL`.
- Dates are `MM/DD/YYYY`.

## Setting rankings

Members normally rank in-app on the **My Rankings** page. Programmatically, rewrite a
member's whole column from an ordered list (favourite first):

```python
import data_store as ds
ds.set_ranking("Fayez", ["Chez Dior", "Fettoosh", "King Of Koshary"])  # renumbers 1..N
```

`set_ranking` renumbers cleanly and blanks anything not in the list for that member.

## Conventions

- Change data through `data_store` functions, not by rewriting the CSV by hand.
- African countries only; use the ISO-3 code from the shapefile (`GHA`, `SOM`, `SLE`, …).
- Per-person columns are **ranks now, not ratings** — a prior version stored 1–10
  ratings; `tests/` guards the ranking round-trip + consensus math.
- Do not commit or print secrets. There is **no** Google backend; any leftover
  `*.json` key or `.streamlit/secrets.toml` is unused — delete it and revoke the key.
