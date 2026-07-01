"""AfricaX — African Restaurant Passport.

A local, CSV-backed Streamlit app: an accessible clickable map of Africa where a
group of friends logs restaurant visits and ranks them. Group standing is by
**consensus ranking** (median of everyone's normalised orders — the Movie Ranks
method), surfaced as an X/10 star. Members submit their own order on My Rankings.

Run:  streamlit run app.py
Data: data/restaurants.csv  (owned by data_store.py)
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
        st.error(f"Data schema problem — missing columns: {', '.join(missing)}. Check data/restaurants.csv.")
        st.stop()

    page = ui.sidebar(africa, df)
    ui.header(df)
    ui.kpi_cards(df)
    st.write("")

    if page == "Map":
        ui.map_page(africa, df)
    elif page == "Leaderboard":
        ui.leaderboard_page(df)
    elif page == "My Rankings":
        ui.my_rankings_page(df)
    elif page == "All Spots":
        ui.all_spots_page(df)
    elif page == "Wishlist":
        ui.wishlist_page(df)
    elif page == "Add Spot":
        ui.add_spot_page(africa, df)

    st.caption("💡 Tip: use the sidebar to jump around, rank your spots, or add new places to the wishlist.")


if __name__ == "__main__":
    main()
