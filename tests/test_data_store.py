"""Tests for the AfricaX CSV data layer.

Focus: the things that broke during the Sheets migration — per-person ratings
must survive a round-trip, the group rating must be derived correctly, and old
CSVs must migrate to the Status/Maps_URL schema.
"""

import pandas as pd
import pytest


# ---------- group rating math ----------

def test_group_rating_mean_of_present(store):
    assert store.group_rating([8, 9, 7]) == 8.0


def test_group_rating_ignores_blanks_and_nan(store):
    assert store.group_rating([10, "", None, float("nan"), 6]) == 8.0


def test_group_rating_none_when_empty(store):
    assert store.group_rating(["", None]) is None


# ---------- round-trip ----------

def test_visited_round_trip_preserves_per_person(store):
    row = {
        "Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "Test Spot",
        "Fayez": 9, "Muhammad": 8, "Seth": 7, "Ian": 6, "Shubham": 10,
        "Visit Date": pd.Timestamp("2026-01-15"), "Status": "visited",
    }
    store.append_row(row)
    df = store.load()
    r = df.iloc[0]
    assert [r["Fayez"], r["Muhammad"], r["Seth"], r["Ian"], r["Shubham"]] == [9, 8, 7, 6, 10]
    assert r["Group_Rating"] == 8.0  # (9+8+7+6+10)/5
    assert r["Status"] == "visited"


def test_group_rating_is_derived_not_trusted(store):
    """A wrong Group_Rating on disk is recomputed on load."""
    store.CSV_PATH.write_text(
        "Country,ISO_A3,Restaurant,Fayez,Muhammad,Seth,Ian,Shubham,"
        "Group_Rating,Visit Date,Notes,Dishes,Status,Maps_URL\n"
        "Ghana,GHA,X,10,10,10,10,10,1.0,01/01/2026,,,visited,\n"
    )
    assert store.load().iloc[0]["Group_Rating"] == 10.0


# ---------- migration ----------

def test_old_schema_migrates(store):
    """A pre-migration CSV (no Status/Maps_URL) loads with sane defaults."""
    store.CSV_PATH.write_text(
        "Country,ISO_A3,Restaurant,Fayez,Muhammad,Seth,Ian,Shubham,"
        "Group_Rating,Visit Date,Notes,Dishes\n"
        "Egypt,EGY,Koshary,8,8,8,8,8,8,10/08/2025,,\n"
    )
    df = store.load()
    assert "Status" in df.columns and "Maps_URL" in df.columns
    assert df.iloc[0]["Status"] == "visited"
    assert store.missing_columns(df) == []


# ---------- wishlist ----------

def test_wishlist_entry_has_no_ratings(store):
    store.append_row({
        "Country": "Sierra Leone", "ISO_A3": "SLE", "Restaurant": "Sweet Sweet Kitchen",
        "Status": "wishlist", "Maps_URL": "https://maps.app.goo.gl/abc",
    })
    df = store.load()
    r = df.iloc[0]
    assert r["Status"] == "wishlist"
    assert pd.isna(r["Group_Rating"])
    assert store.wishlist(df).shape[0] == 1
    assert store.visited(df).shape[0] == 0


def test_status_by_iso_visited_beats_wishlist(store):
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "A", "Status": "wishlist"})
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "B",
                      "Fayez": 8, "Status": "visited"})
    assert store.status_by_iso(store.load())["GHA"] == "visited"


# ---------- mutations ----------

def test_update_and_delete(store):
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "A",
                      "Fayez": 5, "Status": "visited"})
    store.update_row(0, {"Restaurant": "A (renamed)", "Fayez": 9})
    df = store.load()
    assert df.iloc[0]["Restaurant"] == "A (renamed)"
    assert df.iloc[0]["Group_Rating"] == 9.0

    store.delete_row(0)
    assert store.load().empty


def test_mark_wishlist_visited(store):
    store.append_row({"Country": "Sierra Leone", "ISO_A3": "SLE",
                      "Restaurant": "Sweet Sweet Kitchen", "Status": "wishlist"})
    store.update_row(0, {"Status": "visited", "Fayez": 8, "Muhammad": 9,
                         "Visit Date": pd.Timestamp("2026-02-01")})
    df = store.load()
    assert df.iloc[0]["Status"] == "visited"
    assert df.iloc[0]["Group_Rating"] == 8.5
