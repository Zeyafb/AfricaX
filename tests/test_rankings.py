"""Tests for the consensus ranking port (mirrors the Movie Ranks method)."""

import pandas as pd

import rankings as rk


# ---------- normalize_rank ----------

def test_normalize_rank_endpoints_and_middle():
    assert rk.normalize_rank(1, 5) == 100.0        # #1 always 100
    assert rk.normalize_rank(5, 5) == 0.0          # last always 0
    assert rk.normalize_rank(3, 5) == 50.0         # middle of 5
    assert rk.normalize_rank(1, 1) == 100.0        # solo list


# ---------- median beats mean (the whole point) ----------

def test_median_resists_one_outlier():
    """4 people rank X first, 1 ranks it last → median stays 100 (mean would be 80)."""
    lists = {
        "Fayez": ["X", "A"],
        "Muhammad": ["X", "B"],
        "Seth": ["X", "C"],
        "Ian": ["X", "D"],
        "Shubham": ["E", "X"],  # the outlier: X is last for Shubham
    }
    res = {r["restaurant"]: r for r in rk.consensus(lists, min_coverage=1)}
    assert res["X"]["median"] == 100.0
    assert res["X"]["coverage"] == 5
    assert res["X"]["overall_rank"] == 1


# ---------- overall ordering ----------

def test_overall_rank_ordering():
    lists = {
        "Fayez": ["Chez Dior", "Fettoosh", "Koshary"],
        "Muhammad": ["Fettoosh", "Chez Dior", "Koshary"],
        "Seth": ["Chez Dior", "Koshary", "Fettoosh"],
    }
    res = rk.consensus(lists, min_coverage=1)
    order = [r["restaurant"] for r in res]
    assert order == ["Chez Dior", "Fettoosh", "Koshary"]
    medians = {r["restaurant"]: r["median"] for r in res}
    assert medians == {"Chez Dior": 100.0, "Fettoosh": 50.0, "Koshary": 0.0}


def test_min_coverage_filters():
    lists = {"Fayez": ["Solo", "Other"], "Muhammad": ["Other"]}
    res = rk.consensus(lists, min_coverage=2)
    names = [r["restaurant"] for r in res]
    assert names == ["Other"]  # Solo has coverage 1, filtered out


def test_cap_limits_list():
    lists = {"Fayez": ["A", "B", "C", "D"]}  # cap at 2 → only A,B scored
    res = {r["restaurant"]: r for r in rk.consensus(lists, cap=2)}
    assert set(res) == {"A", "B"}


# ---------- reading ranks out of the CSV shape ----------

def test_rankings_from_df_reconstructs_order():
    df = pd.DataFrame({
        "Restaurant": ["Chez Dior", "Fettoosh", "Koshary"],
        "Country": ["Senegal", "Morocco", "Egypt"],
        "Fayez": [2, 1, 3],       # Fayez's ranks
        "Muhammad": [1, None, 2],  # Muhammad didn't rank Fettoosh
    })
    got = rk.rankings_from_df(df, raters=["Fayez", "Muhammad"])
    assert got["Fayez"] == ["Fettoosh", "Chez Dior", "Koshary"]
    assert got["Muhammad"] == ["Chez Dior", "Koshary"]


def test_consensus_table_shape():
    df = pd.DataFrame({
        "Restaurant": ["Chez Dior", "Fettoosh"],
        "Country": ["Senegal", "Morocco"],
        "Fayez": [1, 2],
        "Muhammad": [2, 1],
    })
    tbl = rk.consensus_table(df, min_coverage=1)
    assert list(tbl.columns) == ["overall_rank", "restaurant", "country", "median", "coverage", "ranked_by"]
    assert tbl.iloc[0]["overall_rank"] == 1
