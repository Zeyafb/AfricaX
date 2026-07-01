# AfricaX — Google Sheets persistence setup (~5 minutes)

The app saves to a **Google Sheet** when credentials are configured, and falls back
to the local CSV otherwise. This makes rankings entered on
https://africaxfoodmap.streamlit.app/ **persist** across Streamlit Cloud restarts.

You only do this once. The app **auto-seeds** the (empty) Sheet from the committed
`data/restaurants.csv` on first load, so you don't hand-copy any data.

## 1. Google Cloud: service account + APIs
1. Go to https://console.cloud.google.com/ and pick (or create) a project — you may
   still have **`africax-485504`** from before.
2. Enable both **Google Sheets API** and **Google Drive API** (APIs & Services →
   Library → search → Enable).
3. APIs & Services → **Credentials** → *Create credentials* → **Service account**.
   Name it e.g. `africax-writer`. (No roles needed.)
4. Open the service account → **Keys** → *Add key* → *Create new key* → **JSON** →
   Create. A `.json` file downloads. **Keep it private — never commit it.**
   > The old key was deleted for hygiene; if the old service account still exists,
   > either reuse it (new key) or delete it and make a fresh one.

## 2. Create the Sheet and share it
1. Create a new Google Sheet, e.g. **"AfricaX Data"**. Copy its URL.
2. Click **Share** and add the service account's email (the `client_email` in the
   JSON, like `africax-writer@africax-485504.iam.gserviceaccount.com`) as **Editor**.
   *(This is the step everyone forgets — without it the app gets a 403.)*

## 3. Tell Streamlit Cloud the secret
On https://share.streamlit.io → your app → **Settings → Secrets**, paste (fill from
the JSON — copy `private_key` verbatim, keeping the `\n`s):

```toml
[gcp_service_account]
type = "service_account"
project_id = "africax-485504"
private_key_id = "…"
private_key = "-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n"
client_email = "africax-writer@africax-485504.iam.gserviceaccount.com"
client_id = "…"
token_uri = "https://oauth2.googleapis.com/token"

[africax_sheet]
url = "https://docs.google.com/spreadsheets/d/XXXXXXXXXXXX/edit"
```

Save → the app reboots. The sidebar should now read **"💾 Saved to Google Sheets"**,
and the Sheet fills with the seed data on first load. Done — rankings now persist.

## 4. (Optional) Verify locally before trusting it
```bash
cd "D:\Claude Skills\AfricaX\AfricaX"
# point at your key + sheet (PowerShell: $env:AFRICAX_SA_JSON="C:\path\key.json")
export AFRICAX_SA_JSON="/c/path/to/key.json"
export AFRICAX_SHEET_URL="https://docs.google.com/spreadsheets/d/XXXX/edit"
python verify_sheets.py
```
It confirms the backend is `sheets`, reads the data, and does a safe write-back
round-trip (rewrites the same rows) so you know Editor access works.

## Notes
- `.streamlit/secrets.toml` and `*.json` are git-ignored — keep the key out of the repo.
- Concurrency: saves are whole-sheet writes (last-write-wins). For five friends
  ranking asynchronously this is fine; if two hit *Save* the same second, the later
  one wins — just re-save. A cell-level update is a future hardening if needed.
