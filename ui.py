"""AfricaX UI — the "restaurant passport" dashboard (AfricaX Dashboard.dc.html).

A single warm-cream page: header, KPI strip, a hero row (map + the dark-green
group-leaderboard "centrepiece"), a full-width selected-country band, supporting
tiles (a member's order · wishlist · quick-add), and a progress ring + activity.
The reorder ballot and the full leaderboard open as their own views.

Model: consensus RANKING (median of everyone's normalised order), shown as a
0–100 median with a bar — never star ratings. Real data only; empty fields stay
empty until the group fills them in. Every write goes through ``data_store``.
"""

from __future__ import annotations

import base64
import math
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

import data_store as ds
import rankings as rk
from mapview import build_map, country_at_click, legend_html, load_geo

AVATAR_COLORS = {
    "Fayez": "#2E7D5B", "Muhammad": "#2F6FC7", "Seth": "#7B54C0",
    "Ian": "#D2691E", "Shubham": "#E0A500",
}

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


# ---------- atoms ----------

def code(iso3: str) -> str:
    return _A3_A2.get(str(iso3).upper(), str(iso3)[:2].upper())


_FLAG_DIR = Path(__file__).parent / "data" / "flags"
_FLAG_CACHE: dict = {}


def flag(iso3: str, height: int = 15) -> str:
    """Country flag as an inline (bundled) image — the SVGs live in ``data/flags/``
    and are base64-embedded, so they render everywhere with no external CDN request
    (and no reliance on flag *emoji*, which Windows can't show)."""
    a2 = _A3_A2.get(str(iso3).upper())
    if not a2:
        return ""
    if a2 not in _FLAG_CACHE:
        p = _FLAG_DIR / f"{a2.lower()}.svg"
        _FLAG_CACHE[a2] = ("data:image/svg+xml;base64," + base64.b64encode(p.read_bytes()).decode()
                           if p.exists() else f"https://flagcdn.com/{a2.lower()}.svg")
    return (f"<img src='{_FLAG_CACHE[a2]}' alt='{a2}' style='height:{height}px;width:auto;border-radius:2px;"
            f"vertical-align:-2px;box-shadow:0 0 0 1px rgba(0,0,0,.12)'>")


def avatar(name: str, size: int = 30, ring: str = "#FBF8F1") -> str:
    c = AVATAR_COLORS.get(name, "#777")
    return (f"<span title='{name}' style='display:inline-flex;align-items:center;justify-content:center;"
            f"width:{size}px;height:{size}px;border-radius:50%;background:{c};color:#fff;font-weight:800;"
            f"font-size:{max(11, size // 2 - 2)}px;border:2.5px solid {ring};margin-left:-9px'>{name[0]}</span>")


def avatars(names, size: int = 30, ring: str = "#FBF8F1") -> str:
    return "<span style='display:inline-flex;padding-left:9px'>" + "".join(avatar(n, size, ring) for n in names) + "</span>"


def code_chip(iso3: str, kind: str = "visited") -> str:
    bg, ink, bd = {"visited": ("#E3EFE8", "#12513A", "#CBE1D3"),
                   "wishlist": ("#F3EAFB", "#5E3B87", "#E2D0F3"),
                   "none": ("#F1ECE0", "#6B6558", "#E4DDCD")}[kind]
    return (f"<span style='display:inline-flex;align-items:center;justify-content:center;width:42px;height:30px;"
            f"border-radius:7px;background:{bg};color:{ink};font-size:14px;font-weight:800;letter-spacing:.05em;"
            f"border:1px solid {bd}'>{code(iso3)}</span>")


def chip(text: str) -> str:
    return (f"<span style='background:#EEF3EF;border:1px solid #DCE7DF;border-radius:999px;padding:5px 12px;"
            f"font-size:12.5px;font-weight:600;color:#2E5A44;margin:0 6px 6px 0;display:inline-block'>{text}</span>")


# ---------- consensus ----------

def consensus_index(df: pd.DataFrame) -> dict:
    rows = rk.consensus(rk.rankings_from_df(df), min_coverage=1)
    return {r["restaurant"]: r for r in rows}


def score100(median) -> str:
    if median is None:
        return "—"
    m = float(median)
    return str(int(m)) if m == int(m) else f"{m:.1f}"


def _consensus_rows(df: pd.DataFrame) -> list:
    """Sorted consensus rows enriched with country + iso, top-ranked first."""
    idx = consensus_index(df)
    country_by = dict(zip(df["Restaurant"], df["Country"]))
    iso_by = dict(zip(df["Restaurant"], df["ISO_A3"]))
    out = []
    for r in sorted(idx.values(), key=lambda r: r["overall_rank"]):
        out.append({**r, "country": country_by.get(r["restaurant"], ""),
                    "iso": iso_by.get(r["restaurant"], "")})
    return out


def _ranked_members(df: pd.DataFrame) -> list:
    return [m for m in ds.RATERS if pd.to_numeric(df[m], errors="coerce").notna().any()]


# ---------- styling ----------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1400px; }
        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
        html, body, [class*="css"] { font-family: 'Source Sans 3','Source Sans Pro',system-ui,sans-serif; }
        .stApp { background: #FBF8F1; }

        .ax-card { background:#fff; border:1px solid #ECE4D4; border-radius:16px; padding:20px 22px;
                   box-shadow:0 1px 2px rgba(60,50,30,.04); display:flex; flex-direction:column; height:100%; }
        .ax-lab { font-size:11px; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:#9A968C; }
        .ax-num { font-size:34px; font-weight:900; line-height:1; }
        .ax-bar { height:6px; background:#EFE9DB; border-radius:99px; overflow:hidden; }
        .ax-bar > div { height:100%; background:#2E7D5B; border-radius:99px; }

        /* buttons */
        .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
            border-radius:11px; font-weight:700; border:1px solid #E4DDCD; }
        .stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"] {
            background:#2E7D5B; border-color:#2E7D5B; box-shadow:0 6px 16px rgba(46,125,91,.22); }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; border-color:#ECE4D4; background:#fff; }
        /* equalise card heights within a row so sections align */
        div[data-testid="stHorizontalBlock"] { align-items: stretch; }
        div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] { height:100%; }
        div[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] { height:100%; }
        div[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] { height:100%; }
        /* make dropdowns + inputs clearly read as fields on the cream page */
        div[data-baseweb="select"] > div { background:#fff !important; border:1.5px solid #CBBFA1 !important;
            border-radius:10px !important; box-shadow:0 1px 2px rgba(60,50,30,.05); }
        div[data-baseweb="select"] svg { color:#6B6558; }
        .stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input {
            background:#fff !important; border:1.5px solid #D8CFBB !important; border-radius:10px !important; }
        .stTextInput label, .stSelectbox label, .stTextArea label, .stRadio label, .stDateInput label { font-weight:600; }
        h2,h3 { color:#1F2328; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _set_view(v: str) -> None:
    st.session_state["view"] = v


def _select_country(name: str, iso: str) -> None:
    st.session_state["selected_country"] = {"name": name, "iso_a3": iso}


# ---------- header ----------

def header_bar(df: pd.DataFrame) -> None:
    left, right = st.columns([0.52, 0.48])
    with left:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:14px'>"
            "<div style='width:46px;height:46px;border-radius:13px;background:#2E7D5B;display:flex;"
            "align-items:center;justify-content:center;font-size:23px;box-shadow:0 6px 16px rgba(46,125,91,.28)'>🍴</div>"
            "<div><div style='display:flex;align-items:center;gap:10px'>"
            "<span style='font-size:26px;font-weight:900;letter-spacing:.06em'>AFRICAX</span>"
            "<span style='font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#2E7D5B;"
            "background:#E3EFE8;border:1px solid #CBE1D3;padding:3px 8px;border-radius:999px'>Passport</span></div>"
            "<div style='margin-top:2px;font-size:14px;color:#7C7666;font-weight:500'>"
            "African Restaurant Passport · a five-friend consensus</div></div></div>",
            unsafe_allow_html=True)
    with right:
        crew, b1, b2 = st.columns([1.5, 1.15, 0.9])
        crew.markdown(
            f"<div style='display:flex;align-items:center;justify-content:flex-end;gap:10px;height:46px'>"
            f"<span class='ax-lab'>Crew</span>{avatars(ds.RATERS, 34)}</div>", unsafe_allow_html=True)
        b1.button("📊 Rank your spots", type="primary", use_container_width=True,
                  on_click=_set_view, args=("rank",), key="hdr_rank")
        b2.button("＋ Add spot", use_container_width=True, on_click=_set_view, args=("add",), key="hdr_add")


# ---------- KPI strip ----------

def kpi_strip(df: pd.DataFrame, africa) -> None:
    total = len(africa)
    vis, wish = ds.visited(df), ds.wishlist(df)
    vc = vis["ISO_A3"].nunique()
    rows = _consensus_rows(df)
    top = rows[0] if rows else None
    frac = round(100 * vc / total, 1) if total else 0
    codes = "".join(f"<span style='font-size:10px;font-weight:800;color:#2E5A44;background:#E9F1EC;"
                    f"border:1px solid #D3E5DA;border-radius:5px;padding:2px 5px;margin-right:5px'>{code(i)}</span>"
                    for i in vis["ISO_A3"].unique())
    ts = score100(top["median"]) if top else "—"
    tn = f"{top['restaurant']} · {top['country']}" if top else "No rankings yet"
    c1 = (f"<div class='ax-card'><span class='ax-lab'>Countries</span>"
          f"<div style='display:flex;align-items:baseline;gap:6px;margin-top:12px'><span class='ax-num'>{vc}</span>"
          f"<span style='font-size:15px;font-weight:600;color:#B4AE9E'>of {total}</span></div>"
          f"<div class='ax-bar' style='margin-top:auto;margin-top:14px'><div style='width:{frac}%'></div></div></div>")
    c2 = (f"<div class='ax-card'><span class='ax-lab'>Places visited</span>"
          f"<div class='ax-num' style='margin-top:12px'>{len(vis)}</div>"
          f"<div style='margin-top:auto;padding-top:11px'>{codes}</div></div>")
    c3 = (f"<div class='ax-card'><span class='ax-lab'>On wishlist</span>"
          f"<div style='display:flex;align-items:baseline;gap:6px;margin-top:12px'><span class='ax-num'>{len(wish)}</span>"
          f"<span style='font-size:14px;font-weight:600;color:#B4AE9E'>DMV spots</span></div>"
          f"<div style='margin-top:auto;padding-top:11px;font-size:12.5px;color:#8A8577'>Across {wish['ISO_A3'].nunique()} countries · VA · DC · MD</div></div>")
    c4 = (f"<div class='ax-card' style='background:linear-gradient(150deg,#FBF3DF,#F6ECCF);border-color:#EBD9A9'>"
          f"<span class='ax-lab' style='color:#9C7C33'>Top consensus</span>"
          f"<div style='display:flex;align-items:baseline;gap:5px;margin-top:12px'>"
          f"<span class='ax-num' style='color:#8A6A1E'>{ts}</span>"
          f"<span style='font-size:14px;font-weight:700;color:#B79A54'>/100</span></div>"
          f"<div style='margin-top:auto;padding-top:11px;font-size:13px;font-weight:700;color:#7A5E1B'>{tn}</div></div>")
    st.markdown("<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:16px;align-items:stretch'>"
                + c1 + c2 + c3 + c4 + "</div>", unsafe_allow_html=True)


# ---------- rank nudge ----------

def rank_nudge(df: pd.DataFrame) -> None:
    ranked = _ranked_members(df)
    unranked = [m for m in ds.RATERS if m not in ranked]
    if not unranked:
        return
    who = ", ".join(unranked)
    verb = "need" if len(unranked) != 1 else "needs"
    t, b = st.columns([0.8, 0.2])
    t.markdown(
        f"<div class='ax-card' style='border-left:4px solid #C0902F'>"
        f"<div style='font-size:15px;font-weight:700'>Settle the board — {len(ranked)} of {len(ds.RATERS)} have ranked.</div>"
        f"<div style='font-size:13.5px;color:#7C7666;margin-top:2px'>{who} still {verb} to rank the "
        f"{len(ds.visited(df))} spots you've all been to. Consensus is the median of everyone's order.</div></div>",
        unsafe_allow_html=True)
    b.write("")
    b.button("Rank your spots →", type="primary", use_container_width=True,
             on_click=_set_view, args=("rank",), key="nudge")


# ---------- hero: map + dark leaderboard ----------

def hero(africa, df: pd.DataFrame) -> None:
    left, right = st.columns([0.6, 0.4], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("<span class='ax-lab'>The map</span>"
                        "<div style='font-size:19px;font-weight:800;margin-top:2px'>Explore Africa, country by country</div>"
                        + legend_html(), unsafe_allow_html=True)
            m = build_map(africa, ds.status_by_iso(df), ds.country_stats(df))
            from streamlit_folium import st_folium
            st_folium(m, width=None, height=400, key="dash_map")
    with right:
        _leaderboard_card(df)


def _leaderboard_card(df: pd.DataFrame) -> None:
    rows = _consensus_rows(df)
    ranked = len(_ranked_members(df))
    medal = ["#E6BE6A", "#CFCFC7", "#D8B48C"]
    medal_ink = ["#4A360E", "#3B3B36", "#4A2F14"]
    body = ""
    if not rows:
        body = ("<div style='padding:24px 4px;color:#9DB3A7;font-size:14px'>No rankings yet — "
                "be the first to rank and start the board.</div>")
    else:
        for i, r in enumerate(rows[:3]):
            rowbg = "rgba(230,190,106,.12)" if i == 0 else "rgba(255,255,255,.05)"
            rowbd = "rgba(230,190,106,.35)" if i == 0 else "rgba(255,255,255,.08)"
            mb = medal[i] if i < 3 else "rgba(255,255,255,.15)"
            mi = medal_ink[i] if i < 3 else "#fff"
            body += (
                f"<div style='background:{rowbg};border:1px solid {rowbd};border-radius:13px;padding:13px 15px;margin-bottom:11px'>"
                f"<div style='display:flex;align-items:center;gap:12px'>"
                f"<div style='width:30px;height:30px;border-radius:9px;background:{mb};color:{mi};font-size:15px;"
                f"font-weight:900;display:flex;align-items:center;justify-content:center;flex:0 0 auto'>{r['overall_rank']}</div>"
                f"<div style='flex:1;min-width:0'><div style='font-size:14.5px;font-weight:800;color:#fff;white-space:nowrap;"
                f"overflow:hidden;text-overflow:ellipsis'>{r['restaurant']}</div>"
                f"<div style='font-size:12px;color:#9DB3A7;margin-top:1px'>{flag(r['iso'],11)} {r['country']}</div></div>"
                f"<div style='text-align:right;flex:0 0 auto'><div style='font-size:17px;font-weight:900;color:#E6BE6A'>{score100(r['median'])}</div>"
                f"<div style='font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#82998B'>median</div></div></div>"
                f"<div style='margin-top:10px;height:6px;background:rgba(255,255,255,.1);border-radius:99px;overflow:hidden'>"
                f"<div style='width:{r['median']}%;height:100%;background:#E6BE6A;border-radius:99px'></div></div></div>")
    st.markdown(
        "<div style='background:#26332B;border-radius:18px;padding:22px 22px 18px;box-shadow:0 12px 30px "
        "rgba(30,44,32,.24);min-height:452px;display:flex;flex-direction:column'>"
        "<div style='display:flex;align-items:center;justify-content:space-between'>"
        "<div><div class='ax-lab' style='color:#8FB6A2'>The centrepiece</div>"
        "<div style='font-size:20px;font-weight:800;color:#fff;margin-top:2px'>Group leaderboard</div></div>"
        "<div style='width:38px;height:38px;border-radius:11px;background:rgba(192,144,47,.18);display:flex;"
        "align-items:center;justify-content:center;font-size:19px'>🏆</div></div>"
        f"<div style='font-size:12.5px;color:#9DB3A7;margin-top:6px'>Median of everyone's normalised order · {ranked} of 5 ranked</div>"
        f"<div style='margin-top:16px;flex:1'>{body}</div></div>", unsafe_allow_html=True)
    st.button("View full leaderboard →", use_container_width=True, on_click=_set_view, args=("leaderboard",), key="lb_full")


# ---------- selected-country band ----------

def selected_band(africa, df: pd.DataFrame) -> None:
    sel = st.session_state.get("selected_country")
    with st.container(border=True):
        h = st.columns([0.7, 0.3])
        h[0].markdown("<span class='ax-lab'>Selected country</span>", unsafe_allow_html=True)
        if sel:
            h[1].button("Clear ✕", key="clear_sel", on_click=lambda: st.session_state.pop("selected_country", None))
        if not sel:
            _band_default(africa, df)
            return
        name, iso = sel["name"], sel["iso_a3"]
        rows = df[df["ISO_A3"] == iso]
        vis, wish = rows[rows["Status"] == ds.STATUS_VISITED], rows[rows["Status"] == ds.STATUS_WISHLIST]
        if not vis.empty:
            _band_visited(df, name, iso, vis)
        elif not wish.empty:
            _band_wishlist(name, iso, wish.iloc[0])
        else:
            st.caption("No spots logged in this country yet.")


def _band_default(africa, df: pd.DataFrame) -> None:
    names = sorted(africa["name"].tolist())
    iso_by = dict(zip(africa["name"], africa["iso_a3"]))
    pick = st.selectbox("Open a country", ["Pick a country…"] + names, label_visibility="collapsed", key="band_pick")
    if pick != "Pick a country…":
        _select_country(pick, iso_by[pick])
        st.rerun()
    st.markdown("<div style='font-size:13px;color:#7C7666;margin-top:2px'>…or tap the map. Every stamped country shows its "
                "restaurant, dishes, notes, and the group's consensus.</div>", unsafe_allow_html=True)
    vis, wish = ds.visited(df), ds.wishlist(df)
    vchips = "".join(f"<span style='background:#E9F1EC;border:1px solid #D3E5DA;border-radius:9px;padding:6px 10px;"
                     f"font-size:12.5px;font-weight:600;color:#2E5A44;margin:0 6px 6px 0;display:inline-block'>"
                     f"{flag(r['ISO_A3'],11)} {r['Country']}</span>" for _, r in vis.iterrows())
    wchips = "".join(f"<span style='background:#F3EAFB;border:1px solid #E2D0F3;border-radius:9px;padding:6px 10px;"
                     f"font-size:12.5px;font-weight:600;color:#5E3B87;margin:0 6px 6px 0;display:inline-block'>"
                     f"{flag(r['ISO_A3'],11)} {r['Country']}</span>" for _, r in wish.iterrows())
    st.markdown(f"<div class='ax-lab' style='margin-top:12px'>Visited</div><div style='margin-top:8px'>{vchips}</div>"
                f"<div class='ax-lab' style='margin-top:12px'>Wishlist</div><div style='margin-top:8px'>{wchips}</div>",
                unsafe_allow_html=True)


def _band_visited(df, name, iso, vis) -> None:
    idx = consensus_index(df)
    scored = [(r, idx.get(r["Restaurant"])) for _, r in vis.iterrows()]
    ranked = [t for t in scored if t[1]]
    row, cons = min(ranked, key=lambda t: t[1]["overall_rank"]) if ranked else (vis.iloc[0], None)
    dishes = [d.strip() for d in str(row.get("Dishes", "")).split(",") if d.strip()]
    notes = str(row.get("Notes", "")).strip()
    left, right = st.columns([0.62, 0.38], gap="large")
    with left:
        st.markdown(f"<div style='display:flex;align-items:center;gap:12px;margin-top:8px'>{code_chip(iso,'visited')}"
                    f"<span style='font-size:24px;font-weight:800'>{flag(iso,22)} {name}</span>"
                    f"<span style='padding:4px 11px;border-radius:999px;font-size:10.5px;font-weight:800;letter-spacing:.05em;"
                    f"text-transform:uppercase;background:#DDEFE4;color:#12513A'>Visited</span></div>",
                    unsafe_allow_html=True)
        parts = [f"<div style='font-size:16.5px;font-weight:800'>{row['Restaurant']}</div>"]
        if dishes:
            parts.append("<div style='margin-top:12px'>" + "".join(chip(d) for d in dishes) + "</div>")
        if notes:
            parts.append(f"<div style='margin-top:12px;font-size:13.5px;font-style:italic;color:#6B6558'>“{notes}”</div>")
        if not dishes and not notes:
            parts.append("<div style='margin-top:10px;font-size:13px;color:#B4AE9E'>No dishes or notes yet — "
                         "add them from Add spot → Edit.</div>")
        st.markdown("<div style='margin-top:16px;padding:16px 18px;background:#FBFAF6;border:1px solid #EDE6D6;"
                    "border-radius:14px'>" + "".join(parts) + "</div>", unsafe_allow_html=True)
    with right:
        if cons:
            av = avatars(sorted(cons["ranked_by"], key=ds.RATERS.index), 28, "#F3F7F4")
            st.markdown(
                f"<div style='background:#F3F7F4;border:1px solid #DDEAE1;border-radius:14px;padding:18px 20px'>"
                f"<div class='ax-lab' style='color:#7C9A88'>Group consensus</div>"
                f"<div style='display:flex;align-items:baseline;gap:6px;margin-top:8px'>"
                f"<span style='font-size:40px;font-weight:900;color:#2E7D5B;line-height:1'>{score100(cons['median'])}</span>"
                f"<span style='font-size:15px;font-weight:700;color:#9DB3A7'>/100</span></div>"
                f"<div class='ax-bar' style='margin-top:12px;height:8px'><div style='width:{cons['median']}%'></div></div>"
                f"<div style='margin-top:8px;font-size:13px;font-weight:600;color:#6B7280'>Overall #{cons['overall_rank']} of {len(idx)} · median</div>"
                f"<div class='ax-lab' style='color:#7C9A88;margin-top:16px'>Ranked by</div>"
                f"<div style='margin-top:9px'>{av} <span style='margin-left:10px;font-size:12.5px;color:#6B7280;"
                f"font-weight:600'>{cons['coverage']} of 5</span></div></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='background:#F3F7F4;border:1px solid #DDEAE1;border-radius:14px;padding:18px 20px'>"
                        "<div class='ax-lab' style='color:#7C9A88'>Group consensus</div>"
                        "<div style='margin-top:10px;font-size:14px;color:#6B6558'>No one has ranked this yet. "
                        "It joins the board as soon as a member ranks it.</div></div>", unsafe_allow_html=True)
        st.button("Rank your spots →", use_container_width=True, on_click=_set_view, args=("rank",), key="band_rank")


def _band_wishlist(name, iso, r) -> None:
    city = str(r.get("Notes", "")).split("—")[0].strip()
    maps = str(r.get("Maps_URL", "")).strip()
    left, right = st.columns([0.62, 0.38], gap="large")
    with left:
        st.markdown(f"<div style='display:flex;align-items:center;gap:12px;margin-top:8px'>{code_chip(iso,'wishlist')}"
                    f"<span style='font-size:24px;font-weight:800'>{flag(iso,22)} {name}</span>"
                    f"<span style='padding:4px 11px;border-radius:999px;font-size:10.5px;font-weight:800;letter-spacing:.05em;"
                    f"text-transform:uppercase;background:#EADDF7;color:#5E3B87'>Want to go</span></div>",
                    unsafe_allow_html=True)
        link = (f"<div style='margin-top:14px'><a href='{maps}' target='_blank' style='display:inline-flex;align-items:center;"
                f"gap:7px;background:#fff;border:1px solid #E2D0F3;color:#5E3B87;font-size:13px;font-weight:700;"
                f"padding:8px 14px;border-radius:10px;text-decoration:none'>📍 Open in Maps</a></div>") if maps else ""
        st.markdown(f"<div style='margin-top:16px;padding:16px 18px;background:#FBF9FE;border:1px dashed #DFCEF2;"
                    f"border-radius:14px'><div style='font-size:16.5px;font-weight:800'>{r['Restaurant']}</div>"
                    f"<div style='margin-top:6px;font-size:12.5px;color:#8A8577'>📍 {city or 'Location TBC'}</div>"
                    f"{link}</div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div style='background:#FBF9FE;border:1px solid #EADDF7;border-radius:14px;padding:18px 20px'>"
                    "<div class='ax-lab' style='color:#9878B4'>Not ranked yet</div>"
                    f"<div style='margin-top:10px;font-size:14px;color:#6B6558;line-height:1.55'>Been to {name}? "
                    f"Mark it visited (Add spot), then it joins the ballot and the consensus board.</div></div>",
                    unsafe_allow_html=True)


# ---------- supporting tiles ----------

def supporting_tiles(africa, df: pd.DataFrame) -> None:
    c = st.columns(3, gap="medium")
    with c[0]:
        with st.container(border=True):
            _tile_my_order(df)
    with c[1]:
        with st.container(border=True):
            _tile_wishlist(df)
    with c[2]:
        with st.container(border=True):
            _tile_quick_add(africa, df)


def _tile_my_order(df: pd.DataFrame) -> None:
    top = st.columns([0.55, 0.45])
    top[0].markdown("<div style='font-size:16px;font-weight:800;padding-top:6px'>A member's order</div>", unsafe_allow_html=True)
    with top[1]:
        member = st.selectbox("member", ds.RATERS, key="dash_member", label_visibility="collapsed")
    sub = df[pd.to_numeric(df[member], errors="coerce").notna()].copy()
    if sub.empty:
        st.markdown(f"<div style='margin-top:12px;padding:18px;background:#FBFAF6;border:1px dashed #E4DDCD;"
                    f"border-radius:12px;text-align:center'><div style='font-size:13.5px;font-weight:700;color:#7C7666'>"
                    f"{member} hasn't ranked yet.</div></div>", unsafe_allow_html=True)
        st.button(f"Rank as {member} →", key="tile_rank", on_click=_set_view, args=("rank",))
        return
    sub["_r"] = pd.to_numeric(sub[member], errors="coerce")
    html = ""
    for _, r in sub.sort_values("_r").iterrows():
        first = int(r["_r"]) == 1
        html += (f"<div style='display:flex;align-items:center;gap:11px;padding:6px 0'>"
                 f"<div style='width:24px;height:24px;border-radius:7px;background:{'#E3EFE8' if first else '#F1ECE0'};"
                 f"color:{'#2E7D5B' if first else '#7C7666'};font-size:12.5px;font-weight:800;display:flex;"
                 f"align-items:center;justify-content:center'>{int(r['_r'])}</div>"
                 f"<div style='flex:1;min-width:0;font-size:13.5px;font-weight:700'>{r['Restaurant']}</div>"
                 f"<span style='font-size:11px;font-weight:700;color:#9A968C'>{flag(r['ISO_A3'],10)} {r['Country']}</span></div>")
    st.markdown(f"<div style='margin-top:12px'>{html}</div>", unsafe_allow_html=True)


def _tile_wishlist(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:16px;font-weight:800'>Wishlist &amp; next up</div>", unsafe_allow_html=True)
    wish = ds.wishlist(df).head(5)
    html = ""
    for _, r in wish.iterrows():
        city = str(r.get("Notes", "")).split("—")[0].strip()
        meta = f"{r['Country']} · {city}" if city else r["Country"]
        html += (f"<div style='display:flex;align-items:center;gap:11px;padding:9px 0;border-bottom:1px solid #F1ECE0'>"
                 f"<span style='width:30px;height:22px;border-radius:5px;background:#F3EAFB;color:#5E3B87;font-size:10px;"
                 f"font-weight:800;display:flex;align-items:center;justify-content:center;flex:0 0 auto'>{code(r['ISO_A3'])}</span>"
                 f"<div style='flex:1;min-width:0'><div style='font-size:13.5px;font-weight:700;white-space:nowrap;"
                 f"overflow:hidden;text-overflow:ellipsis'>{flag(r['ISO_A3'],11)} {r['Restaurant']}</div>"
                 f"<div style='font-size:11.5px;color:#9A968C'>{meta}</div></div></div>")
    st.markdown(f"<div style='margin-top:12px'>{html}</div>", unsafe_allow_html=True)
    st.button("View full wishlist →", key="tile_wish", on_click=_set_view, args=("wishlist",))


def _tile_quick_add(africa, df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:16px;font-weight:800'>Add a spot</div>"
                "<div style='font-size:13px;color:#7C7666;margin-top:2px'>Been somewhere new, or found a place to try?</div>",
                unsafe_allow_html=True)
    names = sorted(africa["name"].tolist())
    iso_by = dict(zip(africa["name"], africa["iso_a3"]))
    with st.expander("＋ Add visited or wishlist spot"):
        with st.form("quick_add", clear_on_submit=True):
            country = st.selectbox("Country", names, index=None, placeholder="Select a country…")
            restaurant = st.text_input("Restaurant", placeholder="e.g. Buka")
            dishes = st.text_input("Dishes (optional)", placeholder="jollof, suya")
            kind = st.radio("Type", ["Visited", "Wishlist"], horizontal=True)
            if st.form_submit_button("Save to passport", type="primary", use_container_width=True):
                if not country or not restaurant.strip():
                    st.error("Country and restaurant are required.")
                else:
                    row = {"Country": country, "ISO_A3": iso_by[country], "Restaurant": restaurant.strip(),
                           "Dishes": dishes.strip(), "Status": ds.STATUS_VISITED if kind == "Visited" else ds.STATUS_WISHLIST}
                    if kind == "Visited":
                        row["Visit Date"] = pd.Timestamp.today().normalize()
                    ds.append_row(row)
                    st.success(f"Added {restaurant.strip()}!")
                    st.cache_data.clear()
                    st.rerun()
        st.caption("No rating — ranking happens on the ballot.")


# ---------- progress + activity ----------

def progress_and_activity(df: pd.DataFrame, africa) -> None:
    total = len(africa)
    vc = ds.visited(df)["ISO_A3"].nunique()
    pct = round(100 * vc / total) if total else 0
    C = 2 * math.pi * 50
    dash = f"{C * vc / total:.1f} {C:.1f}" if total else f"0 {C:.1f}"
    a, b = st.columns([0.42, 0.58], gap="medium")
    with a:
        with st.container(border=True):
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:22px'>"
                f"<div style='position:relative;width:112px;height:112px;flex:0 0 auto'>"
                f"<svg width='112' height='112' viewBox='0 0 120 120'>"
                f"<circle cx='60' cy='60' r='50' fill='none' stroke='#EFE9DB' stroke-width='12'></circle>"
                f"<circle cx='60' cy='60' r='50' fill='none' stroke='#2E7D5B' stroke-width='12' stroke-linecap='round' "
                f"stroke-dasharray='{dash}' transform='rotate(-90 60 60)'></circle></svg>"
                f"<div style='position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center'>"
                f"<div style='font-size:26px;font-weight:900;line-height:1'>{vc}</div>"
                f"<div style='font-size:11px;font-weight:700;color:#9A968C'>of {total}</div></div></div>"
                f"<div><span class='ax-lab'>Passport progress</span>"
                f"<div style='font-size:19px;font-weight:800;margin-top:4px'>{pct}% of Africa stamped</div>"
                f"<div style='font-size:13.5px;color:#7C7666;margin-top:5px;line-height:1.5'>{total - vc} countries still "
                f"to taste. {ds.wishlist(df)['ISO_A3'].nunique()} are scouted on the wishlist.</div></div></div>",
                unsafe_allow_html=True)
    with b:
        with st.container(border=True):
            _next_up(df)


def _next_up(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:16px;font-weight:800'>Next up near DC</div>"
                "<div style='font-size:13px;color:#7C7666;margin-top:2px'>Wishlist spots, closest first</div>",
                unsafe_allow_html=True)
    order = {"VA": 0, "DC": 1, "MD": 2, "PA": 3, "NJ": 4, "NY": 5, "NC": 6}

    def _key(notes):
        head = str(notes).split("—")[0]
        for st_, o in order.items():
            if f", {st_}" in head:
                return o
        return 9

    wish = sorted((r for _, r in ds.wishlist(df).iterrows()), key=lambda r: _key(r.get("Notes", "")))
    html = ""
    for r in wish[:6]:
        city = str(r.get("Notes", "")).split("—")[0].strip()
        html += (f"<div style='display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #F1ECE0'>"
                 f"<span style='width:30px;height:22px;border-radius:5px;background:#F3EAFB;color:#5E3B87;font-size:10px;"
                 f"font-weight:800;display:flex;align-items:center;justify-content:center;flex:0 0 auto'>{code(r['ISO_A3'])}</span>"
                 f"<div style='flex:1;min-width:0'><div style='font-size:13.5px;font-weight:700'>{r['Restaurant']}</div>"
                 f"<div style='font-size:11.5px;color:#9A968C'>{flag(r['ISO_A3'], 10)} {r['Country']}</div></div>"
                 f"<span style='font-size:12px;color:#7C7666;white-space:nowrap'>{city}</span></div>")
    st.markdown(f"<div style='margin-top:12px'>{html or '<div style=color:#9A968C>Nothing on the wishlist yet.</div>'}</div>",
                unsafe_allow_html=True)
    st.button("See all wishlist →", key="nextup_all", on_click=_set_view, args=("wishlist",))


# ---------- the dashboard ----------

def dashboard(africa, df: pd.DataFrame) -> None:
    header_bar(df)
    st.write("")
    kpi_strip(df, africa)
    rank_nudge(df)
    st.write("")
    hero(africa, df)
    st.write("")
    supporting_tiles(africa, df)
    st.write("")
    progress_and_activity(df, africa)


# ---------- ballot view ----------

def _move(key: str, i: int, delta: int) -> None:
    order = st.session_state[key]
    j = i + delta
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]


def rank_view(df: pd.DataFrame) -> None:
    st.button("← Back to dashboard", on_click=_set_view, args=("dashboard",), key="bk_rank")
    st.markdown("<div style='font-size:28px;font-weight:900;margin-top:8px'>Rank your spots</div>"
                "<div style='font-size:14.5px;color:#7C7666;margin-top:6px;max-width:640px;line-height:1.55'>"
                "Order your five visited spots — <b style='color:#1F2328'>top is your favourite</b>. Your order becomes "
                "a 0–100 percentile and feeds the group's median. Save to update the board.</div>",
                unsafe_allow_html=True)
    vis = ds.visited(df).sort_values("Restaurant")
    names = vis["Restaurant"].tolist()
    if not names:
        st.info("No visited spots to rank yet. Add some first.")
        return

    member = st.selectbox("Who are you?", ds.RATERS, key="rank_member")
    st.markdown(f"{avatar(member,32,'#FBF8F1')} &nbsp; Ranking as **{member}**", unsafe_allow_html=True)
    key = f"order_{member}"
    if key not in st.session_state:
        saved = df[pd.to_numeric(df[member], errors="coerce").notna()].sort_values(member)["Restaurant"].tolist()
        st.session_state[key] = saved + [n for n in names if n not in saved]
    order = [n for n in st.session_state[key] if n in names] + [n for n in names if n not in st.session_state[key]]
    st.session_state[key] = order

    if not pd.to_numeric(df[member], errors="coerce").notna().any():
        st.markdown(f"<div style='margin-top:12px;background:#FBF3DF;border:1px solid #EBD9A9;border-radius:12px;"
                    f"padding:13px 16px;font-size:13.5px;color:#7A5E1B'><b>{member} hasn't ranked yet.</b> "
                    f"Order the spots and save to join the board.</div>", unsafe_allow_html=True)

    left, right = st.columns([0.6, 0.4], gap="large")
    with left:
        cty = dict(zip(vis["Restaurant"], vis["Country"]))
        iso = dict(zip(vis["Restaurant"], vis["ISO_A3"]))
        for i, nm in enumerate(order):
            with st.container(border=True):
                cc = st.columns([0.55, 5, 0.7, 0.7])
                cc[0].markdown(f"<div style='width:32px;height:32px;border-radius:9px;background:"
                               f"{'#E3EFE8' if i == 0 else '#F1ECE0'};color:{'#2E7D5B' if i == 0 else '#7C7666'};"
                               f"font-size:16px;font-weight:900;display:flex;align-items:center;justify-content:center'>{i+1}</div>",
                               unsafe_allow_html=True)
                cc[1].markdown(f"**{nm}**  \n<span style='color:#9A968C;font-size:.8rem'>{flag(iso.get(nm,''),11)} {cty.get(nm,'')}</span>",
                               unsafe_allow_html=True)
                cc[2].button("▲", key=f"up_{member}_{i}", disabled=(i == 0), on_click=_move, args=(key, i, -1), use_container_width=True)
                cc[3].button("▼", key=f"dn_{member}_{i}", disabled=(i == len(order) - 1), on_click=_move, args=(key, i, 1), use_container_width=True)
        s, c = st.columns([1, 1])
        if s.button("💾 Save my ranking", type="primary", use_container_width=True):
            ds.set_ranking(member, order)
            st.session_state["_saved"] = member
            st.cache_data.clear()
            st.rerun()
        if c.button("Clear", use_container_width=True):
            ds.set_ranking(member, [])
            st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()
        if st.session_state.get("_saved") == member:
            st.success(f"✓ Saved {member}'s ranking.")
            st.session_state.pop("_saved", None)
    with right:
        rows = _consensus_rows(df)
        body = ""
        for r in rows:
            rc = "#E6BE6A" if r["overall_rank"] == 1 else "#9DB3A7"
            body += (f"<div style='margin-bottom:13px'><div style='display:flex;align-items:center;justify-content:space-between;gap:10px'>"
                     f"<div style='display:flex;align-items:center;gap:9px;min-width:0'>"
                     f"<span style='font-size:12px;font-weight:800;color:{rc};width:16px'>{r['overall_rank']}</span>"
                     f"<span style='font-size:13.5px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;"
                     f"text-overflow:ellipsis'>{r['restaurant']}</span></div>"
                     f"<span style='font-size:13.5px;font-weight:800;color:#E6BE6A'>{score100(r['median'])}</span></div>"
                     f"<div style='margin-top:6px;height:5px;background:rgba(255,255,255,.1);border-radius:99px;overflow:hidden'>"
                     f"<div style='width:{r['median']}%;height:100%;background:#E6BE6A;border-radius:99px'></div></div></div>")
        st.markdown("<div style='background:#26332B;border-radius:16px;padding:20px 22px'>"
                    "<div class='ax-lab' style='color:#8FB6A2'>Live consensus</div>"
                    "<div style='font-size:12.5px;color:#9DB3A7;margin-top:5px'>Median of everyone's percentiles. "
                    "Updates the moment you save.</div>"
                    f"<div style='margin-top:16px'>{body or '<div style=color:#9DB3A7>No rankings yet.</div>'}</div></div>",
                    unsafe_allow_html=True)


# ---------- full leaderboard view ----------

def leaderboard_view(df: pd.DataFrame) -> None:
    st.button("← Back to dashboard", on_click=_set_view, args=("dashboard",), key="bk_lb")
    st.markdown("<div style='font-size:28px;font-weight:900;margin-top:8px'>The official ranking</div>"
                "<div style='font-size:14.5px;color:#7C7666;margin-top:6px;max-width:660px;line-height:1.55'>"
                "Group consensus — the median of everyone's normalised order. One contrarian can't sink a shared "
                "favourite. Higher is the group's pick.</div>", unsafe_allow_html=True)
    rows = _consensus_rows(df)
    if not rows:
        st.markdown("<div class='ax-card' style='margin-top:20px;text-align:center;padding:34px'>"
                    "<div style='font-size:2rem'>🏆</div><div style='font-size:1.1rem;font-weight:800;margin-top:8px'>"
                    "No rankings yet — be the first.</div></div>", unsafe_allow_html=True)
        st.button("Add your ranking →", type="primary", on_click=_set_view, args=("rank",), key="lb_empty")
        return
    hdr = ("<div style='display:grid;grid-template-columns:56px 1fr 150px 210px 120px;padding:14px 22px;background:#FBFAF6;"
           "border-bottom:1px solid #EDE6D6;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;"
           "color:#9A968C'><div>#</div><div>Restaurant</div><div>Country</div><div>Median</div><div>Ranked by</div></div>")
    body = ""
    for r in rows:
        rc = "#C0902F" if r["overall_rank"] == 1 else "#9A968C"
        rowbg = "#FCFAF3" if r["overall_rank"] == 1 else "#fff"
        av = "".join(avatar(m, 28, "#fff") for m in sorted(r["ranked_by"], key=ds.RATERS.index))
        body += (f"<div style='display:grid;grid-template-columns:56px 1fr 150px 210px 120px;padding:17px 22px;"
                 f"border-bottom:1px solid #F3EEE2;align-items:center;background:{rowbg}'>"
                 f"<div style='font-size:20px;font-weight:900;color:{rc}'>{r['overall_rank']}</div>"
                 f"<div style='display:flex;align-items:center;gap:11px'>{code_chip(r['iso'],'none')}"
                 f"<span style='font-size:15.5px;font-weight:800'>{r['restaurant']}</span></div>"
                 f"<div style='font-size:14px;color:#6B6558'>{flag(r['iso'],13)} {r['country']}</div>"
                 f"<div><div style='display:flex;align-items:baseline;gap:5px'>"
                 f"<span style='font-size:18px;font-weight:900;color:#2E7D5B'>{score100(r['median'])}</span>"
                 f"<span style='font-size:12px;font-weight:700;color:#B4AE9E'>/100</span></div>"
                 f"<div class='ax-bar' style='margin-top:6px;width:170px'><div style='width:{r['median']}%'></div></div></div>"
                 f"<div style='display:flex;align-items:center'>{av}</div></div>")
    st.markdown(f"<div class='ax-card' style='margin-top:22px;padding:0;overflow:hidden'>{hdr}{body}</div>",
                unsafe_allow_html=True)

    st.markdown("<div class='ax-lab' style='margin-top:24px'>Each person's #1</div>", unsafe_allow_html=True)
    cards = ""
    for m in ds.RATERS:
        sub = df[pd.to_numeric(df[m], errors="coerce") == 1]
        top = sub.iloc[0]["Restaurant"] if not sub.empty else "Not ranked yet"
        country = sub.iloc[0]["Country"] if not sub.empty else "—"
        col = "#1F2328" if not sub.empty else "#B4AE9E"
        cards += (f"<div class='ax-card' style='padding:16px'><div style='display:flex;align-items:center;gap:10px'>"
                  f"{avatar(m,34,'#fff')}<div style='font-size:13px;font-weight:700;color:#7C7666'>{m}</div></div>"
                  f"<div style='margin-top:12px;font-size:15px;font-weight:800;color:{col}'>{top}</div>"
                  f"<div style='font-size:12px;color:#9A968C;margin-top:2px'>{country}</div></div>")
    st.markdown(f"<div style='margin-top:13px;display:grid;grid-template-columns:repeat(5,1fr);gap:14px'>{cards}</div>",
                unsafe_allow_html=True)


# ---------- forms + secondary views ----------

def _add_form(name: str, iso: str) -> None:
    kind = st.radio("Type", ["Visited", "Want to go (wishlist)"], horizontal=True, key=f"kind_{iso}")
    wishlist = kind.startswith("Want")
    with st.form(key=f"add_{iso}", clear_on_submit=True):
        restaurant = st.text_input("Restaurant name", placeholder="e.g., Buka")
        maps_url = st.text_input("Google Maps link (optional)", placeholder="https://maps.app.goo.gl/…")
        dishes = st.text_input("Dishes (comma-separated, optional)", placeholder="jollof, suya")
        notes = st.text_area("Notes (optional)")
        visit_date = None if wishlist else st.date_input("Visit date", value=date.today(), format="MM/DD/YYYY")
        if st.form_submit_button("Save spot", type="primary"):
            if not restaurant.strip():
                st.error("Restaurant name is required.")
                return
            row = {"Country": name, "ISO_A3": iso, "Restaurant": restaurant.strip(), "Dishes": dishes.strip(),
                   "Notes": notes.strip(), "Maps_URL": maps_url.strip(),
                   "Status": ds.STATUS_WISHLIST if wishlist else ds.STATUS_VISITED}
            if not wishlist:
                row["Visit Date"] = pd.to_datetime(visit_date)
            ds.append_row(row)
            st.success(f"Added {restaurant.strip()}.")
            st.cache_data.clear()
            st.rerun()


def add_spot_page(africa, df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:28px;font-weight:900;margin-top:8px'>Add a spot</div>"
                "<div style='font-size:14px;color:#7C7666;margin-top:6px'>Log a place. No scores here — "
                "ranking happens on the ballot.</div>", unsafe_allow_html=True)
    names = sorted(africa["name"].tolist())
    iso_by = dict(zip(africa["name"], africa["iso_a3"]))
    cur = st.session_state.get("selected_country")
    idx = names.index(cur["name"]) if cur and cur["name"] in names else 0
    country = st.selectbox("Country", names, index=idx)
    _add_form(country, iso_by[country])


def wishlist_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:28px;font-weight:900;margin-top:8px'>The wishlist</div>", unsafe_allow_html=True)
    wish = ds.wishlist(df)
    if wish.empty:
        st.info("Nothing on the wishlist yet.")
        return
    st.caption(f"{len(wish)} spots to try across {wish['ISO_A3'].nunique()} countries · the DMV.")
    cards = ""
    for _, r in wish.sort_values("Country").iterrows():
        meta = str(r.get("Notes", "")).strip()
        maps = str(r.get("Maps_URL", "")).strip()
        link = f" · <a href='{maps}' target='_blank'>Maps</a>" if maps else ""
        cards += (f"<div class='ax-card' style='display:flex;gap:13px'>{code_chip(r['ISO_A3'],'wishlist')}"
                  f"<div style='flex:1;min-width:0'><div style='font-weight:700'>{flag(r['ISO_A3'],13)} {r['Country']}</div>"
                  f"<div style='font-size:.9rem;color:#2E5A44;font-weight:600;margin-top:2px'>{r['Restaurant']}</div>"
                  f"<div style='font-size:.8rem;color:#9A968C;margin-top:2px'>{meta}{link}</div></div></div>")
    st.markdown(f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px'>{cards}</div>",
                unsafe_allow_html=True)


def all_spots_page(df: pd.DataFrame) -> None:
    st.markdown("<div style='font-size:28px;font-weight:900;margin-top:8px'>All spots (data)</div>", unsafe_allow_html=True)
    idx = consensus_index(df)
    show = df.copy()
    show["Overall"] = show["Restaurant"].map(lambda n: idx[n]["overall_rank"] if n in idx else pd.NA)
    show["Median"] = show["Restaurant"].map(lambda n: round(idx[n]["median"], 1) if n in idx else pd.NA)
    show["Visit Date"] = pd.to_datetime(show["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")
    cols = ["Overall", "Country", "Restaurant", "Status", "Median", *ds.RATERS, "Visit Date", "Dishes", "Notes", "Maps_URL"]
    st.dataframe(show[cols].sort_values(["Status", "Overall"], na_position="last"), hide_index=True, width="stretch")
    st.download_button("⬇ Download CSV", data=df.to_csv(index=False), file_name="africax_restaurants.csv", mime="text/csv")


def _back_button(key: str) -> None:
    st.button("← Back to dashboard", on_click=_set_view, args=("dashboard",), key=key)
