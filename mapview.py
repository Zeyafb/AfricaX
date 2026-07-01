"""AfricaX map layer — Folium choropleth of Africa with 3 visit states.

Visual target (see the app mockup): a clean map with a light-blue ocean, light-grey
"not visited" countries, solid green "visited", and solid purple "wishlist", with a
permanent name label on every lit country.

Accessibility notes:
- The three states differ in **lightness + hue** and every lit country is also
  labelled in text, so states never rely on colour alone.
- Every state is also reachable without the map (sidebar country picker + tables
  in ``ui.py``), and hover tooltips carry the same info as text.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import folium
import geopandas as gpd
import streamlit as st
from shapely.geometry import Point

from data_store import STATUS_VISITED, STATUS_WISHLIST

_SHP = Path(__file__).parent / "data" / "ne_110m_admin_0_countries.shp"

OCEAN = "#DCEFF9"

# States differ in lightness AND hue. Green = visited, purple = wishlist,
# light grey = not visited (matches the product mockup).
STATE_STYLE = {
    STATUS_VISITED:  {"fill": "#2E7D5B", "border": "#1C5C41", "weight": 1.2, "opacity": 0.92, "label": "#FFFFFF"},
    STATUS_WISHLIST: {"fill": "#8B5FBF", "border": "#5E3B87", "weight": 1.2, "opacity": 0.90, "label": "#FFFFFF"},
    "unvisited":     {"fill": "#E6E6E6", "border": "#CFCFCF", "weight": 0.7, "opacity": 0.95, "label": "#6B6B6B"},
}
HOVER = {"weight": 2.6, "color": "#1A1A1A", "fillOpacity": 1.0}


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
        n = stat.get("visited", 0)
        return f"Visited · {n} place{'s' if n != 1 else ''}"
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
        tiles=None,
        prefer_canvas=True,
        no_wrap=True,
        zoom_control=True,
    )
    # Light-blue ocean: style the leaflet container *inside* folium's own iframe.
    m.get_root().header.add_child(
        folium.Element(f"<style>.leaflet-container{{background:{OCEAN} !important;}}</style>")
    )

    def style_function(feat):
        s = STATE_STYLE[feat["properties"]["state"]]
        return {
            "fillColor": s["fill"],
            "color": s["border"],
            "weight": s["weight"],
            "fillOpacity": s["opacity"],
        }

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

    _add_labels(m, feats)
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    return m


def _add_labels(m: folium.Map, feats: gpd.GeoDataFrame) -> None:
    """Permanent name labels on every lit (visited/wishlist) country."""
    lit = feats[feats["state"] != "unvisited"]
    if lit.empty:
        return
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # representative_point on geographic CRS
        for _, r in lit.iterrows():
            pt = r.geometry.representative_point()
            colour = STATE_STYLE[r["state"]]["label"]
            html = (
                f"<div style=\"font-size:11px;font-weight:700;color:{colour};"
                "text-shadow:0 1px 2px rgba(0,0,0,.45);white-space:nowrap;"
                "transform:translate(-50%,-50%);text-align:center;\">"
                f"{r['name']}</div>"
            )
            folium.map.Marker(
                [pt.y, pt.x],
                icon=folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0)),
            ).add_to(m)


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

    def swatch(style):
        return (
            f"<span style='display:inline-block;width:14px;height:14px;"
            f"background:{style['fill']};border:1px solid {style['border']};border-radius:4px;"
            f"vertical-align:middle;margin-right:6px;'></span>"
        )

    return (
        "<div role='group' aria-label='Map legend' style='display:flex;gap:20px;"
        "align-items:center;font-size:.85rem;flex-wrap:wrap;color:#3a3a3a;'>"
        f"<span>{swatch(v)}Visited</span>"
        f"<span>{swatch(w)}Wishlist</span>"
        f"<span>{swatch(u)}Not Visited</span>"
        "</div>"
    )
