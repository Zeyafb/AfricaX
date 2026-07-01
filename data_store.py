"""AfricaX data layer — local CSV backend.

Single source of truth: ``data/restaurants.csv``. This module owns the schema,
the group-rating math, and all reads/writes so the UI never touches the file
directly. Backed out of Google Sheets (June 2026) — see README.

Schema (canonical column order)::

    Country, ISO_A3, Restaurant,
    Fayez, Muhammad, Seth, Ian, Shubham,   # per-person ratings, 1-10, blank = absent
    Group_Rating,                          # mean of present ratings (derived)
    Visit Date, Notes, Dishes,
    Status,                                # "visited" | "wishlist"
    Maps_URL                               # optional Google Maps link
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "restaurants.csv"

# The group of friends who rate. Order here is the CSV column order.
RATERS = ["Fayez", "Muhammad", "Seth", "Ian", "Shubham"]

STATUS_VISITED = "visited"
STATUS_WISHLIST = "wishlist"
STATUSES = (STATUS_VISITED, STATUS_WISHLIST)

_BASE = ["Country", "ISO_A3", "Restaurant"]
_TAIL = ["Group_Rating", "Visit Date", "Notes", "Dishes", "Status", "Maps_URL"]
COLUMNS = _BASE + RATERS + _TAIL

_NUMERIC = RATERS + ["Group_Rating"]


# ---------- group rating ----------

def group_rating(ratings: Iterable) -> Optional[float]:
    """Mean of the ratings that are actually present (non-blank, non-NaN).

    Returns ``None`` when nobody rated (e.g. a wishlist entry).
    """
    vals = []
    for v in ratings:
        if v is None:
            continue
        if isinstance(v, float) and pd.isna(v):
            continue
        s = str(v).strip()
        if s == "":
            continue
        try:
            vals.append(float(s))
        except ValueError:
            continue
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _recompute_group(df: pd.DataFrame) -> pd.Series:
    return df.apply(lambda r: group_rating([r[x] for x in RATERS]), axis=1)


# ---------- load / save ----------

def empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


def load() -> pd.DataFrame:
    """Load visits + wishlist in file order (stable row index for edit/delete)."""
    if not CSV_PATH.exists():
        return empty()

    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")

    # Migrate: add any missing columns (older files had no Status / Maps_URL).
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""

    # Normalise status; anything unknown/blank is treated as a visited record.
    df["Status"] = df["Status"].astype(str).str.strip().str.lower()
    df.loc[~df["Status"].isin(STATUSES), "Status"] = STATUS_VISITED

    df["ISO_A3"] = df["ISO_A3"].astype(str).str.upper().str.strip()

    for c in _NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Group rating is always derived, never trusted from disk.
    df["Group_Rating"] = _recompute_group(df)

    # Dates: prefer MM/DD/YYYY, fall back to anything parseable.
    strict = pd.to_datetime(df["Visit Date"], format="%m/%d/%Y", errors="coerce")
    loose = pd.to_datetime(df["Visit Date"], errors="coerce")
    df["Visit Date"] = strict.fillna(loose)

    return df[COLUMNS].reset_index(drop=True)


def save(df: pd.DataFrame) -> None:
    """Write the whole frame back atomically in canonical schema."""
    out = df.copy()

    for c in COLUMNS:
        if c not in out.columns:
            out[c] = ""

    out["Status"] = out["Status"].astype(str).str.strip().str.lower()
    out.loc[~out["Status"].isin(STATUSES), "Status"] = STATUS_VISITED
    out["ISO_A3"] = out["ISO_A3"].astype(str).str.upper().str.strip()

    out["Group_Rating"] = _recompute_group(out)
    out["Visit Date"] = pd.to_datetime(out["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")

    for c in _NUMERIC:
        out[c] = out[c].apply(lambda v: "" if pd.isna(v) else f"{float(v):g}")

    out = out[COLUMNS].fillna("")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CSV_PATH.with_suffix(".csv.tmp")
    out.to_csv(tmp, index=False)
    tmp.replace(CSV_PATH)


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
    """Per-ISO summary used for map tooltips."""
    stats: dict = {}
    for iso, g in df.groupby("ISO_A3"):
        vis = g[g["Status"] == STATUS_VISITED]
        wish = g[g["Status"] == STATUS_WISHLIST]
        avg = vis["Group_Rating"].dropna().mean()
        stats[iso] = {
            "visited": int(len(vis)),
            "wishlist": int(len(wish)),
            "avg": round(float(avg), 1) if pd.notna(avg) else None,
        }
    return stats


# ---------- mutations ----------

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


# ---------- integrity ----------

def missing_columns(df: pd.DataFrame) -> list:
    """Columns the app needs but the frame lacks — for a loud startup check."""
    return [c for c in COLUMNS if c not in df.columns]
