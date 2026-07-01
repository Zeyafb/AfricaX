"""AfricaX consensus ranking — ported from the Movie Ranks project.

Faithful copy of the scoring method in
``Movie Ranks/2026/calculate_rankings.py`` (``normalize_rank`` + ``calculate``):

1. Each member submits an ORDERED ranking of the restaurants they've tried
   (their #1 first). Lists may be different sizes.
2. Each rank becomes a 0-100 percentile *within that member's own list*:
   ``100 * (size - rank) / (size - 1)`` — so everyone's #1 = 100, last = 0.
   This makes ranks from a list of 5 comparable to ranks from a list of 20.
3. A restaurant's overall score is the **MEDIAN** of those percentiles (median,
   not mean — one outlier can't sink a consensus favorite).
4. Restaurants are ordered by that median → that ordering is the overall rank.
   **Coverage** = how many members ranked it.

An optional ``cap`` mirrors the movie project's list-size cap (Doyle @ 50); with
only a handful of restaurants it's unused, but kept for parity.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

import data_store as ds


def normalize_rank(rank: int, list_size: int) -> float:
    """Convert a 1-based rank to a 0-100 percentile. #1 = 100, last = 0.

    Copied verbatim from Movie Ranks ``LetterboxdRankings.normalize_rank``.
    """
    if list_size <= 1:
        return 100.0
    return 100.0 * (list_size - rank) / (list_size - 1)


def consensus(
    rankings_by_person: Dict[str, List[str]],
    min_coverage: int = 1,
    cap: Optional[int] = None,
) -> List[dict]:
    """Consensus ranking from per-member ordered lists.

    Port of Movie Ranks ``calculate``. ``rankings_by_person`` maps a member to
    their ordered list (index 0 = their #1). Returns dicts sorted by median
    percentile descending, each stamped with ``overall_rank``.
    """
    item_data: Dict[str, Dict[str, float]] = defaultdict(dict)
    for person, items in rankings_by_person.items():
        ranked = items[:cap] if cap else items
        size = len(ranked)
        for rank, item in enumerate(ranked, 1):
            item_data[item][person] = normalize_rank(rank, size)

    results: List[dict] = []
    for item, by_person in item_data.items():
        coverage = len(by_person)
        if coverage >= min_coverage:
            results.append({
                "restaurant": item,
                "coverage": coverage,
                "median": round(statistics.median(by_person.values()), 1),
                "ranked_by": list(by_person.keys()),
                "percentiles": {p: round(v, 1) for p, v in by_person.items()},
            })

    # Movie project sorts by median desc; we add coverage then name as stable
    # tiebreakers (ties are common with few restaurants).
    results.sort(key=lambda r: (-r["median"], -r["coverage"], r["restaurant"]))
    for i, r in enumerate(results, 1):
        r["overall_rank"] = i
    return results


def rankings_from_df(
    df: pd.DataFrame, raters: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """Build ``{member: [restaurants ordered #1 first]}`` from the CSV.

    Under the ranking model each per-member column holds that member's *rank*
    of the restaurant (1 = favorite, blank = not ranked). Sorting a member's
    non-blank rows by that value reconstructs their ordered list.
    """
    raters = raters or ds.RATERS
    out: Dict[str, List[str]] = {}
    for person in raters:
        if person not in df.columns:
            continue
        sub = df[pd.to_numeric(df[person], errors="coerce").notna()].copy()
        if sub.empty:
            continue
        sub[person] = pd.to_numeric(sub[person], errors="coerce")
        out[person] = sub.sort_values(person)["Restaurant"].tolist()
    return out


def consensus_table(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """``consensus()`` as a tidy DataFrame joined with each restaurant's country."""
    rows = consensus(rankings_from_df(df), **kwargs)
    if not rows:
        return pd.DataFrame(columns=["overall_rank", "restaurant", "country", "median", "coverage"])
    out = pd.DataFrame(rows)
    country = dict(zip(df["Restaurant"], df["Country"]))
    out["country"] = out["restaurant"].map(country)
    out["ranked_by"] = out["ranked_by"].map(lambda names: ", ".join(names))
    return out[["overall_rank", "restaurant", "country", "median", "coverage", "ranked_by"]]
