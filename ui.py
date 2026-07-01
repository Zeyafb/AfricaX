"""AfricaX UI layer — Streamlit widgets: KPIs, country detail, forms, leaderboard.

Every write goes through ``data_store``; this module never touches the CSV.
Accessibility: all inputs are labelled, ratings carry help text, and the sidebar
country picker is a full keyboard-only alternative to clicking the map.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st

import data_store as ds

RATING_HELP = "1–10. Leave the person in ‘Anyone absent?’ below if they didn’t rate."


# ---------- styling ----------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        [data-testid="stMetric"] {
            background: linear-gradient(135deg,#F5EFE6 0%,#FEFCF8 100%);
            border: 1px solid #E3D5BC; border-radius: 12px; padding: .9rem 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,.05);
        }
        [data-testid="stMetricLabel"] { color:#4A4A4A; font-weight:600; font-size:.82rem; }
        [data-testid="stMetricValue"] { color:#22201C; font-weight:700; }
        [data-testid="stVerticalBlock"] iframe { border-radius:14px; box-shadow:0 4px 20px rgba(0,0,0,.08); }
        .stButton>button, .stDownloadButton>button { border-radius:8px; font-weight:600; }
        h2, h3 { color:#22201C; }
        .ax-pill { display:inline-block; padding:2px 10px; border-radius:999px;
                   font-size:.75rem; font-weight:700; }
        .ax-visited  { background:#DDEFE4; color:#12513A; border:1px solid #2E7D5B; }
        .ax-wishlist { background:#DCEBF9; color:#17456F; border:1px solid #2F80C7; }
        #MainMenu, footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_pill(status: str) -> str:
    if status == ds.STATUS_WISHLIST:
        return "<span class='ax-pill ax-wishlist'>WANT TO GO</span>"
    return "<span class='ax-pill ax-visited'>VISITED</span>"


# ---------- KPIs ----------

def kpis(df: pd.DataFrame) -> None:
    vis = ds.visited(df)
    wish = ds.wishlist(df)
    avg = vis["Group_Rating"].dropna().mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Countries visited", f"{vis['ISO_A3'].nunique():,}")
    c2.metric("Places visited", f"{len(vis):,}")
    c3.metric("On the wishlist", f"{len(wish):,}")
    c4.metric("Avg group rating", f"{avg:.1f}/10" if pd.notna(avg) else "—")


# ---------- sidebar: accessible navigation ----------

def sidebar_nav(africa, df: pd.DataFrame) -> Optional[dict]:
    """Keyboard-friendly country picker — full alternative to clicking the map."""
    st.sidebar.header("🔎 Jump to a country")

    names = sorted(africa["name"].tolist())
    iso_by_name = dict(zip(africa["name"], africa["iso_a3"]))

    # Mark which countries have data so the picker is informative.
    status = ds.status_by_iso(df)

    def label(n: str) -> str:
        s = status.get(iso_by_name[n])
        tag = " ✓" if s == ds.STATUS_VISITED else (" ★" if s == ds.STATUS_WISHLIST else "")
        return n + tag

    current = st.session_state.get("selected_country")
    idx = names.index(current["name"]) + 1 if current and current["name"] in names else 0

    choice = st.sidebar.selectbox(
        "Country",
        options=["— select —"] + names,
        index=idx,
        format_func=lambda n: n if n == "— select —" else label(n),
        help="✓ visited · ★ on the wishlist. Selecting here is equivalent to clicking the map.",
    )
    if choice != "— select —":
        st.session_state["selected_country"] = {"name": choice, "iso_a3": iso_by_name[choice]}

    st.sidebar.markdown("---")
    st.sidebar.caption("Legend")
    from mapview import legend_html
    st.sidebar.markdown(legend_html(), unsafe_allow_html=True)

    return st.session_state.get("selected_country")


# ---------- country detail ----------

def country_detail(df: pd.DataFrame, selected: Optional[dict]) -> None:
    if not selected:
        st.info("Pick a country on the map or in the sidebar to see visits, ratings, and to add a new spot.")
        return

    name, iso = selected["name"], selected["iso_a3"]
    rows = df[df["ISO_A3"] == iso]  # keeps file-order index for edit/delete
    vis = rows[rows["Status"] == ds.STATUS_VISITED]
    wish = rows[rows["Status"] == ds.STATUS_WISHLIST]

    st.subheader(f"🌍 {name}")

    if vis.empty and wish.empty:
        st.caption("No visits or wishlist spots logged here yet.")
    else:
        if not vis.empty:
            best = vis.loc[vis["Group_Rating"].idxmax()] if vis["Group_Rating"].notna().any() else None
            for _idx, r in vis.sort_values("Group_Rating", ascending=False, na_position="last").iterrows():
                _visit_card(r, is_best=(best is not None and r.name == best.name))
        if not wish.empty:
            st.markdown("**🔖 Want to go**")
            for _idx, r in wish.iterrows():
                _wishlist_card(r)

    st.markdown("---")
    with st.expander("➕ Add a spot here", expanded=(vis.empty and wish.empty)):
        _add_form(name, iso)


def _rating_row(r: pd.Series) -> str:
    parts = []
    for rater in ds.RATERS:
        v = r[rater]
        parts.append(f"{rater} {v:g}" if pd.notna(v) else f"{rater} —")
    return " · ".join(parts)


def _visit_card(r: pd.Series, is_best: bool = False) -> None:
    star = " ⭐ top-rated" if is_best else ""
    grp = f"{r['Group_Rating']:g}/10" if pd.notna(r["Group_Rating"]) else "—"
    dt = pd.to_datetime(r["Visit Date"], errors="coerce")
    when = dt.strftime("%b %d, %Y") if pd.notna(dt) else "date unknown"

    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(f"**{r['Restaurant']}**{star}  \n<span style='color:#6b6b6b'>{when}</span>", unsafe_allow_html=True)
        top[1].metric("Group", grp)
        if str(r.get("Dishes", "")).strip():
            st.markdown(f"🍽️ {r['Dishes']}")
        st.caption(_rating_row(r))
        if str(r.get("Notes", "")).strip():
            st.markdown(f"📝 {r['Notes']}")
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("Edit / delete"):
            _edit_form(r)


def _wishlist_card(r: pd.Series) -> None:
    with st.container(border=True):
        st.markdown(f"**{r['Restaurant']}** {status_pill(ds.STATUS_WISHLIST)}", unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.markdown(f"📝 {r['Notes']}")
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("✅ Mark as visited / edit"):
            _mark_visited_form(r)


# ---------- forms ----------

def _ratings_inputs(prefix: str, defaults: Optional[dict] = None):
    defaults = defaults or {}
    st.markdown("**Per-person ratings**", help=RATING_HELP)
    cols = st.columns(len(ds.RATERS))
    ratings = {}
    for col, rater in zip(cols, ds.RATERS):
        dv = defaults.get(rater)
        ratings[rater] = col.slider(
            rater, 1.0, 10.0,
            float(dv) if dv is not None and pd.notna(dv) else 7.0,
            0.5, key=f"{prefix}_{rater}",
        )
    absent = st.multiselect(
        "Anyone absent? (excluded from the group average)",
        ds.RATERS, default=[], key=f"{prefix}_absent",
        help="Absent people are stored blank and don't count toward the group score.",
    )
    present = {r: v for r, v in ratings.items() if r not in absent}
    grp = ds.group_rating(list(present.values()))
    st.markdown(f"### 🎯 Group average: **{grp if grp is not None else '—'}/10**")
    return present, absent


def _add_form(name: str, iso: str) -> None:
    kind = st.radio(
        "Type", ["Visited", "Want to go (wishlist)"],
        horizontal=True, key=f"kind_{iso}",
        help="Log somewhere you've been (with ratings) or bookmark a place to try later.",
    )
    wishlist = kind.startswith("Want")

    with st.form(key=f"add_{iso}", clear_on_submit=True):
        restaurant = st.text_input("Restaurant name", placeholder="e.g., Sweet Sweet Kitchen")
        maps_url = st.text_input("Google Maps link (optional)", placeholder="https://maps.app.goo.gl/…")
        dishes = st.text_input("Dishes (comma-separated, optional)", placeholder="jollof, suya")
        notes = st.text_area("Notes (optional)", placeholder="Why you want to go / how it was")

        present, absent = ({}, [])
        visit_date = None
        if not wishlist:
            visit_date = st.date_input("Visit date", value=date.today(), format="MM/DD/YYYY")
            present, absent = _ratings_inputs(f"add_{iso}")

        if st.form_submit_button("Add", type="primary"):
            if not restaurant.strip():
                st.error("Restaurant name is required.")
                return
            row = {
                "Country": name, "ISO_A3": iso, "Restaurant": restaurant.strip(),
                "Dishes": dishes.strip(), "Notes": notes.strip(),
                "Maps_URL": maps_url.strip(),
                "Status": ds.STATUS_WISHLIST if wishlist else ds.STATUS_VISITED,
            }
            for rater in ds.RATERS:
                row[rater] = present.get(rater, "")
            if not wishlist:
                row["Visit Date"] = pd.to_datetime(visit_date)
            ds.append_row(row)
            st.success(f"Added {restaurant.strip()}.")
            st.cache_data.clear()
            st.rerun()


def _edit_form(r: pd.Series) -> None:
    idx = r.name
    with st.form(key=f"edit_{idx}"):
        restaurant = st.text_input("Restaurant", value=r["Restaurant"], key=f"er_{idx}")
        c1, c2 = st.columns(2)
        dt = pd.to_datetime(r["Visit Date"], errors="coerce")
        visit_date = c1.date_input(
            "Visit date", value=dt.date() if pd.notna(dt) else date.today(),
            format="MM/DD/YYYY", key=f"ed_{idx}",
        )
        dishes = c2.text_input("Dishes", value=r.get("Dishes", ""), key=f"edi_{idx}")
        notes = st.text_area("Notes", value=r.get("Notes", ""), key=f"en_{idx}")
        maps_url = st.text_input("Google Maps link", value=r.get("Maps_URL", ""), key=f"em_{idx}")
        present, absent = _ratings_inputs(
            f"edit_{idx}", defaults={rater: r[rater] for rater in ds.RATERS}
        )

        col_u, col_d = st.columns(2)
        if col_u.form_submit_button("Save", type="primary"):
            update = {
                "Restaurant": restaurant.strip(), "Dishes": dishes.strip(),
                "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                "Visit Date": pd.to_datetime(visit_date),
            }
            for rater in ds.RATERS:
                update[rater] = present.get(rater, "")
            ds.update_row(idx, update)
            st.success("Saved.")
            st.cache_data.clear()
            st.rerun()
        if col_d.form_submit_button("Delete"):
            ds.delete_row(idx)
            st.success("Deleted.")
            st.cache_data.clear()
            st.rerun()


def _mark_visited_form(r: pd.Series) -> None:
    idx = r.name
    with st.form(key=f"mark_{idx}"):
        visit_date = st.date_input("When did you go?", value=date.today(), format="MM/DD/YYYY", key=f"md_{idx}")
        dishes = st.text_input("Dishes", value=r.get("Dishes", ""), key=f"mdi_{idx}")
        notes = st.text_area("Notes", value=r.get("Notes", ""), key=f"mn_{idx}")
        present, absent = _ratings_inputs(f"mark_{idx}")
        if st.form_submit_button("Mark as visited", type="primary"):
            update = {
                "Status": ds.STATUS_VISITED, "Visit Date": pd.to_datetime(visit_date),
                "Dishes": dishes.strip(), "Notes": notes.strip(),
            }
            for rater in ds.RATERS:
                update[rater] = present.get(rater, "")
            ds.update_row(idx, update)
            st.success(f"{r['Restaurant']} moved to visited!")
            st.cache_data.clear()
            st.rerun()


# ---------- leaderboard ----------

def leaderboard(df: pd.DataFrame) -> None:
    vis = ds.visited(df)
    rated = vis[vis["Group_Rating"].notna()]
    if rated.empty:
        st.info("No rated visits yet — add ratings to build the leaderboard.")
        return

    st.markdown("#### 🏆 Top restaurants")
    top = rated.sort_values("Group_Rating", ascending=False).head(10)
    st.dataframe(
        top[["Restaurant", "Country", "Group_Rating", "Visit Date"]].assign(
            **{"Visit Date": pd.to_datetime(top["Visit Date"], errors="coerce").dt.strftime("%b %d, %Y")}
        ).rename(columns={"Group_Rating": "Group"}),
        hide_index=True, width="stretch",
        column_config={"Group": st.column_config.NumberColumn("Group", format="%.1f ⭐")},
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🌍 Countries by average")
        by_country = (
            rated.groupby("Country")["Group_Rating"].agg(["mean", "count"])
            .sort_values("mean", ascending=False).round(1)
            .rename(columns={"mean": "Avg", "count": "Visits"})
        )
        st.dataframe(by_country, width="stretch")
    with c2:
        st.markdown("#### 👥 Each person's favorite")
        picks = []
        for rater in ds.RATERS:
            sub = vis[vis[rater].notna()]
            if sub.empty:
                continue
            fav = sub.loc[sub[rater].idxmax()]
            picks.append({"Who": rater, "Favorite": fav["Restaurant"], "Rating": f"{fav[rater]:g}"})
        if picks:
            st.dataframe(pd.DataFrame(picks), hide_index=True, width="stretch")
        else:
            st.caption("No individual ratings yet.")


# ---------- wishlist tab ----------

def wishlist_view(df: pd.DataFrame) -> None:
    wish = ds.wishlist(df)
    if wish.empty:
        st.info("Nothing on the wishlist yet. Open a country and add a ‘Want to go’ spot.")
        return
    st.caption(f"{len(wish)} spot{'s' if len(wish) != 1 else ''} to try, across {wish['ISO_A3'].nunique()} countries.")
    for country, g in wish.groupby("Country"):
        st.markdown(f"**{country}**")
        for _idx, r in g.iterrows():
            link = f" — [📍 Maps]({r['Maps_URL']})" if str(r.get("Maps_URL", "")).strip() else ""
            note = f" · {r['Notes']}" if str(r.get("Notes", "")).strip() else ""
            st.markdown(f"- {r['Restaurant']}{link}{note}")


# ---------- all visits table ----------

def all_visits_table(df: pd.DataFrame) -> None:
    show = df.copy()
    show["Visit Date"] = pd.to_datetime(show["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")
    show = show.rename(columns={"Group_Rating": "Group"})
    cols = ["Country", "Restaurant", "Status", "Group", *ds.RATERS, "Visit Date", "Dishes", "Notes", "Maps_URL"]
    st.dataframe(show[cols], hide_index=True, width="stretch")
    st.download_button(
        "⬇️ Download CSV",
        data=df.to_csv(index=False),
        file_name="africax_restaurants.csv",
        mime="text/csv",
    )
