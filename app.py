from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
import streamlit as st

# Leaflet map + geo
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Point

APP_TITLE = "🍽️ AfricaX – African Restaurant Passport"
DATA_DIR = Path(__file__).parent / "data"
DATA_PATH = DATA_DIR / "restaurants.csv"
# Natural Earth shapefile you extracted
AFRICA_SHP = DATA_DIR / "ne_110m_admin_0_countries.shp"

# Team members for per-person ratings (1–10)
RATERS = ["Fayez", "Muhammad", "Seth", "Ian", "Shubham"]

st.set_page_config(page_title="AfricaX", page_icon="🍽️", layout="wide")


# ---------- Data ----------

@st.cache_data
def load_geo() -> gpd.GeoDataFrame:
    """Load shapefile and keep only Africa (name, iso_a3, geometry)."""
    if not AFRICA_SHP.exists():
        st.error("Missing Natural Earth shapefile at data/ne_110m_admin_0_countries.shp (and sidecar files).")
        st.stop()

    gdf = gpd.read_file(AFRICA_SHP)

    # Filter to Africa only
    continent_col = next((c for c in ["CONTINENT", "continent", "REGION_UN", "region_un"] if c in gdf.columns), None)
    if continent_col:
        gdf = gdf[gdf[continent_col].str.strip().str.lower() == "africa"]


    # Standardize name and ISO3
    name_col = next((c for c in ["NAME", "ADMIN", "name"] if c in gdf.columns), None)
    iso_col = next((c for c in ["ISO_A3", "ADM0_A3", "iso_a3"] if c in gdf.columns), None)
    if not name_col or not iso_col:
        st.error("Shapefile is missing expected columns (NAME/ADMIN and ISO_A3/ADM0_A3).")
        st.stop()

    africa = gdf[[name_col, iso_col, "geometry"]].rename(columns={name_col: "name", iso_col: "iso_a3"}).copy()
    africa["name"] = africa["name"].astype(str).str.strip()
    africa["iso_a3"] = africa["iso_a3"].astype(str).str.upper().str.strip()
    africa = africa.reset_index(drop=True)
    return africa


CSV_COLUMNS = [
    "Country", "ISO_A3", "Restaurant",
    *RATERS,
    "Group_Rating",
    "Visit Date", "Notes", "Dishes"
]


@st.cache_data
def load_visits() -> pd.DataFrame:
    """Load visits CSV; coerce schema; compute group averages; parse dates (MM/DD/YYYY)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        pd.DataFrame(columns=CSV_COLUMNS).to_csv(DATA_PATH, index=False)

    df = pd.read_csv(DATA_PATH, dtype="string", keep_default_na=False)

    # Ensure all expected columns exist
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Ratings: per-person numeric 1–10, compute Group_Rating if missing
    for r in RATERS:
        df[r] = pd.to_numeric(df[r], errors="coerce").clip(1, 10)

    # If legacy 'Rating' column existed, use it to fill Group_Rating once
    if "Rating" in df.columns and df["Rating"].notna().any():
        df["Group_Rating"] = pd.to_numeric(df["Rating"], errors="coerce") * 2.0  # in case legacy 1–5
        df.drop(columns=["Rating"], inplace=True)

    # Compute group rating = mean of available individual ratings, else use given Group_Rating
    indiv = df[RATERS].astype(float)
    df["Group_Rating"] = pd.to_numeric(df["Group_Rating"], errors="coerce")
    computed = indiv.mean(axis=1, skipna=True)
    df.loc[computed.notna(), "Group_Rating"] = computed
    df["Group_Rating"] = df["Group_Rating"].clip(1, 10)

    # Dates: parse robustly; display/save as MM/DD/YYYY
    # Try MM/DD/YYYY first, then other
    parsed = pd.to_datetime(df["Visit Date"], format="%m/%d/%Y", errors="coerce")
    fallback = pd.to_datetime(df["Visit Date"], errors="coerce")
    df["Visit Date"] = parsed.fillna(fallback)

    # Only real visits: require Restaurant + some rating info
    has_any_rating = df[RATERS + ["Group_Rating"]].astype(float).notna().any(axis=1)
    df = df[(df["Restaurant"].str.len() > 0) & has_any_rating].copy()

    # Normalize ISO
    df["ISO_A3"] = df["ISO_A3"].astype("string").str.upper()

    df.sort_values(["Visit Date", "Country", "Restaurant"], ascending=[False, True, True], inplace=True, na_position="last")
    return df


def write_visit(row: Dict) -> None:
    """Append a single visit row to the CSV, saving date as MM/DD/YYYY."""
    out = {col: row.get(col, "") for col in CSV_COLUMNS}
    # date formatting
    dt = row.get("Visit Date")
    if isinstance(dt, (pd.Timestamp, datetime)):
        out["Visit Date"] = pd.to_datetime(dt).strftime("%m/%d/%Y")
    elif isinstance(dt, str):
        try:
            out["Visit Date"] = pd.to_datetime(dt).strftime("%m/%d/%Y")
        except Exception:
            out["Visit Date"] = dt

    # per-person rating bounds
    for r in RATERS:
        v = pd.to_numeric(out.get(r, None), errors="coerce")
        out[r] = "" if pd.isna(v) else float(min(max(v, 1.0), 10.0))

    # Group_Rating: mean of available individual ratings
    vals = [pd.to_numeric(out[r], errors="coerce") for r in RATERS]
    vals = [float(v) for v in vals if pd.notna(v)]
    out["Group_Rating"] = "" if not vals else round(sum(vals) / len(vals), 2)

    df = pd.DataFrame([out], columns=CSV_COLUMNS)
    header = not DATA_PATH.exists() or DATA_PATH.stat().st_size == 0
    df.to_csv(DATA_PATH, mode="a", header=header, index=False)


def update_visit(index: int, row: Dict) -> None:
    """Update an existing visit at the given index."""
    df = pd.read_csv(DATA_PATH, dtype="string", keep_default_na=False)
    
    # date formatting
    dt = row.get("Visit Date")
    if isinstance(dt, (pd.Timestamp, datetime)):
        row["Visit Date"] = pd.to_datetime(dt).strftime("%m/%d/%Y")
    elif isinstance(dt, str):
        try:
            row["Visit Date"] = pd.to_datetime(dt).strftime("%m/%d/%Y")
        except Exception:
            pass
    
    # per-person rating bounds
    for r in RATERS:
        v = pd.to_numeric(row.get(r, None), errors="coerce")
        row[r] = "" if pd.isna(v) else float(min(max(v, 1.0), 10.0))
    
    # Group_Rating: mean of available individual ratings
    vals = [pd.to_numeric(row[r], errors="coerce") for r in RATERS]
    vals = [float(v) for v in vals if pd.notna(v)]
    row["Group_Rating"] = "" if not vals else round(sum(vals) / len(vals), 2)
    
    # Update the row
    for col in CSV_COLUMNS:
        if col in row:
            df.at[index, col] = row[col]
    
    df.to_csv(DATA_PATH, index=False)


def delete_visit(index: int) -> None:
    """Delete a visit at the given index."""
    df = pd.read_csv(DATA_PATH, dtype="string", keep_default_na=False)
    df = df.drop(index)
    df.to_csv(DATA_PATH, index=False)


# ---------- Map helpers ----------

def make_map(africa: gpd.GeoDataFrame, visited_isos: set) -> folium.Map:
    # Fit to Africa and lock viewport to Africa bounds
    minx, miny, maxx, maxy = africa.total_bounds  # lon/lat
    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]

    m = folium.Map(location=center, zoom_start=3, tiles="cartodbpositron", prefer_canvas=True, no_wrap=True)
    
    def style_function(feat):
        iso = feat["properties"].get("iso_a3", "")
        if iso in visited_isos:
            return {"fillColor": "#4CAF50", "color": "#2E7D32", "weight": 2, "fillOpacity": 0.7}
        else:
            return {"fillColor": "#f2f2f2", "color": "#555", "weight": 1, "fillOpacity": 0.6}
    
    folium.GeoJson(
        africa.to_json(),
        name="Africa",
        style_function=style_function,
        highlight_function=lambda feat: {"weight": 2, "color": "#333", "fillColor": "#ffd24d", "fillOpacity": 0.7},
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Country"], sticky=False),
    ).add_to(m)

    m.fit_bounds([[miny, minx], [maxy, maxx]])
    js = f"""
    <script>
    var map = window.map_{id(m)};
    if (map) {{
        map.setMaxBounds([[{miny - 5}, {minx - 5}], [{maxy + 5}, {maxx + 5}]]);
        map.options.worldCopyJump = false;
        map.options.maxBoundsViscosity = 1.0;
    }}
    </script>
    """
    m.get_root().html.add_child(folium.Element(js))
    return m


def country_at_click(africa: gpd.GeoDataFrame, lat: float, lon: float) -> Optional[dict]:
    """Return {'name':..., 'iso_a3':...} of the polygon containing the point, else None."""
    pt = Point(lon, lat)  # shapely uses x=lon, y=lat
    idx = africa.sindex.query(pt, predicate="intersects")
    if len(idx) == 0:
        return None
    subset = africa.iloc[idx]
    hit = subset[subset.contains(pt)]
    if hit.empty:
        return None
    row = hit.iloc[0]
    return {"name": row["name"], "iso_a3": row["iso_a3"]}


# ---------- UI ----------

def kpis(visits: pd.DataFrame):
    c1, c2, c3 = st.columns(3)
    c1.metric("Countries covered", f"{visits['Country'].nunique():,}")
    c2.metric("Avg rating", f"{visits['Group_Rating'].astype(float).mean():.2f}" if not visits.empty else "–")
    last = pd.to_datetime(visits["Visit Date"], errors="coerce").max()
    c3.metric("Latest visit", last.strftime("%m/%d/%Y") if pd.notna(last) else "–")



def country_panel(visits: pd.DataFrame, selected: Optional[dict]):
    if selected is None:
        st.subheader("Select a country")
        st.info("Click a country on the map to view or add a visit.")
        return

    name, iso = selected["name"], selected["iso_a3"]
    st.subheader(f"{name}")
    rows = visits[visits["ISO_A3"] == iso].copy()

    if rows.empty:
        st.info("No visits logged yet. Add one below.")
        with st.form(key=f"visit_form_{iso}", clear_on_submit=True):
            restaurant = st.text_input("Restaurant", placeholder="e.g., Lucy Ethiopian Restaurant")


            st.markdown("**Per-person ratings (1–10)**")
            per_person = {}
            for r in RATERS:
                per_person[r] = st.slider(r, min_value=1.0, max_value=10.0, value=8.0, step=0.1, key=f"{r}_{iso}")

            # Show computed group avg live as headline
            vals = [per_person[r] for r in RATERS if per_person[r] is not None]
            group_avg = round(sum(vals) / len(vals), 2) if vals else None
            if group_avg is not None:
                st.markdown(f"### 🎯 Group Average: **{group_avg}/10**")
            
            visit_date = st.date_input("Visit date", format="MM/DD/YYYY")
            dishes = st.text_input("Dishes (comma-separated)", placeholder="injera, kitfo, tibs")
            notes = st.text_area("Notes", placeholder="Highlights, who joined, standout dishes...")

            submitted = st.form_submit_button("Add visit")
            if submitted:
                if restaurant.strip() == "":
                    st.error("Restaurant name is required.")
                else:
                    row = {
                        "Country": name,
                        "ISO_A3": iso,
                        "Restaurant": restaurant.strip(),
                        "Visit Date": pd.to_datetime(visit_date),
                        "Notes": notes.strip(),
                        "Dishes": dishes.strip(),
                        "Group_Rating": group_avg,
                    }


                    for r in RATERS:
                        row[r] = per_person[r]
                    write_visit(row)
                    st.success("Visit added.")
                    st.cache_data.clear()
                    st.rerun()
    else:
        # Display country visits with per-person ratings and group avg
        display = rows.assign(
            **{
                "Visit Date": pd.to_datetime(rows["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y"),
            }
        )[["Restaurant", *RATERS, "Group_Rating", "Visit Date", "Dishes", "Notes"]]


        st.dataframe(display, use_container_width=True, hide_index=True)

        # Country summary
        st.markdown("**Summary**")
        s1, s2, s3 = st.columns(3)
        s1.metric("Visits", f"{len(display):,}")
        s2.metric("Avg rating", f"{pd.to_numeric(display['Group_Rating'], errors='coerce').mean():.2f}")
        latest = pd.to_datetime(rows["Visit Date"], errors="coerce").max()
        s3.metric("Latest visit", latest.strftime("%m/%d/%Y") if pd.notna(latest) else "–")

        # Edit existing visits
        with st.expander("Edit or delete visits"):
            for idx, (orig_idx, row) in enumerate(rows.iterrows()):
                st.markdown(f"**{row['Restaurant']}** — {pd.to_datetime(row['Visit Date'], errors='coerce').strftime('%m/%d/%Y') if pd.notna(row['Visit Date']) else 'N/A'}")
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    with st.form(key=f"edit_form_{orig_idx}"):
                        restaurant = st.text_input("Restaurant", value=row["Restaurant"], key=f"edit_rest_{orig_idx}")
                        
                        st.markdown("**Per-person ratings (1–10)**")
                        per_person = {}
                        for r in RATERS:
                            curr_val = pd.to_numeric(row[r], errors="coerce")
                            per_person[r] = st.slider(
                                r, 
                                min_value=1.0, 
                                max_value=10.0, 
                                value=float(curr_val) if pd.notna(curr_val) else 8.0, 
                                step=0.1, 
                                key=f"edit_{r}_{orig_idx}"
                            )
                        
                        vals = [per_person[r] for r in RATERS if per_person[r] is not None]
                        group_avg = round(sum(vals) / len(vals), 2) if vals else None
                        if group_avg is not None:
                            st.markdown(f"### 🎯 Group Average: **{group_avg}/10**")
                        
                        visit_date = st.date_input(
                            "Visit date", 
                            value=pd.to_datetime(row["Visit Date"], errors="coerce") if pd.notna(row["Visit Date"]) else datetime.now(),
                            format="MM/DD/YYYY",
                            key=f"edit_date_{orig_idx}"
                        )
                        dishes = st.text_input("Dishes (comma-separated)", value=row["Dishes"], key=f"edit_dish_{orig_idx}")
                        notes = st.text_area("Notes", value=row["Notes"], key=f"edit_note_{orig_idx}")
                        
                        update_btn = st.form_submit_button("Update")
                        if update_btn:
                            if restaurant.strip() == "":
                                st.error("Restaurant name is required.")
                            else:
                                updated_row = {
                                    "Country": name,
                                    "ISO_A3": iso,
                                    "Restaurant": restaurant.strip(),
                                    "Visit Date": pd.to_datetime(visit_date),
                                    "Notes": notes.strip(),
                                    "Dishes": dishes.strip(),
                                    "Group_Rating": group_avg,
                                }
                                for r in RATERS:
                                    updated_row[r] = per_person[r]
                                update_visit(orig_idx, updated_row)
                                st.success("Visit updated.")
                                st.cache_data.clear()
                                st.rerun()
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Delete", key=f"delete_{orig_idx}", type="secondary"):
                        delete_visit(orig_idx)
                        st.success("Visit deleted.")
                        st.cache_data.clear()
                        st.rerun()
                
                if idx < len(rows) - 1:
                    st.divider()

        with st.expander("Add another visit"):
            with st.form(key=f"visit_form_more_{iso}", clear_on_submit=True):
                restaurant = st.text_input("Restaurant", key=f"rest_{iso}")


                st.markdown("**Per-person ratings (1–10)**")
                per_person = {}
                for r in RATERS:
                    per_person[r] = st.slider(r, min_value=1.0, max_value=10.0, value=8.0, step=0.1, key=f"{r}_more_{iso}")

                vals = [per_person[r] for r in RATERS if per_person[r] is not None]
                group_avg = round(sum(vals) / len(vals), 2) if vals else None
                if group_avg is not None:
                    st.markdown(f"### 🎯 Group Average: **{group_avg}/10**")

                visit_date = st.date_input("Visit date", format="MM/DD/YYYY", key=f"date_{iso}")
                dishes = st.text_input("Dishes (comma-separated)", key=f"dish_{iso}")
                notes = st.text_area("Notes", key=f"note_{iso}")

                submitted = st.form_submit_button("Add visit")
                if submitted:
                    if restaurant.strip() == "":
                        st.error("Restaurant name is required.")
                    else:
                        row = {
                            "Country": name,
                            "ISO_A3": iso,
                            "Restaurant": restaurant.strip(),
                            "Visit Date": pd.to_datetime(visit_date),
                            "Notes": notes.strip(),
                            "Dishes": dishes.strip(),
                            "Group_Rating": group_avg,
                        }
                        for r in RATERS:
                            row[r] = per_person[r]
                        write_visit(row)
                        st.success("Visit added.")
                        st.cache_data.clear()
                        st.rerun()


# ---------- App ----------

def main():
    st.title(APP_TITLE)
    st.caption("Click a country (Africa only) to view logged visits or add a new one. Dates use MM/DD/YYYY; ratings are per-person (1–10) with group average auto-computed.")

    africa = load_geo()
    visits = load_visits()
    kpis(visits)

    col_map, col_panel = st.columns([3, 2], gap="large")

    with col_map:
        visited_isos = set(visits["ISO_A3"].unique())
        m = make_map(africa, visited_isos)
        map_state = st_folium(m, width=None, height=650)
        if map_state and map_state.get("last_object_clicked"):
            lat = map_state["last_object_clicked"]["lat"]
            lon = map_state["last_object_clicked"]["lng"]
            hit = country_at_click(africa, lat, lon)
            if hit:
                st.session_state["selected_country"] = hit

    with col_panel:
        selected = st.session_state.get("selected_country")
        country_panel(visits, selected)

    st.markdown("---")
    st.download_button(
        "Download all visits (CSV)",
        data=visits.to_csv(index=False),
        file_name="africax_restaurants.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()