from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Leaflet map + geo
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Point

APP_TITLE = "AfricaX - African Restaurant Passport"
DATA_DIR = Path(__file__).parent / "data"
# Natural Earth shapefile
AFRICA_SHP = DATA_DIR / "ne_110m_admin_0_countries.shp"

# Google Sheets column order
SHEET_COLUMNS = ["Country", "ISO_A3", "Restaurant", "Visit Date", "Dishes", "Notes"]

st.set_page_config(page_title="AfricaX", page_icon="🍽️", layout="wide")


# ---------- Custom CSS ----------

def inject_css():
    """Inject custom CSS for polished styling."""
    st.markdown("""
    <style>
    /* Main container spacing */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* KPI metrics styling */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #F5EFE6 0%, #FEFCF8 100%);
        border: 1px solid #E8DCC4;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    [data-testid="stMetricLabel"] {
        color: #666;
        font-size: 0.85rem;
        font-weight: 500;
    }

    [data-testid="stMetricValue"] {
        color: #2C2C2C;
        font-size: 1.8rem;
        font-weight: 600;
    }

    /* Map container */
    [data-testid="stVerticalBlock"] iframe {
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }

    /* Panel styling */
    .stExpander {
        background: #FEFCF8;
        border: 1px solid #E8DCC4;
        border-radius: 12px;
    }

    /* Form inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 8px;
        border: 1px solid #E8DCC4;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #D4A574;
        box-shadow: 0 0 0 2px rgba(212, 165, 116, 0.2);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Download button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #4A7C59 0%, #3D6B4A 100%);
        color: white;
        border: none;
        border-radius: 8px;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #E8DCC4;
        margin: 1.5rem 0;
    }

    /* Subheader styling */
    h2 {
        color: #2C2C2C;
        font-weight: 600;
        border-bottom: 2px solid #D4A574;
        padding-bottom: 0.5rem;
    }

    /* Info boxes */
    .stAlert {
        border-radius: 10px;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


# ---------- Google Sheets Backend ----------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


@st.cache_resource
def get_gsheet_client():
    """Create authenticated gspread client from Streamlit secrets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.info("Please configure your Google Sheets credentials in .streamlit/secrets.toml")
        st.stop()


def get_worksheet():
    """Get the visits worksheet, creating headers if needed."""
    client = get_gsheet_client()
    spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    spreadsheet = client.open_by_key(spreadsheet_id)

    # Get or create the first worksheet
    worksheet = spreadsheet.sheet1

    # Check if headers exist, if not add them
    try:
        first_row = worksheet.row_values(1)
        if not first_row or first_row[0] != "Country":
            worksheet.insert_row(SHEET_COLUMNS, 1)
    except:
        worksheet.insert_row(SHEET_COLUMNS, 1)

    return worksheet


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


@st.cache_data(ttl=30)
def load_visits() -> pd.DataFrame:
    """Load visits from Google Sheets."""
    try:
        worksheet = get_worksheet()
        data = worksheet.get_all_records()

        if not data:
            return pd.DataFrame(columns=SHEET_COLUMNS)

        df = pd.DataFrame(data)

        # Ensure all expected columns exist
        for col in SHEET_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # Parse dates
        parsed = pd.to_datetime(df["Visit Date"], format="%m/%d/%Y", errors="coerce")
        fallback = pd.to_datetime(df["Visit Date"], errors="coerce")
        df["Visit Date"] = parsed.fillna(fallback)

        # Filter valid visits (must have restaurant name)
        df = df[df["Restaurant"].astype(str).str.len() > 0].copy()

        # Normalize ISO
        df["ISO_A3"] = df["ISO_A3"].astype("string").str.upper()

        df.sort_values(["Visit Date", "Country", "Restaurant"], ascending=[False, True, True], inplace=True, na_position="last")
        return df

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(columns=SHEET_COLUMNS)


def write_visit(row: Dict) -> None:
    """Append a single visit row to Google Sheets."""
    out = []
    for col in SHEET_COLUMNS:
        val = row.get(col, "")

        # Format date
        if col == "Visit Date":
            if isinstance(val, (pd.Timestamp, datetime)):
                val = pd.to_datetime(val).strftime("%m/%d/%Y")
            elif isinstance(val, str):
                try:
                    val = pd.to_datetime(val).strftime("%m/%d/%Y")
                except:
                    pass

        out.append(val if val != "" else "")

    worksheet = get_worksheet()
    worksheet.append_row(out, value_input_option="USER_ENTERED")


def update_visit(row_num: int, row: Dict) -> None:
    """Update an existing visit at the given row number (1-indexed, header is row 1)."""
    out = []
    for col in SHEET_COLUMNS:
        val = row.get(col, "")

        # Format date
        if col == "Visit Date":
            if isinstance(val, (pd.Timestamp, datetime)):
                val = pd.to_datetime(val).strftime("%m/%d/%Y")
            elif isinstance(val, str):
                try:
                    val = pd.to_datetime(val).strftime("%m/%d/%Y")
                except:
                    pass

        out.append(val if val != "" else "")

    worksheet = get_worksheet()
    worksheet.update(values=[out], range_name=f"A{row_num}:{chr(65 + len(SHEET_COLUMNS) - 1)}{row_num}", value_input_option="USER_ENTERED")


def delete_visit(row_num: int) -> None:
    """Delete a visit at the given row number."""
    worksheet = get_worksheet()
    worksheet.delete_rows(row_num)


# ---------- Map helpers ----------

# Color palette
COLORS = {
    "visited": "#4A7C59",      # Forest green
    "visited_border": "#3D6B4A",
    "unvisited": "#E8DCC4",    # Warm beige
    "unvisited_border": "#C9B896",
    "hover": "#F4C430",        # Golden
    "selected": "#D4A574",     # Amber
}


def make_map(africa: gpd.GeoDataFrame, visited_isos: set) -> folium.Map:
    """Create the Africa map with improved styling."""
    minx, miny, maxx, maxy = africa.total_bounds
    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]

    m = folium.Map(
        location=center,
        zoom_start=3,
        tiles="cartodbvoyager",
        prefer_canvas=True,
        no_wrap=True
    )

    def style_function(feat):
        iso = feat["properties"].get("iso_a3", "")
        if iso in visited_isos:
            return {
                "fillColor": COLORS["visited"],
                "color": COLORS["visited_border"],
                "weight": 2,
                "fillOpacity": 0.75
            }
        else:
            return {
                "fillColor": COLORS["unvisited"],
                "color": COLORS["unvisited_border"],
                "weight": 1,
                "fillOpacity": 0.6
            }

    def highlight_function(feat):
        return {
            "weight": 3,
            "color": COLORS["hover"],
            "fillColor": COLORS["hover"],
            "fillOpacity": 0.8
        }

    folium.GeoJson(
        africa.to_json(),
        name="Africa",
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["name"],
            aliases=[""],
            style="font-size: 14px; font-weight: 500; padding: 8px 12px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);",
            sticky=False
        ),
    ).add_to(m)

    m.fit_bounds([[miny, minx], [maxy, maxx]])

    # Restrict panning to Africa
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
    pt = Point(lon, lat)
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
    """Display KPI metrics."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Countries Explored", f"{visits['Country'].nunique():,}")
    c2.metric("Total Visits", f"{len(visits):,}")
    last = pd.to_datetime(visits["Visit Date"], errors="coerce").max()
    c3.metric("Latest Visit", last.strftime("%b %d, %Y") if pd.notna(last) else "-")


def country_panel(visits: pd.DataFrame, selected: Optional[dict]):
    """Display the country detail panel."""
    if selected is None:
        st.subheader("Select a Country")
        st.info("Click any country on the map to view visits or add a new one.")
        return

    name, iso = selected["name"], selected["iso_a3"]
    st.subheader(f"{name}")

    # Get visits for this country
    all_visits = load_visits()
    rows = all_visits[all_visits["ISO_A3"] == iso].copy()

    if rows.empty:
        st.info("No visits logged yet.")
        _render_add_form(name, iso, "first")
    else:
        # Display visits table
        display = rows.assign(
            **{
                "Visit Date": pd.to_datetime(rows["Visit Date"], errors="coerce").dt.strftime("%b %d, %Y"),
            }
        )[["Restaurant", "Visit Date", "Dishes", "Notes"]]

        st.dataframe(display, width="stretch", hide_index=True)

        # Country summary
        st.markdown("**Summary**")
        s1, s2 = st.columns(2)
        s1.metric("Total Visits", f"{len(display):,}")
        latest = pd.to_datetime(rows["Visit Date"], errors="coerce").max()
        s2.metric("Latest", latest.strftime("%b %d") if pd.notna(latest) else "-")

        # Edit existing visits
        with st.expander("Edit or delete visit"):
            _render_edit_forms(name, iso, rows)


def _render_add_form(name: str, iso: str, suffix: str):
    """Render the form to add a new visit."""
    with st.form(key=f"visit_form_{suffix}_{iso}", clear_on_submit=True):
        restaurant = st.text_input("Restaurant name", placeholder="e.g., Lucy Ethiopian Kitchen")

        col1, col2 = st.columns(2)
        with col1:
            visit_date = st.date_input("Visit date", format="MM/DD/YYYY", key=f"date_{suffix}_{iso}")
        with col2:
            dishes = st.text_input("Dishes (comma-separated)", placeholder="injera, kitfo", key=f"dish_{suffix}_{iso}")

        notes = st.text_area("Notes", placeholder="Highlights, atmosphere, recommendations...", key=f"note_{suffix}_{iso}")

        submitted = st.form_submit_button("Add Visit", type="primary")
        if submitted:
            if restaurant.strip() == "":
                st.error("Please enter a restaurant name.")
            else:
                row = {
                    "Country": name,
                    "ISO_A3": iso,
                    "Restaurant": restaurant.strip(),
                    "Visit Date": pd.to_datetime(visit_date),
                    "Dishes": dishes.strip(),
                    "Notes": notes.strip(),
                }
                write_visit(row)
                st.success("Visit added!")
                st.cache_data.clear()
                st.rerun()


def _render_edit_forms(name: str, iso: str, rows: pd.DataFrame):
    """Render edit forms for existing visits."""
    # Need to find the actual row numbers in the sheet
    worksheet = get_worksheet()
    all_data = worksheet.get_all_values()

    for idx, (_, row) in enumerate(rows.iterrows()):
        restaurant_name = row["Restaurant"]
        visit_date_str = pd.to_datetime(row["Visit Date"], errors="coerce")
        visit_date_display = visit_date_str.strftime('%b %d, %Y') if pd.notna(visit_date_str) else 'N/A'

        st.markdown(f"**{restaurant_name}** - {visit_date_display}")

        # Find this row in the sheet (match on Restaurant + ISO)
        sheet_row_num = None
        for i, sheet_row in enumerate(all_data[1:], start=2):  # Skip header, 1-indexed
            if len(sheet_row) >= 3:
                if sheet_row[0] == row["Country"] and sheet_row[1] == iso and sheet_row[2] == restaurant_name:
                    sheet_row_num = i
                    break

        if sheet_row_num is None:
            st.warning("Could not locate this visit in the sheet.")
            continue

        col1, col2 = st.columns([4, 1])

        with col1:
            with st.form(key=f"edit_form_{sheet_row_num}"):
                restaurant = st.text_input("Restaurant", value=row["Restaurant"], key=f"edit_rest_{sheet_row_num}")

                edit_col1, edit_col2 = st.columns(2)
                with edit_col1:
                    edit_date = st.date_input(
                        "Visit date",
                        value=pd.to_datetime(row["Visit Date"], errors="coerce") if pd.notna(row["Visit Date"]) else datetime.now(),
                        format="MM/DD/YYYY",
                        key=f"edit_date_{sheet_row_num}"
                    )
                with edit_col2:
                    edit_dishes = st.text_input("Dishes", value=row["Dishes"], key=f"edit_dish_{sheet_row_num}")

                edit_notes = st.text_area("Notes", value=row["Notes"], key=f"edit_note_{sheet_row_num}")

                update_btn = st.form_submit_button("Update")
                if update_btn:
                    if restaurant.strip() == "":
                        st.error("Restaurant name is required.")
                    else:
                        updated_row = {
                            "Country": name,
                            "ISO_A3": iso,
                            "Restaurant": restaurant.strip(),
                            "Visit Date": pd.to_datetime(edit_date),
                            "Dishes": edit_dishes.strip(),
                            "Notes": edit_notes.strip(),
                        }
                        update_visit(sheet_row_num, updated_row)
                        st.success("Visit updated!")
                        st.cache_data.clear()
                        st.rerun()

        with col2:
            st.write("")
            st.write("")
            if st.button("Delete", key=f"delete_{sheet_row_num}", type="secondary"):
                delete_visit(sheet_row_num)
                st.success("Visit deleted!")
                st.cache_data.clear()
                st.rerun()

        if idx < len(rows) - 1:
            st.divider()


# ---------- App ----------

def main():
    inject_css()

    st.title(APP_TITLE)
    st.caption("Tracking our group's African culinary adventures. Click a country to view visits or add new ones.")

    africa = load_geo()
    visits = load_visits()

    kpis(visits)
    st.markdown("")  # Spacing

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

    col_dl, col_legend = st.columns([1, 2])
    with col_dl:
        st.download_button(
            "Download All Visits (CSV)",
            data=visits.to_csv(index=False),
            file_name="africax_visits.csv",
            mime="text/csv",
        )
    with col_legend:
        st.markdown(
            f"""
            <div style="display: flex; gap: 20px; align-items: center; font-size: 0.9rem;">
                <span><span style="display: inline-block; width: 16px; height: 16px; background: {COLORS['visited']}; border-radius: 4px; vertical-align: middle;"></span> Visited</span>
                <span><span style="display: inline-block; width: 16px; height: 16px; background: {COLORS['unvisited']}; border-radius: 4px; vertical-align: middle;"></span> Not yet visited</span>
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
