"""Verify the Google Sheets backend end-to-end, without changing any data.

Usage (after setting AFRICAX_SA_JSON + AFRICAX_SHEET_URL, or a local secrets.toml):

    python verify_sheets.py

It confirms the backend is 'sheets', reads the data, and performs a safe
write-back round-trip (rewrites the SAME rows) so you know the service account has
Editor access. Exits non-zero on any problem.
"""
import sys

import data_store as ds


def main() -> int:
    print("backend:", ds.backend_name())
    if not ds.using_sheets():
        print("FAIL: Sheets not configured. Set AFRICAX_SA_JSON + AFRICAX_SHEET_URL "
              "(or add .streamlit/secrets.toml). See docs/SHEETS_SETUP.md.")
        return 1

    try:
        df = ds.load()
    except Exception as e:
        print(f"FAIL reading sheet: {type(e).__name__}: {e}")
        print("→ Did you share the Sheet with the service-account client_email as Editor?")
        return 1
    print(f"read OK: {len(df)} rows, {df['Status'].eq('visited').sum()} visited, "
          f"{df['Status'].eq('wishlist').sum()} wishlist")

    try:
        ds.save(df)  # rewrites the same rows — safe, proves write access
        after = ds.load()
    except Exception as e:
        print(f"FAIL writing sheet: {type(e).__name__}: {e}")
        return 1

    if len(after) == len(df):
        print(f"write round-trip OK: {len(after)} rows preserved")
        print("\nSHEETS BACKEND VERIFIED — rankings will persist.")
        return 0
    print(f"FAIL: row count changed on round-trip ({len(df)} -> {len(after)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
