# AfricaX Guide

Streamlit app for logging African restaurant visits and ratings on a clickable Folium map.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Key Files

- `app.py`: Streamlit application.
- `data/restaurants.csv`: persistent visit data.
- `data/ne_110m_admin_0_countries.*`: map geometry data.

## Conventions

- Keep restaurant data in CSV format with existing headers.
- Use African countries only.
- Preserve per-person ratings and calculate group rating from available individual ratings.
- Do not commit or print service account JSON secrets.
