"""AfricaX — African Restaurant Passport.

A local/Sheets-backed Streamlit app built to the AfricaX.dc.html design: a map-first
"restaurant passport" where the group logs visits, ranks them, and watches the group
consensus (median of everyone's normalised orders) update. Members rank on My Rankings.

Run:  streamlit run app.py
Data: Google Sheet when configured, else data/restaurants.csv  (owned by data_store.py)
"""

from __future__ import annotations

import streamlit as st

import data_store as ds
import ui
from mapview import load_geo

st.set_page_config(page_title="AfricaX — African Restaurant Passport", page_icon="🍴", layout="wide")


def main() -> None:
    ui.inject_css()

    africa = load_geo()
    df = ds.load()

    missing = ds.missing_columns(df)
    if missing:
        st.error(f"Data schema problem — missing columns: {', '.join(missing)}. Check the data source.")
        st.stop()

    page = ui.sidebar(africa, df)
    ui.header(df)
    ui.kpi_row(df)
    st.write("")

    if page == "Map":
        ui.map_page(africa, df)
    elif page == "My Rankings":
        ui.my_rankings_page(df)
    elif page == "Leaderboard":
        ui.leaderboard_page(df)
    elif page == "All Spots":
        ui.all_spots_page(df)
    elif page == "Wishlist":
        ui.wishlist_page(df)
    elif page == "Add Spot":
        ui.add_spot_page(africa, df)

    st.markdown("<div style='margin-top:28px;font-size:.78rem;color:#B0B4BA'>💡 Tip: rank your spots to move the "
                "leaderboard, jump countries from the sidebar, or add new places to the wishlist.</div>",
                unsafe_allow_html=True)


if __name__ == "__main__":
    main()
