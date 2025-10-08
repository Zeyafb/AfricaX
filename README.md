# AfricaX 🍽️

AfricaX is a Streamlit-powered tasting passport that helps our crew track every African restaurant we visit in the DMV area. The app features an interactive Africa map, country highlights, and a filterable tasting log so we can celebrate where we've been and plan the next outing.

## Features

- **Africa choropleth** highlighting the countries represented in our tastings.
- **Interactive restaurant map** with hoverable ratings, notes, and visit dates.
- **Filter panel** to focus on specific countries, rating ranges, and visit windows.
- **Downloadable tasting log** so the crew can export the current data.

## Getting started

1. Create and activate a virtual environment (optional but recommended).
2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Launch the Streamlit app:

   ```bash
   streamlit run app.py
   ```

   The app will open in your browser at `http://localhost:8501`.

   Prefer running everything with a single Python command? Once dependencies are
   installed you can also start the dashboard with:

   ```bash
   python app.py
   ```

## Updating the tasting log

All restaurant visits live in [`data/restaurants.csv`](data/restaurants.csv). Add new rows with the country, ISO3 code, city, restaurant name, rating, visit date, notes, and coordinates. When the file updates, Streamlit reloads and displays the new spot immediately.

## Deploying

To share the experience with friends:

- Deploy to [Streamlit Community Cloud](https://streamlit.io/cloud) for a quick, free option.
- Or host it yourself and point a custom domain (e.g., via Netlify or Fly.io reverse proxy).

Make sure to keep your `requirements.txt` updated so the deployment environment has everything it needs.
