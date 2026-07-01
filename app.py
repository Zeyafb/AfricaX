"""AfricaX — African Restaurant Passport.

A local, CSV-backed Streamlit app: an accessible clickable map of Africa where a
group of friends logs restaurant visits (with per-person + group ratings) and
bookmarks places they still want to try.

Run:  streamlit run app.py
Data: data/restaurants.csv  (owned by data_store.py)
"""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

import data_store as ds
import ui
from mapview import build_map, country_at_click, legend_html, load_geo

st.set_page_config(page_title="AfricaX", page_icon="🍽️", layout="wide")


def main() -> None:
    ui.inject_css()

    st.title("AfricaX 🍽️")
    st.caption("Our group's African restaurant passport — visited spots, ratings, and places we want to try.")

    africa = load_geo()
    df = ds.load()

    missing = ds.missing_columns(df)
    if missing:
        st.error(f"Data schema problem — missing columns: {', '.join(missing)}. Check data/restaurants.csv.")
        st.stop()

    ui.kpis(df)
    selected = ui.sidebar_nav(africa, df)

    tab_map, tab_board, tab_wish, tab_all = st.tabs(
        ["🗺️ Map", "🏆 Leaderboard", "🔖 Wishlist", "📋 All spots"]
    )

    with tab_map:
        col_map, col_detail = st.columns([3, 2], gap="large")
        with col_map:
            m = build_map(africa, ds.status_by_iso(df), ds.country_stats(df))
            state = st_folium(m, width=None, height=620, key="africa_map")
            if state and state.get("last_object_clicked"):
                c = state["last_object_clicked"]
                hit = country_at_click(africa, c["lat"], c["lng"])
                current = (st.session_state.get("selected_country") or {}).get("iso_a3")
                if hit and hit["iso_a3"] != current:
                    st.session_state["selected_country"] = hit
                    st.rerun()
            st.markdown(legend_html(), unsafe_allow_html=True)
        with col_detail:
            ui.country_detail(df, selected)

    with tab_board:
        ui.leaderboard(df)

    with tab_wish:
        ui.wishlist_view(df)

    with tab_all:
        ui.all_visits_table(df)


if __name__ == "__main__":
    main()
