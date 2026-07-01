"""AfricaX map layer — Folium choropleth of Africa with 3 visit states.

Accessibility notes:
- The three states differ in **lightness + hue + border style** (wishlist uses a
  dashed border), so they are distinguishable without relying on colour alone.
- Every state is also reachable without the map (sidebar country picker + tables
  in ``ui.py``), and hover tooltips carry the same info as text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import folium
import geopandas as gpd
import streamlit as st
from shapely.geometry import Point

from data_store import STATUS_VISITED, STATUS_WISHLIST

_SHP = Path(__file__).parent / "data" / "ne_110m_admin_0_countries.shp"

# Colour-vision-safe-ish palette: differ in lightness AND hue, wishlist dashed.
STATE_STYLE = {
    STATUS_VISITED: {"fill": "#2E7D5B", "border": "#12513A", "dash": None, "weight": 2.0, "opacity": 0.82},
    STATUS_WISHLIST: {"fill": "#2F80C7", "border": "#17456F", "dash": "6,4", "weight": 2.6, "opacity": 0.80},
    "unvisited": {"fill": "#ECE6D9", "border": "#C4B393", "dash": None, "weight": 0.8, "opacity": 0.55},
}
HOVER = {"weight": 3.2, "color": "#1A1A1A", "fillOpacity": 0.9}


@st.cache_data(show_spinner=False)
def load_geo() -> gpd.GeoDataFrame:
    """Load the Natural Earth shapefile, keep Africa, standardise name/iso."""
    if not _SHP.exists():
        st.error("Missing map data: data/ne_110m_admin_0_countries.shp (+ sidecar files).")
        st.stop()

    gdf = gpd.read_file(_SHP)

    cont = next((c for c in ["CONTINENT", "continent", "REGION_UN"] if c in gdf.columns), None)
    if cont:
        gdf = gdf[gdf[cont].astype(str).str.strip().str.lower() == "africa"]

    name_col = next((c for c in ["NAME", "ADMIN", "name"] if c in gdf.columns), None)
    iso_col = next((c for c in ["ISO_A3", "ADM0_A3", "iso_a3"] if c in gdf.columns), None)
    if not name_col or not iso_col:
        st.error("Shapefile missing expected NAME/ISO_A3 columns.")
        st.stop()

    africa = (
        gdf[[name_col, iso_col, "geometry"]]
        .rename(columns={name_col: "name", iso_col: "iso_a3"})
        .copy()
    )
    africa["name"] = africa["name"].astype(str).str.strip()
    africa["iso_a3"] = africa["iso_a3"].astype(str).str.upper().str.strip()
    return africa.reset_index(drop=True)


def _tooltip(status: Optional[str], stat: Optional[dict]) -> str:
    if status == STATUS_VISITED and stat:
        avg = f" · avg {stat['avg']}/10" if stat.get("avg") is not None else ""
        n = stat.get("visited", 0)
        return f"Visited · {n} place{'s' if n != 1 else ''}{avg}"
    if status == STATUS_WISHLIST and stat:
        n = stat.get("wishlist", 0)
        return f"On the wishlist · {n} spot{'s' if n != 1 else ''}"
    return "Not visited yet"


def build_map(
    africa: gpd.GeoDataFrame,
    status_by_iso: dict,
    stats_by_iso: dict,
) -> folium.Map:
    """Render the choropleth. Feature props carry name + status label for a11y."""
    feats = africa.copy()
    feats["state"] = feats["iso_a3"].map(lambda i: status_by_iso.get(i, "unvisited"))
    feats["tip"] = feats.apply(
        lambda r: _tooltip(status_by_iso.get(r["iso_a3"]), stats_by_iso.get(r["iso_a3"])),
        axis=1,
    )

    minx, miny, maxx, maxy = feats.total_bounds
    m = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=3,
        tiles="cartodbvoyager",
        prefer_canvas=True,
        no_wrap=True,
    )

    def style_function(feat):
        s = STATE_STYLE[feat["properties"]["state"]]
        style = {
            "fillColor": s["fill"],
            "color": s["border"],
            "weight": s["weight"],
            "fillOpacity": s["opacity"],
        }
        if s["dash"]:
            style["dashArray"] = s["dash"]
        return style

    folium.GeoJson(
        feats.to_json(),
        name="Africa",
        style_function=style_function,
        highlight_function=lambda _f: HOVER,
        tooltip=folium.GeoJsonTooltip(
            fields=["name", "tip"],
            aliases=["", ""],
            style=(
                "font-size:13px; padding:8px 12px; background:white; "
                "border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.15);"
            ),
            sticky=True,
        ),
    ).add_to(m)

    m.fit_bounds([[miny, minx], [maxy, maxx]])
    return m


def country_at_click(africa: gpd.GeoDataFrame, lat: float, lon: float) -> Optional[dict]:
    """Return {'name','iso_a3'} for the polygon under a click, else None."""
    pt = Point(lon, lat)
    idx = africa.sindex.query(pt, predicate="intersects")
    if len(idx) == 0:
        return None
    hit = africa.iloc[idx]
    hit = hit[hit.contains(pt)]
    if hit.empty:
        return None
    row = hit.iloc[0]
    return {"name": row["name"], "iso_a3": row["iso_a3"]}


def legend_html() -> str:
    v, w, u = STATE_STYLE[STATUS_VISITED], STATE_STYLE[STATUS_WISHLIST], STATE_STYLE["unvisited"]

    def swatch(style, dashed=False):
        border = f"2px {'dashed' if dashed else 'solid'} {style['border']}"
        return (
            f"<span style='display:inline-block;width:16px;height:16px;"
            f"background:{style['fill']};border:{border};border-radius:4px;"
            f"vertical-align:middle;margin-right:6px;'></span>"
        )

    return (
        "<div role='group' aria-label='Map legend' style='display:flex;gap:22px;"
        "align-items:center;font-size:.9rem;flex-wrap:wrap;'>"
        f"<span>{swatch(v)}Visited</span>"
        f"<span>{swatch(w, dashed=True)}Want to go (dashed)</span>"
        f"<span>{swatch(u)}Not visited yet</span>"
        "</div>"
    )
