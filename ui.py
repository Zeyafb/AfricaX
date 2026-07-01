"""AfricaX UI layer — built to the AfricaX.dc.html design concept.

A "restaurant passport": map-first, card-based, consensus-ranking driven. There are
no 1–10 ratings — each member drags/orders the places they've been on **My Rankings**,
and the group consensus (median of normalised ranks, ``rankings.py``) is shown as an
X/10 star. Every write goes through ``data_store``; this module never touches storage.

Deviations from the dc are intentional: no fabricated dishes/notes/reviews (those
render only when the group fills them in), up/down reordering instead of true drag
(Streamlit has no native drag), and the real Folium map instead of the dc's SVG dots.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

import data_store as ds
import rankings as rk
from mapview import build_map, country_at_click, legend_html, load_geo

# Member accent colours (match the dc avatars).
AVATAR_COLORS = {
    "Fayez": "#2E7D5B", "Muhammad": "#2F6FC7", "Seth": "#7B54C0",
    "Ian": "#D2691E", "Shubham": "#E0A500",
}

# ISO_A3 → 2-letter code for the little country-code chips the dc uses.
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

PAGES = ["Map", "My Rankings", "Leaderboard", "All Spots", "Wishlist", "Add Spot"]
_NAV_ICON = {"Map": "🗺", "My Rankings": "📊", "Leaderboard": "🏆",
             "All Spots": "📋", "Wishlist": "🔖", "Add Spot": "＋"}


def code(iso3: str) -> str:
    return _A3_A2.get(str(iso3).upper(), str(iso3)[:2].upper())


def flag(iso3: str) -> str:
    a2 = _A3_A2.get(str(iso3).upper())
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in a2) if a2 else "🌍"


def goto(page: str) -> None:
    """Callback for CTA buttons — switch the active page (nav radio key='page')."""
    st.session_state["page"] = page


# ---------- consensus helpers ----------

def consensus_index(df: pd.DataFrame) -> dict:
    rows = rk.consensus(rk.rankings_from_df(df), min_coverage=1)
    return {r["restaurant"]: r for r in rows}


def score10(median: float) -> str:
    return f"{median / 10:.1f}"


def _ranked_members(df: pd.DataFrame) -> list:
    return [m for m in ds.RATERS if pd.to_numeric(df[m], errors="coerce").notna().any()]


# ---------- html atoms ----------

def avatar(name: str, size: int = 30) -> str:
    c = AVATAR_COLORS.get(name, "#777")
    return (f"<span title='{name}' style='display:inline-flex;align-items:center;justify-content:center;"
            f"width:{size}px;height:{size}px;border-radius:50%;background:{c};color:#fff;font-weight:700;"
            f"font-size:{max(11,size//2-2)}px;margin-left:-6px;border:2px solid #fff;'>{name[0]}</span>")


def avatars(names, size: int = 30) -> str:
    return "<span style='display:inline-flex;padding-left:6px'>" + "".join(avatar(n, size) for n in names) + "</span>"


def code_chip(iso3: str, kind: str = "visited") -> str:
    bg, ink = {"visited": ("#E3F0E8", "#12513A"), "wishlist": ("#EADDF7", "#5E3B87"),
               "none": ("#EDEDEA", "#6B7280")}[kind]
    return (f"<span style='display:inline-flex;align-items:center;justify-content:center;width:38px;height:26px;"
            f"border-radius:6px;background:{bg};color:{ink};font-size:12px;font-weight:700;letter-spacing:.05em'>"
            f"{code(iso3)}</span>")


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
        .main .block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1400px; }
        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
        html, body, [class*="css"] { font-family: 'Source Sans 3','Source Sans Pro',system-ui,sans-serif; }

        .ax-title { font-size: 2.4rem; font-weight: 800; letter-spacing:-.01em; color:#1F2328; line-height:1; margin:0; }
        .ax-sub { color:#6B7280; font-size:1rem; margin-top:.3rem; }

        .ax-kpi { display:flex; align-items:center; gap:13px; background:#fff; border:1px solid #EAEAE4;
                  border-radius:14px; padding:15px 17px; box-shadow:0 1px 2px rgba(0,0,0,.03); }
        .ax-kpi-icon { display:flex; align-items:center; justify-content:center; width:42px; height:42px;
                       border-radius:11px; font-size:19px; flex:none; }
        .ax-kpi-num { font-size:1.65rem; font-weight:800; line-height:1; }
        .ax-kpi-label { color:#6B7280; font-size:.8rem; margin-top:3px; }

        .ax-pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.7rem; font-weight:700;
                   letter-spacing:.03em; vertical-align:middle; }
        .ax-visited { background:#DDEFE4; color:#12513A; }
        .ax-wishlist { background:#EADDF7; color:#5E3B87; }
        .ax-chip { display:inline-block; background:#EEF3EF; color:#2E5A44; border-radius:999px;
                   padding:5px 11px; font-size:.78rem; font-weight:600; margin:0 6px 6px 0; }

        .ax-card { background:#fff; border:1px solid #EAEAE4; border-radius:12px; padding:15px 17px; }
        .ax-label { color:#8A8F98; font-size:.66rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
        .ax-nudge { background:linear-gradient(90deg,#EAF4EE,#F3F9F5); border:1px solid #CDE6D8;
                    border-radius:14px; padding:15px 20px; }

        .ax-stat { display:flex; justify-content:space-between; padding:4px 2px; font-size:.88rem; }
        .ax-about { background:#fff; border:1px solid #EAEAE4; border-radius:12px; padding:13px 15px; margin-top:4px; }
        .ax-logo { display:flex; align-items:center; gap:9px; font-weight:800; font-size:1.15rem;
                   letter-spacing:.04em; padding:2px 4px 8px; }

        section[data-testid="stSidebar"] div[role="radiogroup"] { gap:2px; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            display:flex; align-items:center; width:100%; padding:9px 12px; border-radius:9px;
            font-weight:600; font-size:.92rem; color:#3f454c; cursor:pointer; margin:0; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background:#EEF3EF; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background:#E3F0E8; color:#12513A; }

        .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button { border-radius:9px; font-weight:700; }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:12px; }
        h2,h3 { color:#1F2328; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- header ----------

def header(df: pd.DataFrame) -> None:
    left, right = st.columns([0.6, 0.4])
    with left:
        st.markdown("<div class='ax-title'>AFRICAX</div>"
                    "<div class='ax-sub'>African Restaurant Passport 🌐</div>", unsafe_allow_html=True)
    with right:
        st.markdown(f"<div style='display:flex;justify-content:flex-end;padding-top:6px'>{avatars(ds.RATERS,34)}</div>",
                    unsafe_allow_html=True)
        with st.popover("👥 Edit Group"):
            st.caption("The tasting crew (fixed in config):")
            for n in ds.RATERS:
                st.markdown(f"{avatar(n,24)} &nbsp; **{n}**", unsafe_allow_html=True)


# ---------- KPI row ----------

def kpi_row(df: pd.DataFrame) -> None:
    vis, wish = ds.visited(df), ds.wishlist(df)
    idx = consensus_index(df)
    top = min(idx.values(), key=lambda r: r["overall_rank"]) if idx else None
    top_num = f"<span class='ax-kpi-num'>{score10(top['median'])}</span><span style='font-size:.8rem;font-weight:600;color:#9AA0A8'>/10</span>" if top else "<span class='ax-kpi-num'>—</span>"
    top_label = f"Top consensus · {top['restaurant']}" if top else "No rankings yet"

    cards = [
        ("🌍", "#E3F0E8", f"<span class='ax-kpi-num'>{vis['ISO_A3'].nunique()}</span>", "Countries Visited"),
        ("🍴", "#E3F0E8", f"<span class='ax-kpi-num'>{len(vis)}</span>", "Places Visited"),
        ("🔖", "#EADDF7", f"<span class='ax-kpi-num'>{len(wish)}</span>", "On Wishlist"),
        ("⭐", "#FBEFD0", top_num, top_label),
    ]
    for col, (icon, tint, num, label) in zip(st.columns(4), cards):
        col.markdown(f"<div class='ax-kpi'><div class='ax-kpi-icon' style='background:{tint}'>{icon}</div>"
                     f"<div><div style='display:flex;align-items:baseline;gap:3px'>{num}</div>"
                     f"<div class='ax-kpi-label'>{label}</div></div></div>", unsafe_allow_html=True)


# ---------- sidebar ----------

def sidebar(africa, df: pd.DataFrame) -> str:
    sb = st.sidebar
    st.session_state.setdefault("page", "Map")
    sb.markdown("<div class='ax-logo'>🍴 AFRICAX</div>", unsafe_allow_html=True)

    sb.radio("Navigation", PAGES, key="page", label_visibility="collapsed",
             format_func=lambda p: f"{_NAV_ICON.get(p, '')}  {p}")

    sb.markdown("<div class='ax-label' style='margin-top:8px'>Country filter</div>", unsafe_allow_html=True)
    names = sorted(africa["name"].tolist())
    iso_by_name = dict(zip(africa["name"], africa["iso_a3"]))
    status = ds.status_by_iso(df)

    def label(n):
        s = status.get(iso_by_name[n])
        return n + (" ✓" if s == ds.STATUS_VISITED else (" ★" if s == ds.STATUS_WISHLIST else ""))

    cur = st.session_state.get("selected_country")
    idx = names.index(cur["name"]) + 1 if cur and cur["name"] in names else 0
    pick = sb.selectbox("Jump to country", ["All countries"] + names, index=idx,
                        format_func=lambda n: n if n == "All countries" else label(n),
                        label_visibility="collapsed")
    if pick != "All countries":
        st.session_state["selected_country"] = {"name": pick, "iso_a3": iso_by_name[pick]}

    total = len(africa)
    lit = set(ds.visited(df)["ISO_A3"]) | set(ds.wishlist(df)["ISO_A3"])
    rows = [("Visited", ds.visited(df)["ISO_A3"].nunique(), "#2E7D5B"),
            ("Wishlist", ds.wishlist(df)["ISO_A3"].nunique(), "#8B5FBF"),
            ("Not visited", total - len(lit), "#6B7280")]
    sb.markdown("<div class='ax-label' style='margin-top:14px'>Quick stats</div>", unsafe_allow_html=True)
    html = "".join(f"<div class='ax-stat'><span style='color:#4b5158'>{n}</span>"
                   f"<b style='color:{c}'>{v}</b></div>" for n, v, c in rows)
    html += (f"<div class='ax-stat' style='border-top:1px solid #E7E7E0;padding-top:7px;margin-top:2px'>"
             f"<span style='color:#4b5158'>Total countries</span><b>{total}</b></div>")
    sb.markdown(html, unsafe_allow_html=True)

    sb.markdown("<div class='ax-about'><div class='ax-label'>About</div>"
                "<div style='margin-top:6px;font-size:.82rem;line-height:1.5;color:#3f454c'>"
                "Our group's journey to try the best African restaurants, country by country.</div>"
                "<div style='margin-top:8px;font-size:.78rem;font-style:italic;color:#8A8F98'>"
                "Eat well. Rank honestly. Explore Africa. 🏝</div></div>", unsafe_allow_html=True)

    badge = "💾 Saved to Google Sheets" if ds.using_sheets() else "💾 Local CSV (dev — not shared)"
    colour = "#2E7D5B" if ds.using_sheets() else "#9AA0A8"
    sb.markdown(f"<div style='margin-top:10px;font-size:.72rem;font-weight:600;color:{colour}'>{badge}</div>",
                unsafe_allow_html=True)
    return st.session_state["page"]


# ---------- rank nudge (map landing) ----------

def rank_nudge(df: pd.DataFrame) -> None:
    ranked = _ranked_members(df)
    unranked = [m for m in ds.RATERS if m not in ranked]
    if not unranked:
        return
    who = ", ".join(unranked[:-1]) + (" and " + unranked[-1] if len(unranked) > 1 else unranked[0]) \
        if unranked else ""
    verb = "have" if len(unranked) > 1 else "has"
    c1, c2 = st.columns([0.78, 0.22])
    with c1:
        st.markdown(
            f"<div class='ax-nudge'><div style='font-size:1rem;font-weight:700'>🏆 Settle the debate — "
            f"rank the {len(ds.visited(df))} spots you've been to.</div>"
            f"<div style='font-size:.85rem;color:#4b5158;margin-top:2px'>{len(ranked)} of {len(ds.RATERS)} "
            f"have ranked so far. {who} still {verb} to.</div></div>", unsafe_allow_html=True)
    with c2:
        st.write("")
        st.button("Rank your spots →", type="primary", use_container_width=True,
                  on_click=goto, args=("My Rankings",), key="nudge_cta")


# ---------- Map page ----------

def map_page(africa, df: pd.DataFrame) -> None:
    rank_nudge(df)
    st.write("")
    col_map, col_detail = st.columns([0.58, 0.42], gap="large")
    with col_map:
        m = build_map(africa, ds.status_by_iso(df), ds.country_stats(df))
        from streamlit_folium import st_folium
        state = st_folium(m, width=None, height=560, key="africa_map")
        if state and state.get("last_object_clicked"):
            c = state["last_object_clicked"]
            hit = country_at_click(africa, c["lat"], c["lng"])
            if hit and hit["iso_a3"] != (st.session_state.get("selected_country") or {}).get("iso_a3"):
                st.session_state["selected_country"] = hit
                st.rerun()
        st.markdown(legend_html(), unsafe_allow_html=True)
        st.caption("Click a country on the map to see its consensus and spots.")
    with col_detail:
        country_detail(df, st.session_state.get("selected_country"))


def country_detail(df: pd.DataFrame, selected: Optional[dict]) -> None:
    if not selected:
        st.markdown("<div class='ax-card' style='background:#F4F9FC;border-color:#CFE6F2'>"
                    "<b>Pick a country</b><div style='color:#6B7280;font-size:.9rem;margin-top:4px'>"
                    "Click the map or use the sidebar to see restaurants, notes, and rankings.</div></div>",
                    unsafe_allow_html=True)
        st.button("Rank your spots →", type="primary", on_click=goto, args=("My Rankings",), key="detail_cta")
        return

    name, iso = selected["name"], selected["iso_a3"]
    rows = df[df["ISO_A3"] == iso]
    vis, wish = rows[rows["Status"] == ds.STATUS_VISITED], rows[rows["Status"] == ds.STATUS_WISHLIST]
    idx = consensus_index(df)
    kind = "visited" if not vis.empty else ("wishlist" if not wish.empty else "none")
    pill = status_pill(ds.STATUS_VISITED) if not vis.empty else (status_pill(ds.STATUS_WISHLIST) if not wish.empty else "")

    st.markdown(f"<div style='display:flex;align-items:center;gap:10px'>{code_chip(iso, kind)}"
                f"<span style='font-size:1.5rem;font-weight:800'>{name}</span>{pill}</div>", unsafe_allow_html=True)

    tab_over, tab_spots = st.tabs(["Overview", f"Spots ({len(rows)})"])
    with tab_over:
        _overview(vis, wish, idx)
    with tab_spots:
        _spots_tab(vis, wish, idx)
    st.write("")
    with st.expander(f"＋ Add a spot in {name}", expanded=rows.empty):
        _add_form(name, iso)


def _overview(vis, wish, idx) -> None:
    if not vis.empty:
        scored = [(r, idx.get(r["Restaurant"])) for _, r in vis.iterrows()]
        ranked = [t for t in scored if t[1]]
        head_row, head = min(ranked, key=lambda t: t[1]["overall_rank"]) if ranked else (vis.iloc[0], None)
        c1, c2 = st.columns(2)
        with c1:
            if head:
                inner = (f"<div style='display:flex;align-items:baseline;gap:4px;margin-top:4px'>"
                         f"<span style='font-size:2rem;font-weight:800;color:#2E7D5B'>{score10(head['median'])}</span>"
                         f"<span style='font-size:.9rem;color:#9AA0A8'>/10</span></div>"
                         f"<div style='font-size:.82rem;color:#6B7280;font-weight:600'>Overall #{head['overall_rank']} of {len(idx)}</div>")
            else:
                inner = "<div style='color:#6B7280;margin-top:6px'>No rankings yet</div>"
            st.markdown(f"<div class='ax-card'><div class='ax-label'>Consensus</div>{inner}</div>", unsafe_allow_html=True)
        with c2:
            who = sorted({p for _, h in ranked for p in h["ranked_by"]}, key=ds.RATERS.index) if ranked else []
            av = avatars(who) if who else "<span style='color:#6B7280'>—</span>"
            sub = f"{len(who)} of {len(ds.RATERS)} members" if who else "Not ranked yet"
            st.markdown(f"<div class='ax-card'><div class='ax-label'>Ranked by</div>"
                        f"<div style='margin-top:8px'>{av}</div>"
                        f"<div style='margin-top:8px;font-size:.82rem;color:#6B7280;font-weight:600'>{sub}</div></div>",
                        unsafe_allow_html=True)
        # spot card(s)
        for _, r in vis.iterrows():
            _spot_card(r)
    if not wish.empty:
        for _, r in wish.iterrows():
            _wishlist_summary(r)
    if vis.empty and wish.empty:
        st.caption("No visits or wishlist spots logged here yet.")


def _spot_card(r: pd.Series) -> None:
    dishes = [d.strip() for d in str(r.get("Dishes", "")).split(",") if d.strip()]
    notes = str(r.get("Notes", "")).strip()
    body = ""
    if dishes:
        body += "<div style='margin-top:10px'>" + "".join(chip(d) for d in dishes) + "</div>"
    if notes:
        body += f"<div style='margin-top:8px;font-size:.85rem;font-style:italic;color:#6b6f76'>“{notes}”</div>"
    if not dishes and not notes:
        body = "<div style='margin-top:8px;font-size:.82rem;color:#9AA0A8'>No dishes or notes yet — add them from the Spots tab.</div>"
    maps = f"<a href='{r['Maps_URL']}' target='_blank' style='font-size:.8rem'>📍 Maps</a>" if str(r.get("Maps_URL", "")).strip() else ""
    st.markdown(f"<div class='ax-card' style='margin-top:12px'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                f"<b style='font-size:1rem'>{r['Restaurant']}</b>{maps}</div>{body}</div>", unsafe_allow_html=True)


def _spots_tab(vis, wish, idx) -> None:
    if vis.empty and wish.empty:
        st.caption("Nothing here yet.")
        return
    for _, r in vis.iterrows():
        _visit_card(r, idx.get(r["Restaurant"]))
    for _, r in wish.iterrows():
        _wishlist_card(r)


def _visit_card(r: pd.Series, cons: Optional[dict]) -> None:
    with st.container(border=True):
        t = st.columns([3, 1])
        badge = f"#{cons['overall_rank']} · ⭐ {score10(cons['median'])}/10" if cons else "unranked"
        t[0].markdown(f"**{r['Restaurant']}**")
        t[1].markdown(f"<div style='text-align:right;font-size:.8rem;color:#6B7280'>{badge}</div>", unsafe_allow_html=True)
        dishes = [d.strip() for d in str(r.get("Dishes", "")).split(",") if d.strip()]
        if dishes:
            st.markdown("".join(chip(d) for d in dishes), unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.caption(r["Notes"])
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("Edit / delete"):
            _edit_form(r)


def _wishlist_summary(r: pd.Series) -> None:
    city = str(r.get("Notes", "")).strip()
    st.markdown(f"<div class='ax-card' style='margin-top:12px;background:#FBF8FE;border-color:#E4D3F5'>"
                f"<div style='font-size:.8rem;font-weight:700;color:#8B5FBF'>📌 Want to go</div>"
                f"<div style='margin-top:8px;font-size:1rem;font-weight:700'>{r['Restaurant']}</div>"
                + (f"<div style='margin-top:6px;font-size:.85rem;font-style:italic;color:#6b6f76'>“{city}”</div>" if city else "")
                + "</div>", unsafe_allow_html=True)


def _wishlist_card(r: pd.Series) -> None:
    with st.container(border=True):
        st.markdown(f"**{r['Restaurant']}** {status_pill(ds.STATUS_WISHLIST)}", unsafe_allow_html=True)
        if str(r.get("Notes", "")).strip():
            st.caption(r["Notes"])
        if str(r.get("Maps_URL", "")).strip():
            st.markdown(f"[📍 Open in Google Maps]({r['Maps_URL']})")
        with st.expander("✅ Mark as visited / edit"):
            _mark_visited_form(r)


# ---------- forms ----------

def _add_form(name: str, iso: str) -> None:
    kind = st.radio("Type", ["Visited", "Want to go (wishlist)"], horizontal=True, key=f"kind_{iso}")
    wishlist = kind.startswith("Want")
    with st.form(key=f"add_{iso}", clear_on_submit=True):
        restaurant = st.text_input("Restaurant name", placeholder="e.g., Buka")
        maps_url = st.text_input("Google Maps link (optional)", placeholder="https://maps.app.goo.gl/…")
        dishes = st.text_input("Dishes (comma-separated, optional)", placeholder="jollof, suya")
        notes = st.text_area("Notes (optional)")
        visit_date = None if wishlist else st.date_input("Visit date", value=date.today(), format="MM/DD/YYYY")
        if st.form_submit_button("💾 Save spot", type="primary"):
            if not restaurant.strip():
                st.error("Restaurant name is required.")
                return
            row = {"Country": name, "ISO_A3": iso, "Restaurant": restaurant.strip(),
                   "Dishes": dishes.strip(), "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                   "Status": ds.STATUS_WISHLIST if wishlist else ds.STATUS_VISITED}
            if not wishlist:
                row["Visit Date"] = pd.to_datetime(visit_date)
            ds.append_row(row)
            st.success(f"Added {restaurant.strip()}." + ("" if wishlist else " Rank it on My Rankings."))
            st.cache_data.clear()
            st.rerun()


def _edit_form(r: pd.Series) -> None:
    i = r.name
    with st.form(key=f"edit_{i}"):
        restaurant = st.text_input("Restaurant", value=r["Restaurant"], key=f"er_{i}")
        c1, c2 = st.columns(2)
        dt = pd.to_datetime(r["Visit Date"], errors="coerce")
        vd = c1.date_input("Visit date", value=dt.date() if pd.notna(dt) else date.today(),
                           format="MM/DD/YYYY", key=f"ed_{i}")
        dishes = c2.text_input("Dishes", value=r.get("Dishes", ""), key=f"edi_{i}")
        notes = st.text_area("Notes", value=r.get("Notes", ""), key=f"en_{i}")
        maps_url = st.text_input("Google Maps link", value=r.get("Maps_URL", ""), key=f"em_{i}")
        u, d = st.columns(2)
        if u.form_submit_button("Save", type="primary"):
            ds.update_row(i, {"Restaurant": restaurant.strip(), "Dishes": dishes.strip(),
                              "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                              "Visit Date": pd.to_datetime(vd)})
            st.success("Saved.")
            st.cache_data.clear()
            st.rerun()
        if d.form_submit_button("Delete"):
            ds.delete_row(i)
            st.success("Deleted.")
            st.cache_data.clear()
            st.rerun()


def _mark_visited_form(r: pd.Series) -> None:
    i = r.name
    with st.form(key=f"mark_{i}"):
        vd = st.date_input("When did you go?", value=date.today(), format="MM/DD/YYYY", key=f"md_{i}")
        dishes = st.text_input("Dishes", value=r.get("Dishes", ""), key=f"mdi_{i}")
        notes = st.text_area("Notes", value=r.get("Notes", ""), key=f"mn_{i}")
        if st.form_submit_button("Mark as visited", type="primary"):
            ds.update_row(i, {"Status": ds.STATUS_VISITED, "Visit Date": pd.to_datetime(vd),
                              "Dishes": dishes.strip(), "Notes": notes.strip()})
            st.success(f"{r['Restaurant']} moved to visited! Add your rank on My Rankings.")
            st.cache_data.clear()
            st.rerun()


# ---------- My Rankings (reorderable) ----------

def _move(key: str, i: int, delta: int) -> None:
    order = st.session_state[key]
    j = i + delta
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]


def my_rankings_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:1.4rem;font-weight:800'>📊 My Rankings</div>", unsafe_allow_html=True)
    st.caption("Order your spots — **top = favourite**. Your order becomes a 0–100 percentile and feeds the group's median consensus.")

    vis = ds.visited(df).sort_values("Restaurant")
    names = vis["Restaurant"].tolist()
    if not names:
        st.info("No visited spots to rank yet. Add some on **Add Spot** first.")
        return

    member = st.selectbox("Who are you?", ds.RATERS, key="rank_member")
    st.markdown(f"{avatar(member)} &nbsp; Ranking as **{member}**", unsafe_allow_html=True)

    key = f"order_{member}"
    if key not in st.session_state:
        saved = df[pd.to_numeric(df[member], errors="coerce").notna()].sort_values(member)["Restaurant"].tolist()
        st.session_state[key] = saved + [n for n in names if n not in saved]
    order = [n for n in st.session_state[key] if n in names]
    order += [n for n in names if n not in order]
    st.session_state[key] = order

    if not _country_ranked(df, member):
        st.markdown(f"<div class='ax-card' style='background:#FEF7EC;border-color:#F3E2C2;margin:10px 0'>"
                    f"✨ <b>{member} hasn't ranked yet.</b> Order the spots below and hit Save to join the board.</div>",
                    unsafe_allow_html=True)

    cty = dict(zip(vis["Restaurant"], vis["Country"]))
    left, right = st.columns([0.62, 0.38], gap="large")
    with left:
        for i, nm in enumerate(order):
            with st.container(border=True):
                cc = st.columns([0.5, 5, 0.7, 0.7])
                cc[0].markdown(f"<div style='width:30px;height:30px;border-radius:8px;background:#E3F0E8;color:#12513A;"
                               f"font-weight:800;display:flex;align-items:center;justify-content:center'>{i+1}</div>",
                               unsafe_allow_html=True)
                cc[1].markdown(f"**{nm}**  \n<span style='color:#8A8F98;font-size:.82rem'>{cty.get(nm,'')}</span>",
                               unsafe_allow_html=True)
                cc[2].button("▲", key=f"up_{member}_{i}", disabled=(i == 0),
                             on_click=_move, args=(key, i, -1), use_container_width=True)
                cc[3].button("▼", key=f"dn_{member}_{i}", disabled=(i == len(order) - 1),
                             on_click=_move, args=(key, i, 1), use_container_width=True)

        b1, b2 = st.columns([1, 1])
        if b1.button("💾 Save my ranking", type="primary", use_container_width=True):
            ds.set_ranking(member, order)
            st.session_state["_just_saved"] = member
            st.cache_data.clear()
            st.rerun()
        if b2.button("Clear", use_container_width=True):
            ds.set_ranking(member, [])
            st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()
        if st.session_state.get("_just_saved") == member:
            st.success(f"✓ Saved {member}'s ranking.")
            st.session_state.pop("_just_saved", None)
    with right:
        st.markdown("<div class='ax-card' style='background:#F6F6F3'><div style='font-weight:800'>How it works</div>"
                    "<div style='font-size:.82rem;color:#6B7280;margin-top:5px'>Your order becomes a 0–100 percentile "
                    "(your #1 = 100). Everyone's are combined by <b>median</b>, so one outlier can't sink a group "
                    "favourite. Save to update the board below.</div></div>", unsafe_allow_html=True)

    st.write("")
    editorial_consensus(df)


def _country_ranked(df: pd.DataFrame, member: str) -> bool:
    return pd.to_numeric(df[member], errors="coerce").notna().any()


def editorial_consensus(df: pd.DataFrame, title: str = "Group Consensus") -> None:
    """Movie-Ranks-poster-style editorial ranked list of the group consensus:
    numbered ranks, flag + restaurant + country, the 0-100 MEDIAN with a score bar,
    and 'RANKED BY' member avatars, on a warm cream panel."""
    tbl = rk.consensus_table(df, min_coverage=1)
    head = ("<div style='background:#F7F3EC;border:1px solid #E9E1D2;border-radius:16px;padding:20px 24px'>"
            "<div style='display:flex;align-items:baseline;gap:12px;border-bottom:2px solid #1F2328;padding-bottom:8px'>"
            "<span style='font-size:.72rem;font-weight:800;color:#B4A88E'>01</span>"
            f"<span style='font-size:1.25rem;font-weight:800;letter-spacing:.01em'>{title}</span></div>"
            "<div style='font-size:.78rem;color:#9a917f;margin-top:6px;font-style:italic'>"
            "Median of everyone's normalised rankings · higher = the group's favourite</div>")
    if tbl.empty:
        st.markdown(head + "<div style='padding:18px 0;color:#9a917f'>No rankings yet — be the first "
                    "to rank and start the board.</div></div>", unsafe_allow_html=True)
        return
    idx = consensus_index(df)
    iso_by_country = dict(zip(df["Country"], df["ISO_A3"]))
    grid = "display:grid;grid-template-columns:46px 1fr 92px 116px;gap:12px;align-items:center"
    rows = (f"<div style='{grid};margin-top:14px;font-size:.6rem;font-weight:800;letter-spacing:.09em;"
            "text-transform:uppercase;color:#B4A88E'><div>#</div><div>Restaurant</div>"
            "<div>Median</div><div>Ranked by</div></div>")
    for _, r in tbl.iterrows():
        med = float(r["median"])
        barw = max(3, min(100, round(med)))
        who = idx.get(r["restaurant"], {}).get("ranked_by", [])
        fl = flag(iso_by_country.get(r["country"], ""))
        rows += (f"<div style='{grid};padding:13px 0;border-bottom:1px solid #E9E1D2'>"
                 f"<div style='font-size:1.5rem;font-weight:800'>{int(r['overall_rank'])}</div>"
                 f"<div><div style='font-weight:700;font-size:1rem'>{fl} {r['restaurant']}</div>"
                 f"<div style='font-size:.78rem;color:#9a917f'>{r['country']}</div></div>"
                 f"<div><div style='font-size:1.2rem;font-weight:800'>{med:.1f}</div>"
                 f"<div style='height:4px;background:#E4DAC6;border-radius:2px;margin-top:4px'>"
                 f"<div style='height:4px;width:{barw}%;background:#2E7D5B;border-radius:2px'></div></div></div>"
                 f"<div>{avatars(who, 26)}</div></div>")
    st.markdown(head + rows + "</div>", unsafe_allow_html=True)


# ---------- Leaderboard ----------

def leaderboard_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:1.4rem;font-weight:800'>🏆 Leaderboard</div>", unsafe_allow_html=True)
    st.caption("Group consensus — the median of everyone's normalised rankings (the Movie Ranks method).")
    tbl = rk.consensus_table(df, min_coverage=1)
    idx = consensus_index(df)

    if tbl.empty:
        st.markdown("<div class='ax-card' style='background:#F4F9FC;border-color:#CFE6F2;text-align:center;padding:34px'>"
                    "<div style='font-size:2rem'>🥇</div>"
                    "<div style='font-size:1.1rem;font-weight:800;margin-top:8px'>No rankings yet — be the first.</div>"
                    "<div style='color:#6B7280;margin-top:4px'>The board fills in as people rank the spots they've been to.</div>"
                    "</div>", unsafe_allow_html=True)
        st.button("Add your ranking →", type="primary", on_click=goto, args=("My Rankings",), key="lb_cta")
        return

    editorial_consensus(df, title="Official Ranking")

    st.markdown("<div class='ax-label' style='margin-top:18px'>Each person's #1</div>", unsafe_allow_html=True)
    cards = []
    for m in ds.RATERS:
        sub = df[pd.to_numeric(df[m], errors="coerce") == 1]
        top = sub.iloc[0]["Restaurant"] if not sub.empty else "—"
        cards.append(f"<div class='ax-card' style='display:inline-flex;align-items:center;gap:11px;margin:6px 8px 0 0'>"
                     f"{avatar(m,34)}<div><div style='font-size:.75rem;color:#8A8F98'>{m}</div>"
                     f"<div style='font-weight:700'>{top}</div></div></div>")
    st.markdown("<div style='display:flex;flex-wrap:wrap'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


# ---------- All Spots ----------

def all_spots_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:1.4rem;font-weight:800'>📋 All Spots</div>", unsafe_allow_html=True)
    st.caption("Every logged place — consensus score and each member's rank where they've weighed in.")
    idx = consensus_index(df)
    show = df.copy()
    show["Overall"] = show["Restaurant"].map(lambda n: idx[n]["overall_rank"] if n in idx else pd.NA)
    show["Score"] = show["Restaurant"].map(lambda n: round(idx[n]["median"] / 10, 1) if n in idx else pd.NA)
    show["Visit Date"] = pd.to_datetime(show["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")
    cols = ["Overall", "Country", "Restaurant", "Status", "Score", *ds.RATERS, "Visit Date", "Dishes", "Notes", "Maps_URL"]
    st.dataframe(show[cols].sort_values(["Status", "Overall"], na_position="last"), hide_index=True, width="stretch",
                 column_config={"Score": st.column_config.NumberColumn("Score", format="%.1f ⭐"),
                                "Overall": st.column_config.NumberColumn("Overall", format="#%d")})
    st.download_button("⬇ Download CSV", data=df.to_csv(index=False),
                       file_name="africax_restaurants.csv", mime="text/csv")


# ---------- Wishlist ----------

def wishlist_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:1.4rem;font-weight:800'>🔖 Wishlist</div>", unsafe_allow_html=True)
    wish = ds.wishlist(df)
    if wish.empty:
        st.info("Nothing on the wishlist yet. Use **Add Spot** to bookmark a place to try.")
        return
    st.caption(f"{len(wish)} spots to try across {wish['ISO_A3'].nunique()} countries.")
    cards = []
    for _, r in wish.sort_values("Country").iterrows():
        meta = str(r.get("Notes", "")).strip()
        maps = f" · <a href='{r['Maps_URL']}' target='_blank'>Maps</a>" if str(r.get("Maps_URL", "")).strip() else ""
        cards.append(
            f"<div class='ax-card' style='display:flex;gap:12px'>{code_chip(r['ISO_A3'],'wishlist')}"
            f"<div style='flex:1;min-width:0'><div style='font-weight:700'>{r['Country']}</div>"
            f"<div style='font-size:.88rem;color:#2E5A44;font-weight:600;margin-top:2px'>{r['Restaurant']}</div>"
            f"<div style='font-size:.8rem;color:#8A8F98;margin-top:2px'>{meta}{maps}</div></div></div>")
    # two-column grid
    cols = st.columns(2)
    for n, card in enumerate(cards):
        cols[n % 2].markdown(card, unsafe_allow_html=True)
        cols[n % 2].write("")


# ---------- Add Spot ----------

def add_spot_page(africa, df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:1.4rem;font-weight:800'>＋ Add a Spot</div>", unsafe_allow_html=True)
    st.caption("Log a place. No scores here — ranking happens on **My Rankings**.")
    names = sorted(africa["name"].tolist())
    iso_by_name = dict(zip(africa["name"], africa["iso_a3"]))
    cur = st.session_state.get("selected_country")
    idx = names.index(cur["name"]) if cur and cur["name"] in names else 0
    country = st.selectbox("Country", names, index=idx)
    _add_form(country, iso_by_name[country])
