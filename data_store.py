"""AfricaX data layer — dual backend (local CSV / Google Sheets), ranking model.

Storage:
- **Local dev / tests / offline:** ``data/restaurants.csv`` (no credentials needed).
- **Streamlit Cloud (shared, persistent):** a Google Sheet, when credentials are
  configured. Streamlit Cloud has an ephemeral filesystem, so a local CSV can't
  persist writes there — the Sheet is the durable, multi-user source of truth.

Backend selection is automatic (``using_sheets()``): if a service account + sheet
URL are configured via Streamlit secrets or env vars, the Sheet is used; otherwise
the CSV. **Only ``load()``/``save()`` know the difference** — every mutation
(``set_ranking``, ``append_row``, …) is built on them, so the whole app is
backend-agnostic. An empty Sheet is auto-seeded from the committed CSV on first read.

Schema (canonical column order)::

    Country, ISO_A3, Restaurant,
    Fayez, Muhammad, Seth, Ian, Shubham,   # each member's RANK (1 = favorite), blank = not ranked
    Visit Date, Notes, Dishes,
    Status,                                # "visited" | "wishlist"
    Maps_URL                               # optional Google Maps link
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "restaurants.csv"

# The group of friends who rank. Order here is the column order.
RATERS = ["Fayez", "Muhammad", "Seth", "Ian", "Shubham"]

STATUS_VISITED = "visited"
STATUS_WISHLIST = "wishlist"
STATUSES = (STATUS_VISITED, STATUS_WISHLIST)

_BASE = ["Country", "ISO_A3", "Restaurant"]
_TAIL = ["Visit Date", "Notes", "Dishes", "Status", "Maps_URL"]
COLUMNS = _BASE + RATERS + _TAIL

# Google Sheets
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_WORKSHEET = "restaurants"
_WS = None  # cached authorized worksheet handle (single-process container)


def empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


# ---------- backend selection ----------

def _sheet_config() -> Optional[Tuple[dict, str]]:
    """(service_account_info, sheet_ref) if Google Sheets is configured, else None."""
    # 1) Streamlit secrets — Streamlit Cloud, or a local .streamlit/secrets.toml
    try:
        import streamlit as st
        sa = st.secrets["gcp_service_account"]
        url = st.secrets["africax_sheet"]["url"]
        return dict(sa), str(url)
    except Exception:
        pass
    # 2) Environment (local dev / CI): a path to the key + the sheet URL
    sa_path = os.environ.get("AFRICAX_SA_JSON")
    url = os.environ.get("AFRICAX_SHEET_URL")
    if sa_path and url and Path(sa_path).exists():
        return json.loads(Path(sa_path).read_text(encoding="utf-8")), url
    return None


def using_sheets() -> bool:
    return _sheet_config() is not None


def backend_name() -> str:
    return "sheets" if using_sheets() else "csv"


def _worksheet():
    """Authorized gspread worksheet, cached for the life of the process."""
    global _WS
    if _WS is not None:
        return _WS
    cfg = _sheet_config()
    if not cfg:
        return None
    creds_info, ref = cfg
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(creds_info, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(ref) if ref.startswith("http") else gc.open_by_key(ref)
    try:
        ws = sh.worksheet(_WORKSHEET)
    except Exception:
        ws = sh.sheet1
        try:
            ws.update_title(_WORKSHEET)
        except Exception:
            pass
    _WS = ws
    return ws


# ---------- shared normalisation ----------

def _normalize_in(df: pd.DataFrame) -> pd.DataFrame:
    """Raw string frame (from any backend) → typed frame in canonical schema."""
    df = df.copy()
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    if "Group_Rating" in df.columns:  # retired mean-rating column
        df = df.drop(columns=["Group_Rating"])

    df["Status"] = df["Status"].astype(str).str.strip().str.lower()
    df.loc[~df["Status"].isin(STATUSES), "Status"] = STATUS_VISITED
    df["ISO_A3"] = df["ISO_A3"].astype(str).str.upper().str.strip()

    for c in RATERS:  # per-member ranks are integers
        df[c] = pd.to_numeric(df[c], errors="coerce")

    strict = pd.to_datetime(df["Visit Date"], format="%m/%d/%Y", errors="coerce")
    loose = pd.to_datetime(df["Visit Date"], errors="coerce")
    df["Visit Date"] = strict.fillna(loose)

    return df[COLUMNS].reset_index(drop=True)


def _normalize_out(df: pd.DataFrame) -> pd.DataFrame:
    """Typed frame → serialisable string frame in canonical schema (for any backend)."""
    out = df.copy()
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = ""

    out["Status"] = out["Status"].astype(str).str.strip().str.lower()
    out.loc[~out["Status"].isin(STATUSES), "Status"] = STATUS_VISITED
    out["ISO_A3"] = out["ISO_A3"].astype(str).str.upper().str.strip()
    out["Visit Date"] = pd.to_datetime(out["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")

    for c in RATERS:
        out[c] = pd.to_numeric(out[c], errors="coerce").apply(
            lambda v: "" if pd.isna(v) else str(int(round(v)))
        )

    return out[COLUMNS].fillna("")


# ---------- per-backend raw read/write ----------

def _read_csv_raw() -> pd.DataFrame:
    if not CSV_PATH.exists():
        return empty()
    return pd.read_csv(CSV_PATH, dtype=str).fillna("")


def _write_csv(out: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CSV_PATH.with_suffix(".csv.tmp")
    out.to_csv(tmp, index=False)
    tmp.replace(CSV_PATH)


def _read_sheet_raw() -> pd.DataFrame:
    ws = _worksheet()
    values = ws.get_all_values()
    if not values or not any(str(v).strip() for v in values[0]):
        # Empty sheet → seed it from the committed CSV so the group starts populated.
        seed = _normalize_out(_normalize_in(_read_csv_raw()))
        _write_sheet(seed)
        return seed
    header, *rows = values
    return pd.DataFrame(rows, columns=header)


def _write_sheet(out: pd.DataFrame) -> None:
    ws = _worksheet()
    values = [list(map(str, out.columns))] + out.astype(str).values.tolist()
    ws.clear()
    try:
        ws.update(values=values, range_name="A1")  # gspread >= 6
    except TypeError:
        ws.update("A1", values)  # older gspread signature


# ---------- public load / save ----------

def load() -> pd.DataFrame:
    """Load visits + wishlist in stable row order from the active backend."""
    raw = _read_sheet_raw() if using_sheets() else _read_csv_raw()
    return _normalize_in(raw)


def save(df: pd.DataFrame) -> None:
    """Write the whole frame back (canonical schema) to the active backend."""
    out = _normalize_out(df)
    if using_sheets():
        _write_sheet(out)
    else:
        _write_csv(out)


# ---------- views ----------

def visited(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Status"] == STATUS_VISITED].copy()


def wishlist(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Status"] == STATUS_WISHLIST].copy()


def status_by_iso(df: pd.DataFrame) -> dict:
    """Best status per country for map colouring (visited beats wishlist)."""
    out: dict = {}
    for _, r in df.iterrows():
        iso = r["ISO_A3"]
        if r["Status"] == STATUS_VISITED:
            out[iso] = STATUS_VISITED
        else:
            out.setdefault(iso, STATUS_WISHLIST)
    return out


def country_stats(df: pd.DataFrame) -> dict:
    """Per-ISO counts used for map tooltips."""
    stats: dict = {}
    for iso, g in df.groupby("ISO_A3"):
        stats[iso] = {
            "visited": int((g["Status"] == STATUS_VISITED).sum()),
            "wishlist": int((g["Status"] == STATUS_WISHLIST).sum()),
        }
    return stats


# ---------- mutations (backend-agnostic — built on load()/save()) ----------

def append_row(row: dict) -> None:
    df = load()
    new = pd.DataFrame([row]).reindex(columns=COLUMNS)
    df = new if df.empty else pd.concat([df, new], ignore_index=True)
    save(df)


def update_row(index: int, row: dict) -> None:
    df = load()
    for k, v in row.items():
        df.at[index, k] = v
    save(df)


def delete_row(index: int) -> None:
    df = load()
    df = df.drop(index=index).reset_index(drop=True)
    save(df)


def set_ranking(member: str, ordered_restaurants: List[str]) -> None:
    """Rewrite a member's whole ranking column from an ordered list (#1 first).

    Restaurants are matched by name; anything not in the list is left unranked
    (blank) for that member. Ranks are renumbered 1..N so the input is always clean.
    """
    if member not in RATERS:
        raise ValueError(f"Unknown member: {member}")
    df = load()
    rank_map = {name: i + 1 for i, name in enumerate(ordered_restaurants)}
    df[member] = df["Restaurant"].map(rank_map)
    save(df)


# ---------- integrity ----------

def missing_columns(df: pd.DataFrame) -> list:
    """Columns the app needs but the frame lacks — for a loud startup check."""
    return [c for c in COLUMNS if c not in df.columns]
