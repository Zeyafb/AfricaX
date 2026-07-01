"""Tests for the AfricaX CSV data layer (ranking model).

Focus: per-member *ranks* survive a round-trip, ``set_ranking`` rewrites a member's
column from an ordered list (and renumbers cleanly), the retired ``Group_Rating``
column is dropped on load, and old CSVs migrate to the Status/Maps_URL schema.
"""

import pandas as pd
import pytest


# ---------- round-trip of ranks ----------

def test_visited_round_trip_preserves_ranks(store):
    row = {
        "Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "Test Spot",
        "Fayez": 2, "Muhammad": 1, "Seth": 3, "Ian": 5, "Shubham": 4,
        "Visit Date": pd.Timestamp("2026-01-15"), "Status": "visited",
    }
    store.append_row(row)
    r = store.load().iloc[0]
    assert [r["Fayez"], r["Muhammad"], r["Seth"], r["Ian"], r["Shubham"]] == [2, 1, 3, 5, 4]
    assert r["Status"] == "visited"


# ---------- set_ranking ----------

def _seed_three(store):
    for name, iso in [("Chez Dior", "SEN"), ("Fettoosh", "MAR"), ("Koshary", "EGY")]:
        store.append_row({"Country": name, "ISO_A3": iso, "Restaurant": name, "Status": "visited"})


def test_set_ranking_writes_member_order(store):
    _seed_three(store)
    store.set_ranking("Fayez", ["Fettoosh", "Chez Dior", "Koshary"])
    df = store.load().set_index("Restaurant")
    assert df.loc["Fettoosh", "Fayez"] == 1
    assert df.loc["Chez Dior", "Fayez"] == 2
    assert df.loc["Koshary", "Fayez"] == 3


def test_set_ranking_renumbers_and_leaves_others_blank(store):
    _seed_three(store)
    # Only two of the three; ranks come out 1..2, the third stays unranked.
    store.set_ranking("Seth", ["Koshary", "Fettoosh"])
    df = store.load().set_index("Restaurant")
    assert df.loc["Koshary", "Seth"] == 1
    assert df.loc["Fettoosh", "Seth"] == 2
    assert pd.isna(df.loc["Chez Dior", "Seth"])


def test_set_ranking_is_independent_per_member(store):
    _seed_three(store)
    store.set_ranking("Fayez", ["Fettoosh", "Chez Dior", "Koshary"])
    store.set_ranking("Muhammad", ["Chez Dior", "Koshary", "Fettoosh"])
    df = store.load().set_index("Restaurant")
    assert df.loc["Fettoosh", "Fayez"] == 1 and df.loc["Fettoosh", "Muhammad"] == 3


def test_set_ranking_unknown_member_raises(store):
    with pytest.raises(ValueError):
        store.set_ranking("Nobody", ["X"])


# ---------- migration ----------

def test_retired_group_rating_column_is_dropped(store):
    store.CSV_PATH.write_text(
        "Country,ISO_A3,Restaurant,Fayez,Muhammad,Seth,Ian,Shubham,"
        "Group_Rating,Visit Date,Notes,Dishes,Status,Maps_URL\n"
        "Ghana,GHA,X,1,2,3,,,7.5,01/01/2026,,,visited,\n"
    )
    df = store.load()
    assert "Group_Rating" not in df.columns
    assert df.iloc[0]["Fayez"] == 1  # ranks survive the drop
    assert store.missing_columns(df) == []


def test_old_schema_migrates(store):
    """A pre-Status CSV loads with sane defaults and the full schema."""
    store.CSV_PATH.write_text(
        "Country,ISO_A3,Restaurant,Fayez,Muhammad,Seth,Ian,Shubham,Visit Date,Notes,Dishes\n"
        "Egypt,EGY,Koshary,1,2,,,,10/08/2025,,\n"
    )
    df = store.load()
    assert "Status" in df.columns and "Maps_URL" in df.columns
    assert df.iloc[0]["Status"] == "visited"
    assert store.missing_columns(df) == []


# ---------- wishlist ----------

def test_wishlist_entry_has_no_ranks(store):
    store.append_row({
        "Country": "Sierra Leone", "ISO_A3": "SLE", "Restaurant": "Sweet Sweet Kitchen",
        "Status": "wishlist", "Maps_URL": "https://maps.app.goo.gl/abc",
    })
    df = store.load()
    r = df.iloc[0]
    assert r["Status"] == "wishlist"
    assert all(pd.isna(r[m]) for m in store.RATERS)
    assert store.wishlist(df).shape[0] == 1
    assert store.visited(df).shape[0] == 0


def test_status_by_iso_visited_beats_wishlist(store):
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "A", "Status": "wishlist"})
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "B", "Status": "visited"})
    assert store.status_by_iso(store.load())["GHA"] == "visited"


def test_country_stats_counts(store):
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "A", "Status": "visited"})
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "B", "Status": "wishlist"})
    s = store.country_stats(store.load())["GHA"]
    assert s == {"visited": 1, "wishlist": 1}


# ---------- mutations ----------

def test_update_and_delete(store):
    store.append_row({"Country": "Ghana", "ISO_A3": "GHA", "Restaurant": "A",
                      "Fayez": 1, "Status": "visited"})
    store.update_row(0, {"Restaurant": "A (renamed)", "Fayez": 2})
    df = store.load()
    assert df.iloc[0]["Restaurant"] == "A (renamed)"
    assert df.iloc[0]["Fayez"] == 2

    store.delete_row(0)
    assert store.load().empty
