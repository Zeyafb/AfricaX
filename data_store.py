"""AfricaX data layer — local CSV backend (ranking model).

Single source of truth: ``data/restaurants.csv``. This module owns the schema
and all reads/writes; it stores each member's **rank** of a restaurant. Consensus
scoring (percentile + median → overall rank) lives in ``rankings.py``, ported
from the Movie Ranks project.

Schema (canonical column order)::

    Country, ISO_A3, Restaurant,
    Fayez, Muhammad, Seth, Ian, Shubham,   # each member's RANK (1 = favorite), blank = not ranked
    Visit Date, Notes, Dishes,
    Status,                                # "visited" | "wishlist"
    Maps_URL                               # optional Google Maps link

Rankings apply to visited restaurants. Wishlist rows carry no ranks.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "restaurants.csv"

# The group of friends who rank. Order here is the CSV column order.
RATERS = ["Fayez", "Muhammad", "Seth", "Ian", "Shubham"]

STATUS_VISITED = "visited"
STATUS_WISHLIST = "wishlist"
STATUSES = (STATUS_VISITED, STATUS_WISHLIST)

_BASE = ["Country", "ISO_A3", "Restaurant"]
_TAIL = ["Visit Date", "Notes", "Dishes", "Status", "Maps_URL"]
COLUMNS = _BASE + RATERS + _TAIL


# ---------- load / save ----------

def empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


def load() -> pd.DataFrame:
    """Load visits + wishlist in file order (stable row index for edit/delete)."""
    if not CSV_PATH.exists():
        return empty()

    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")

    # Migrate: add missing columns; drop the retired Group_Rating (mean model).
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    if "Group_Rating" in df.columns:
        df = df.drop(columns=["Group_Rating"])

    df["Status"] = df["Status"].astype(str).str.strip().str.lower()
    df.loc[~df["Status"].isin(STATUSES), "Status"] = STATUS_VISITED
    df["ISO_A3"] = df["ISO_A3"].astype(str).str.upper().str.strip()

    # Per-member ranks are integers.
    for c in RATERS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

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
    out["Visit Date"] = pd.to_datetime(out["Visit Date"], errors="coerce").dt.strftime("%m/%d/%Y")

    for c in RATERS:
        out[c] = pd.to_numeric(out[c], errors="coerce").apply(
            lambda v: "" if pd.isna(v) else str(int(round(v)))
        )

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
    """Per-ISO counts used for map tooltips."""
    stats: dict = {}
    for iso, g in df.groupby("ISO_A3"):
        stats[iso] = {
            "visited": int((g["Status"] == STATUS_VISITED).sum()),
            "wishlist": int((g["Status"] == STATUS_WISHLIST).sum()),
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
