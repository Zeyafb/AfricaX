"""AfricaX — African Restaurant Passport (single-page dashboard).

One dashboard shows everything at a glance — map, selected country, group
leaderboard, personal rankings, wishlist, quick-add, progress, and activity.
The consensus-ranking flow (reorder ballot) and the full editorial leaderboard
open as their own dedicated views. Group standing is by consensus ranking
(median of everyone's normalised orders), never 1-10 ratings.

Run:  streamlit run app.py
Data: Google Sheet when configured, else data/restaurants.csv (owned by data_store.py)
"""

from __future__ import annotations

import streamlit as st

import data_store as ds
import ui
from mapview import load_geo

st.set_page_config(page_title="AfricaX — African Restaurant Passport", page_icon="🍴",
                   layout="wide", initial_sidebar_state="collapsed")


def main() -> None:
    ui.inject_css()
    st.markdown("<style>section[data-testid='stSidebar'],"
                "div[data-testid='stSidebarCollapsedControl']{display:none}</style>", unsafe_allow_html=True)

    africa = load_geo()
    df = ds.load()

    missing = ds.missing_columns(df)
    if missing:
        st.error(f"Data schema problem — missing columns: {', '.join(missing)}. Check the data source.")
        st.stop()

    view = st.session_state.get("view", "dashboard")
    if view == "rank":
        ui.rank_view(df)
    elif view == "leaderboard":
        ui.leaderboard_view(df)
    elif view == "wishlist":
        ui._back_button("bk_wish")
        ui.wishlist_page(df)
    elif view == "allspots":
        ui._back_button("bk_all")
        ui.all_spots_page(df)
    elif view == "add":
        ui._back_button("bk_add")
        ui.add_spot_page(africa, df)
    else:
        ui.dashboard(africa, df)


if __name__ == "__main__":
    main()
