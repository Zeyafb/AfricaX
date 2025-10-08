# AfricaX 🍽️ – Clickable Africa Map + Inline Logging

A Streamlit app with a Leaflet (Folium) Africa map. Click a country to view logged visits or add a new one. Data persists to `data/restaurants.csv`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
