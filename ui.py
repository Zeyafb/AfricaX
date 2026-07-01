"""AfricaX UI layer — Streamlit components for the African Restaurant Passport.

Ranking model: there are no 1–10 ratings. Each member submits an *ordered* ranking
of the places they've been (favourite first) on the **My Rankings** page; the group
consensus (median-of-percentiles → overall rank, ported in ``rankings.py``) is what
the app shows everywhere. A restaurant's consensus is surfaced as a familiar **X/10
star** (median percentile ÷ 10) so the scoreboard reads naturally.

Every write goes through ``data_store``; this module never touches the CSV.
Accessibility: inputs are labelled, the sidebar country filter is a full keyboard
alternative to clicking the map, and map states are also given text labels.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

import data_store as ds
import rankings as rk
from mapview import build_map, country_at_click, legend_html, load_geo

# Member accent colours (match the mockup avatars: green/blue/purple/orange/gold).
AVATAR_COLORS = {
    "Fayez": "#2E7D5B",
    "Muhammad": "#2F6FC7",
    "Seth": "#7B54C0",
    "Ian": "#D2691E",
    "Shubham": "#E0A500",
}

# ISO_A3 → ISO_A2 for African countries, so we can render a flag emoji.
_A3_A2 = {
    "DZA": "DZ", "AGO": "AO", "BEN": "BJ", "BWA": "BW", "BFA": "BF", "BDI": "BI",
    "CPV": "CV", "CMR": "CM", "CAF": "CF", "TCD": "TD", "COM": "KM", "COG": "CG",
    "COD": "CD", "CIV": "CI", "DJI": "DJ", "EGY": "EG", "GNQ": "GQ", "ERI": "ER",
    "SWZ": "SZ", "ETH": "ET", "GAB": "GA", "GMB": "GM", "GHA": "GH", "GIN": "GN",
    "GNB": "GW", "KEN": "KE", "LSO": "LS", "LBR": "LR", "LBY": "LY", "MDG": "MG",
    "MWI": "MW", "MLI": "ML", "MRT": "MR", "MUS": "MU", "MAR": "MA", "MOZ": "MZ",
    "NAM": "NA", "NER": "NE", "NGA": "NG", "RWA": "RW", "STP": "ST", "SEN": "SN",
    "SYC": "SC", "SLE": "SL", "SOM": "SO", "ZAF": "ZA", "SSD": "SS", "SDN": "SD",
    "TZA": "TZ", "TGO": "TG", "TUN": "TN", "UGA": "UG", "ZMB": "ZM", "ZWE": "ZW",
    "ESH": "EH",
}


def flag(iso3: str) -> str:
    a2 = _A3_A2.get(str(iso3).upper())
    if not a2:
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in a2)


# ---------- consensus helpers ----------

def consensus_index(df: pd.DataFrame) -> dict:
    """{restaurant: {median, overall_rank, coverage, ranked_by, ...}} from rankings."""
    rows = rk.consensus(rk.rankings_from_df(df), min_coverage=1)
    return {r["restaurant"]: r for r in rows}


def score10(median: float) -> str:
    """Median percentile (0–100) shown as a familiar X/10."""
    return f"{median / 10:.1f}/10"


# ---------- html atoms ----------

def avatar(name: str, size: int = 30) -> str:
    colour = AVATAR_COLORS.get(name, "#777")
    fs = max(11, size // 2 - 2)
    return (
        f"<span title='{name}' style='display:inline-flex;align-items:center;"
        f"justify-content:center;width:{size}px;height:{size}px;border-radius:50%;"
        f"background:{colour};color:#fff;font-weight:700;font-size:{fs}px;"
        f"margin-left:-6px;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.15);'>"
        f"{name[0].upper()}</span>"
    )


def avatars(names, size: int = 30) -> str:
    inner = "".join(avatar(n, size) for n in names)
    return f"<span style='display:inline-flex;padding-left:6px;'>{inner}</span>"


def chip(text: str) -> str:
    return f"<span class='ax-chip'>{text}</span>"


def status_pill(status: str) -> str:
    if status == ds.STATUS_WISHLIST:
        return "<span class='ax-pill ax-wishlist'>WANT TO GO</span>"
    return "<span class='ax-pill ax-visited'>VISITED</span>"


# ---------- styling ----------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

        /* ---- header ---- */
        .ax-title { font-size: 2.4rem; font-weight: 800; letter-spacing:-.5px; color:#1F2328; line-height:1; margin:0; }
        .ax-sub   { color:#6B7280; font-size:1rem; margin-top:.25rem; }

        /* ---- KPI cards ---- */
        .ax-kpi { display:flex; align-items:center; gap:14px; background:#fff;
                  border:1px solid #EAEAEA; border-radius:14px; padding:16px 18px;
                  box-shadow:0 1px 3px rgba(0,0,0,.04); }
        .ax-kpi-icon { display:flex; align-items:center; justify-content:center;
                       width:44px; height:44px; border-radius:12px; font-size:20px; flex:none; }
        .ax-kpi-num { font-size:1.7rem; font-weight:800; color:#1F2328; line-height:1; }
        .ax-kpi-label { color:#6B7280; font-size:.82rem; margin-top:3px; }

        /* ---- pills & chips ---- */
        .ax-pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem; font-weight:700; vertical-align:middle; }
        .ax-visited  { background:#DDEFE4; color:#12513A; }
        .ax-wishlist { background:#EADDF7; color:#5E3B87; }
        .ax-chip { display:inline-block; background:#EEF3EF; color:#2E5A44; border-radius:8px;
                   padding:4px 10px; font-size:.8rem; font-weight:600; margin:0 6px 6px 0; }

        /* ---- panel / cards ---- */
        .ax-card { background:#fff; border:1px solid #EAEAEA; border-radius:14px; padding:16px 18px; margin-bottom:14px; }
        .ax-label { color:#8A8F98; font-size:.72rem; font-weight:700; letter-spacing:.5px; text-transform:uppercase; }
        .ax-score { font-size:1.6rem; font-weight:800; color:#1F2328; }

        /* ---- sidebar ---- */
        .ax-logo { display:flex; align-items:center; gap:10px; font-weight:800; font-size:1.25rem;
                   color:#1F2328; padding:2px 4px 10px; }
        .ax-stat { display:flex; justify-content:space-between; padding:5px 4px; font-size:.9rem; border-bottom:1px solid #EFEFEF; }
        .ax-stat b { font-weight:800; }
        .ax-about { background:#F6F7F5; border:1px solid #EAEAEA; border-radius:12px; padding:14px; margin-top:6px; }
        .ax-about .t { color:#8A8F98; font-size:.72rem; font-weight:700; letter-spacing:.5px; }
        .ax-about .q { font-style:italic; color:#4B5563; margin-top:8px; }

        /* sidebar radio → nav list */
        section[data-testid="stSidebar"] div[role="radiogroup"] { gap:2px; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            display:flex; align-items:center; width:100%; padding:9px 12px; border-radius:9px;
            font-weight:600; color:#3a3a3a; cursor:pointer; margin:0;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background:#EEF3EF; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background:#E3F0E8; color:#1C5C41;
        }

        .stButton>button, .stDownloadButton>button { border-radius:9px; font-weight:600; }
        h2, h3 { color:#1F2328; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- header ----------

def header(df: pd.DataFrame) -> None:
    left, right = st.columns([0.62, 0.38])
    with left:
        st.markdown(
            "<div class='ax-title'>AFRICAX</div>"
            "<div class='ax-sub'>African Restaurant Passport 🌐</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"<div style='display:flex;justify-content:flex-end;align-items:center;height:100%;'>"
            f"{avatars(ds.RATERS, 34)}</div>",
            unsafe_allow_html=True,
        )
        with st.popover("👥 Edit Group", use_container_width=False):
            st.caption("The tasting crew (fixed in config):")
            for n in ds.RATERS:
                st.markdown(f"{avatar(n, 24)} &nbsp; **{n}**", unsafe_allow_html=True)


# ---------- KPI cards ----------

def kpi_cards(df: pd.DataFrame) -> None:
    vis = ds.visited(df)
    wish = ds.wishlist(df)
    idx = consensus_index(df)
    if idx:
        avg = sum(r["median"] for r in idx.values()) / len(idx)
        group_score = score10(avg)
    else:
        group_score = "—"

    cards = [
        ("🌍", "#E3F0E8", f"{vis['ISO_A3'].nunique():,}", "Countries Visited"),
        ("🍴", "#E3F0E8", f"{len(vis):,}", "Places Visited"),
        ("🔖", "#EADDF7", f"{len(wish):,}", "On Wishlist"),
        ("⭐", "#FBEFD0", group_score, "Group Score"),
    ]
    for col, (icon, tint, num, label) in zip(st.columns(4), cards):
        col.markdown(
            f"<div class='ax-kpi'><div class='ax-kpi-icon' style='background:{tint}'>{icon}</div>"
            f"<div><div class='ax-kpi-num'>{num}</div><div class='ax-kpi-label'>{label}</div></div></div>",
            unsafe_allow_html=True,
        )


# ---------- sidebar (nav + filter + stats + about) ----------

NAV = [
    ("Map", "🗺️"), ("Leaderboard", "🏆"), ("My Rankings", "📊"),
    ("All Spots", "📋"), ("Wishlist", "🔖"), ("Add Spot", "➕"),
]


def sidebar(africa, df: pd.DataFrame) -> str:
    sb = st.sidebar
    sb.markdown("<div class='ax-logo'>🍴 AFRICAX</div>", unsafe_allow_html=True)

    labels = [f"{icon}  {name}" for name, icon in NAV]
    choice = sb.radio("Navigation", labels, label_visibility="collapsed")
    page = NAV[labels.index(choice)][0]

    sb.markdown("<div class='ax-label' style='margin-top:8px'>Country Filter</div>", unsafe_allow_html=True)
    names = sorted(africa["name"].tolist())
    iso_by_name = dict(zip(africa["name"], africa["iso_a3"]))
    status = ds.status_by_iso(df)

    def label(n: str) -> str:
        s = status.get(iso_by_name[n])
        return n + (" ✓" if s == ds.STATUS_VISITED else (" ★" if s == ds.STATUS_WISHLIST else ""))

    current = st.session_state.get("selected_country")
    idx = names.index(current["name"]) + 1 if current and current["name"] in names else 0
    pick = sb.selectbox(
        "Country", ["All Countries"] + names, index=idx,
        format_func=lambda n: n if n == "All Countries" else label(n),
        label_visibility="collapsed",
        help="✓ visited · ★ wishlist. Same effect as clicking the map.",
    )
    if pick != "All Countries":
        st.session_state["selected_country"] = {"name": pick, "iso_a3": iso_by_name[pick]}

    # quick stats
    total = len(africa)
    lit = set(ds.visited(df)["ISO_A3"]) | set(ds.wishlist(df)["ISO_A3"])
    stats = [
        ("Visited", ds.visited(df)["ISO_A3"].nunique(), "#2E7D5B"),
        ("Wishlist", ds.wishlist(df)["ISO_A3"].nunique(), "#8B5FBF"),
        ("Not Visited", total - len(lit), "#6B7280"),
        ("Total Countries", total, "#1F2328"),
    ]
    sb.markdown("<div class='ax-label' style='margin-top:14px'>Quick Stats</div>", unsafe_allow_html=True)
    sb.markdown(
        "".join(f"<div class='ax-stat'><span>{n}</span><b style='color:{c}'>{v}</b></div>" for n, v, c in stats),
        unsafe_allow_html=True,
    )

    sb.markdown(
        "<div class='ax-about'><div class='t'>ABOUT</div>"
        "Our group's journey to try the best African restaurants country by country."
        "<div class='q'>Eat well. Rate honestly.<br>Explore Africa. 🏝️</div></div>",
        unsafe_allow_html=True,
    )
    return page


# ---------- Map page ----------

def map_page(africa, df: pd.DataFrame) -> None:
    col_map, col_detail = st.columns([0.58, 0.42], gap="large")
    with col_map:
        m = build_map(africa, ds.status_by_iso(df), ds.country_stats(df))
        from streamlit_folium import st_folium
        state = st_folium(m, width=None, height=560, key="africa_map")
        if state and state.get("last_object_clicked"):
            c = state["last_object_clicked"]
            hit = country_at_click(africa, c["lat"], c["lng"])
            current = (st.session_state.get("selected_country") or {}).get("iso_a3")
            if hit and hit["iso_a3"] != current:
                st.session_state["selected_country"] = hit
                st.rerun()
        st.markdown(legend_html(), unsafe_allow_html=True)
        st.caption("Click a country to see its details and spots.")
    with col_detail:
        country_detail(df, st.session_state.get("selected_country"))


def country_detail(df: pd.DataFrame, selected: Optional[dict]) -> None:
    if not selected:
        st.info("Pick a country on the map or in the sidebar to see its spots and consensus.")
        return

    name, iso = selected["name"], selected["iso_a3"]
    rows = df[df["ISO_A3"] == iso]
    vis = rows[rows["Status"] == ds.STATUS_VISITED]
    wish = rows[rows["Status"] == ds.STATUS_WISHLIST]
    idx = consensus_index(df)

    overall_status = ds.STATUS_VISITED if not vis.empty else (ds.STATUS_WISHLIST if not wish.empty else None)
    pill = status_pill(overall_status) if overall_status else ""
    st.markdown(
        f"<div style='font-size:1.5rem;font-weight:800;'>{flag(iso)} {name} &nbsp;{pill}</div>",
        unsafe_allow_html=True,
    )

    tab_over, tab_spots = st.tabs(["Overview", f"Spots ({len(rows)})"])

    with tab_over:
        _overview(vis, wish, idx)
    with tab_spots:
        _spots_tab(vis, wish, idx)

    st.markdown("---")
    with st.expander(f"➕ Add a spot in {name}", expanded=rows.empty):
        _add_form(name, iso)


def _overview(vis: pd.DataFrame, wish: pd.DataFrame, idx: dict) -> None:
    if not vis.empty:
        scored = [(r, idx.get(r["Restaurant"])) for _, r in vis.iterrows()]
        scored_ranked = [t for t in scored if t[1]]
        head_row, head = min(scored_ranked, key=lambda t: t[1]["overall_rank"]) if scored_ranked else (vis.iloc[0], None)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='ax-label'>Consensus</div>", unsafe_allow_html=True)
            if head:
                st.markdown(
                    f"<div class='ax-score'>⭐ {score10(head['median'])}</div>"
                    f"<div style='color:#6B7280;font-size:.85rem'>#{head['overall_rank']} overall · "
                    f"{head['coverage']} ranked</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<div style='color:#6B7280'>No rankings yet</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("<div class='ax-label'>Ranked by</div>", unsafe_allow_html=True)
            who = sorted({p for _, h in scored_ranked for p in h["ranked_by"]}, key=ds.RATERS.index) if scored_ranked else []
            st.markdown(avatars(who) if who else "<span style='color:#6B7280'>—</span>", unsafe_allow_html=True)

        notes = str(head_row.get("Notes", "")).strip()
        dishes = str(head_row.get("Dishes", "")).strip()
        if notes:
            st.markdown("<div class='ax-label' style='margin-top:12px'>Notes</div>", unsafe_allow_html=True)
            st.write(notes)
        if dishes:
            st.markdown("<div class='ax-label' style='margin-top:8px'>Top Dishes</div>", unsafe_allow_html=True)
            st.markdown("".join(chip(d.strip()) for d in dishes.split(",") if d.strip()), unsafe_allow_html=True)

    if not wish.empty:
        st.markdown("<div class='ax-label' style='margin-top:12px'>Want to go</div>", unsafe_allow_html=True)
        for _, r in wish.iterrows():
            _wishlist_summary(r)

    if vis.empty and wish.empty:
        st.caption("No visits or wishlist spots logged here yet.")


def _spots_tab(vis: pd.DataFrame, wish: pd.DataFrame, idx: dict) -> None:
    if vis.empty and wish.empty:
        st.caption("Nothing here yet.")
        return
    for _, r in vis.iterrows():
        _visit_card(r, idx.get(r["Restaurant"]))
    for _, r in wish.iterrows():
        _wishlist_card(r)


def _rank_row(r: pd.Series) -> str:
    parts = []
    for m in ds.RATERS:
        v = r[m]
        parts.append(f"{avatar(m, 22)}<sup>{int(v)}</sup>" if pd.notna(v) else "")
    inner = " ".join(p for p in parts if p)
    return f"<div style='margin-top:6px'>{inner}</div>" if inner else ""


def _visit_card(r: pd.Series, cons: Optional[dict]) -> None:
    with st.container(border=True):
        top = st.columns([3, 1])
        badge = f"#{cons['overall_rank']}" if cons else "—"
        score = f"⭐ {score10(cons['median'])}" if cons else "unranked"
        top[0].markdown(f"**{r['Restaurant']}**", unsafe_allow_html=True)
        top[1].markdown(
            f"<div style='text-align:right'><b>{badge}</b><br>"
            f"<span style='color:#6B7280;font-size:.8rem'>{score}</span></div>",
            unsafe_allow_html=True,
        )
        if str(r.get("Dishes", "")).strip():
            st.markdown("".join(chip(d.strip()) for d in str(r["Dishes"]).split(",") if d.strip()), unsafe_allow_html=True)
        rr = _rank_row(r)
        if rr:
            st.markdown(rr, unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.caption(r["Notes"])
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("Edit / delete"):
            _edit_form(r)


def _wishlist_card(r: pd.Series) -> None:
    with st.container(border=True):
        st.markdown(f"**{r['Restaurant']}** {status_pill(ds.STATUS_WISHLIST)}", unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.caption(r["Notes"])
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("✅ Mark as visited / edit"):
            _mark_visited_form(r)


def _wishlist_summary(r: pd.Series) -> None:
    """Read-only wishlist card for the Overview tab. The interactive 'Mark as
    visited' form lives only in the Spots tab, so form keys never collide across
    the two tabs (both tabs execute on every Streamlit run)."""
    with st.container(border=True):
        st.markdown(f"**{r['Restaurant']}** {status_pill(ds.STATUS_WISHLIST)}", unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.caption(r["Notes"])
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        st.caption("→ Use the **Spots** tab to mark visited or edit.")


# ---------- forms (no rating sliders — ranks are set on the My Rankings page) ----------

def _add_form(name: str, iso: str) -> None:
    kind = st.radio(
        "Type", ["Visited", "Want to go (wishlist)"], horizontal=True, key=f"kind_{iso}",
        help="Log somewhere you've been, or bookmark a place to try. Rank visited spots on the My Rankings page.",
    )
    wishlist = kind.startswith("Want")
    with st.form(key=f"add_{iso}", clear_on_submit=True):
        restaurant = st.text_input("Restaurant name", placeholder="e.g., Sweet Sweet Kitchen")
        maps_url = st.text_input("Google Maps link (optional)", placeholder="https://maps.app.goo.gl/…")
        dishes = st.text_input("Dishes (comma-separated, optional)", placeholder="jollof, suya")
        notes = st.text_area("Notes (optional)")
        visit_date = None if wishlist else st.date_input("Visit date", value=date.today(), format="MM/DD/YYYY")
        if st.form_submit_button("Add", type="primary"):
            if not restaurant.strip():
                st.error("Restaurant name is required.")
                return
            row = {
                "Country": name, "ISO_A3": iso, "Restaurant": restaurant.strip(),
                "Dishes": dishes.strip(), "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                "Status": ds.STATUS_WISHLIST if wishlist else ds.STATUS_VISITED,
            }
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
        visit_date = c1.date_input("Visit date", value=dt.date() if pd.notna(dt) else date.today(),
                                   format="MM/DD/YYYY", key=f"ed_{idx}")
        dishes = c2.text_input("Dishes", value=r.get("Dishes", ""), key=f"edi_{idx}")
        notes = st.text_area("Notes", value=r.get("Notes", ""), key=f"en_{idx}")
        maps_url = st.text_input("Google Maps link", value=r.get("Maps_URL", ""), key=f"em_{idx}")
        col_u, col_d = st.columns(2)
        if col_u.form_submit_button("Save", type="primary"):
            ds.update_row(idx, {
                "Restaurant": restaurant.strip(), "Dishes": dishes.strip(),
                "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                "Visit Date": pd.to_datetime(visit_date),
            })
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
        if st.form_submit_button("Mark as visited", type="primary"):
            ds.update_row(idx, {
                "Status": ds.STATUS_VISITED, "Visit Date": pd.to_datetime(visit_date),
                "Dishes": dishes.strip(), "Notes": notes.strip(),
            })
            st.success(f"{r['Restaurant']} moved to visited! Add your rank on the My Rankings page.")
            st.cache_data.clear()
            st.rerun()


# ---------- Leaderboard (consensus) ----------

def leaderboard_page(df: pd.DataFrame) -> None:
    st.subheader("🏆 Leaderboard")
    st.caption("Group consensus — median of everyone's normalised rankings (the Movie Ranks method).")
    tbl = rk.consensus_table(df, min_coverage=1)
    if tbl.empty:
        st.info("No rankings yet. Head to **My Rankings** and add your order to build the leaderboard.")
        return

    show = tbl.copy()
    show["Score"] = (show["median"] / 10).round(1)
    show = show.rename(columns={
        "overall_rank": "#", "restaurant": "Restaurant", "country": "Country",
        "coverage": "Ranked by", "ranked_by": "Members",
    })[["#", "Restaurant", "Country", "Score", "Ranked by", "Members"]]
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={"Score": st.column_config.NumberColumn("Score", format="%.1f ⭐")},
    )

    st.markdown("#### 👥 Each person's #1")
    picks = []
    for m in ds.RATERS:
        sub = df[pd.to_numeric(df[m], errors="coerce") == 1]
        if not sub.empty:
            picks.append({"Who": m, "Favourite": sub.iloc[0]["Restaurant"], "Country": sub.iloc[0]["Country"]})
    if picks:
        st.dataframe(pd.DataFrame(picks), hide_index=True, width="stretch")
    else:
        st.caption("No #1 picks submitted yet.")


# ---------- My Rankings (the built-in ranking input for every member) ----------

def my_rankings_page(df: pd.DataFrame) -> None:
    st.subheader("📊 My Rankings")
    st.caption("Pick your name, then number the places you've been — **1 = favourite**. "
               "Leave a spot blank if you haven't been. Your order feeds the group consensus.")

    vis = ds.visited(df).sort_values("Restaurant")
    if vis.empty:
        st.info("No visited spots to rank yet. Add some on **Add Spot** first.")
        return

    member = st.selectbox("Who are you?", ds.RATERS,
                          format_func=lambda n: f"{n}")
    st.markdown(f"{avatar(member)} &nbsp; Ranking as **{member}**", unsafe_allow_html=True)

    editor = vis[["Restaurant", "Country", member]].rename(columns={member: "My rank"})
    editor["My rank"] = pd.to_numeric(editor["My rank"], errors="coerce").astype("Int64")

    edited = st.data_editor(
        editor, hide_index=True, width="stretch", key=f"rank_editor_{member}",
        disabled=["Restaurant", "Country"],
        column_config={
            "My rank": st.column_config.NumberColumn(
                "My rank", help="1 = favourite. Blank = not ranked.",
                min_value=1, max_value=len(vis), step=1,
            )
        },
    )

    c1, c2 = st.columns([1, 3])
    if c1.button("💾 Save my ranking", type="primary"):
        ranked = edited.dropna(subset=["My rank"]).copy()
        ranked["My rank"] = ranked["My rank"].astype(int)
        ordered = ranked.sort_values("My rank")["Restaurant"].tolist()
        if len(set(ranked["My rank"])) != len(ranked):
            st.warning("Duplicate rank numbers — I'll order by the numbers you gave and renumber cleanly.")
        ds.set_ranking(member, ordered)
        st.success(f"Saved {member}'s ranking of {len(ordered)} spot{'s' if len(ordered) != 1 else ''}.")
        st.cache_data.clear()
        st.rerun()
    if c2.button("Clear my ranking"):
        ds.set_ranking(member, [])
        st.info(f"Cleared {member}'s ranking.")
        st.cache_data.clear()
        st.rerun()

    # live preview of the resulting consensus
    st.markdown("---")
    st.markdown("#### 🔮 Current consensus")
    tbl = rk.consensus_table(df, min_coverage=1)
    if tbl.empty:
        st.caption("No rankings submitted yet — yours will start the board.")
    else:
        prev = tbl.copy()
        prev["Score"] = (prev["median"] / 10).round(1)
        st.dataframe(
            prev.rename(columns={"overall_rank": "#", "restaurant": "Restaurant", "country": "Country"})
                [["#", "Restaurant", "Country", "Score"]],
            hide_index=True, width="stretch",
            column_config={"Score": st.column_config.NumberColumn("Score", format="%.1f ⭐")},
        )


# ---------- All Spots ----------

def all_spots_page(df: pd.DataFrame) -> None:
    st.subheader("📋 All Spots")
    idx = consensus_index(df)
    show = df.copy()
    show["Overall"] = show["Restaurant"].map(lambda n: idx[n]["overall_rank"] if n in idx else pd.NA)
    show["Score"] = show["Restaurant"].map(lambda n: round(idx[n]["median"] / 10, 1) if n in idx else pd.NA)
    show["Visit Date"] = pd.to_datetime(show["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")
    cols = ["Overall", "Country", "Restaurant", "Status", "Score", *ds.RATERS, "Visit Date", "Dishes", "Notes", "Maps_URL"]
    st.dataframe(
        show[cols].sort_values(["Status", "Overall"], na_position="last"),
        hide_index=True, width="stretch",
        column_config={
            "Score": st.column_config.NumberColumn("Score", format="%.1f ⭐"),
            "Overall": st.column_config.NumberColumn("Overall", format="#%d"),
        },
    )
    st.download_button("⬇️ Download CSV", data=df.to_csv(index=False),
                       file_name="africax_restaurants.csv", mime="text/csv")


# ---------- Wishlist ----------

def wishlist_page(df: pd.DataFrame) -> None:
    st.subheader("🔖 Wishlist")
    wish = ds.wishlist(df)
    if wish.empty:
        st.info("Nothing on the wishlist yet. Use **Add Spot** to bookmark a place to try.")
        return
    st.caption(f"{len(wish)} spot{'s' if len(wish) != 1 else ''} to try across "
               f"{wish['ISO_A3'].nunique()} countries.")
    for country, g in wish.groupby("Country"):
        st.markdown(f"**{flag(g.iloc[0]['ISO_A3'])} {country}**", unsafe_allow_html=True)
        for _, r in g.iterrows():
            link = f" — [📍 Maps]({r['Maps_URL']})" if str(r.get("Maps_URL", "")).strip() else ""
            note = f" · {r['Notes']}" if str(r.get("Notes", "")).strip() else ""
            st.markdown(f"- {r['Restaurant']}{link}{note}")


# ---------- Add Spot ----------

def add_spot_page(africa, df: pd.DataFrame) -> None:
    st.subheader("➕ Add a Spot")
    names = sorted(africa["name"].tolist())
    iso_by_name = dict(zip(africa["name"], africa["iso_a3"]))
    current = st.session_state.get("selected_country")
    idx = names.index(current["name"]) if current and current["name"] in names else 0
    country = st.selectbox("Country", names, index=idx)
    st.markdown(f"### {flag(iso_by_name[country])} {country}")
    _add_form(country, iso_by_name[country])
