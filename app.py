from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "restaurants.csv"

st.set_page_config(
    page_title="AfricaX Restaurant Tracker",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data
def load_restaurants() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["Visit Date"])
    df.sort_values("Visit Date", ascending=False, inplace=True)
    return df


def compute_country_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["Country", "ISO_A3"], as_index=False)
        .agg(
            Visits=("Restaurant", "count"),
            Average_Rating=("Rating", "mean"),
            Latest_Visit=("Visit Date", "max"),
        )
        .sort_values("Visits", ascending=False)
    )
    summary["Average_Rating"] = summary["Average_Rating"].round(2)
    return summary


def africa_choropleth(summary: pd.DataFrame):
    fig = px.choropleth(
        summary,
        locations="ISO_A3",
        color="Visits",
        hover_name="Country",
        hover_data={
            "Visits": True,
            "Average_Rating": True,
            "Latest_Visit": summary["Latest_Visit"].dt.strftime("%b %d, %Y"),
            "ISO_A3": False,
        },
        color_continuous_scale="YlOrRd",
        scope="africa",
        title="Countries we've tasted",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    return fig


def africa_restaurant_map(df: pd.DataFrame):
    fig = px.scatter_geo(
        df,
        lat="Latitude",
        lon="Longitude",
        color="Rating",
        size="Rating",
        size_max=18,
        hover_name="Restaurant",
        hover_data={
            "Country": True,
            "City": True,
            "Rating": True,
            "Visit Date": df["Visit Date"].dt.strftime("%b %d, %Y"),
            "Latitude": False,
            "Longitude": False,
        },
        color_continuous_scale="deep",
        range_color=(3.5, 5),
        projection="natural earth",
        scope="africa",
        title="Restaurant stops",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    return fig


def main():
    df = load_restaurants()
    summary = compute_country_summary(df)

    st.title("🍽️ AfricaX – African Restaurant Passport")
    st.markdown(
        """
        Track your journey as you taste your way across the African continent—one local spot at a time.
        Filter by country, rating, or visit date to explore highlights from your adventures and plan where to go next.
        """
    )

    with st.sidebar:
        st.header("Filter your journey")
        countries = st.multiselect(
            "Countries", options=sorted(df["Country"].unique()), default=sorted(df["Country"].unique())
        )
        min_rating, max_rating = float(df["Rating"].min()), float(df["Rating"].max())
        rating_range = st.slider(
            "Rating", min_value=1.0, max_value=5.0, value=(min_rating, max_rating), step=0.1
        )
        min_date, max_date = df["Visit Date"].min(), df["Visit Date"].max()
        visit_range = st.date_input(
            "Visit window",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        search_text = st.text_input("Search restaurants or notes")
        st.info(
            "Use the filters above to focus on the next country you want to explore or to revisit favorites."
        )

    filtered = df[df["Country"].isin(countries)]
    filtered = filtered[(filtered["Rating"] >= rating_range[0]) & (filtered["Rating"] <= rating_range[1])]
    filtered = filtered[
        (filtered["Visit Date"] >= pd.to_datetime(visit_range[0]))
        & (filtered["Visit Date"] <= pd.to_datetime(visit_range[1]))
    ]
    if search_text:
        mask = filtered.apply(lambda row: search_text.lower() in row.to_string().lower(), axis=1)
        filtered = filtered[mask]

    st.subheader("Where have we been?")
    st.plotly_chart(africa_choropleth(summary), use_container_width=True)

    st.subheader("Restaurant map")
    st.plotly_chart(africa_restaurant_map(filtered), use_container_width=True)

    st.subheader("Tasting log")
    st.dataframe(
        filtered.assign(**{"Visit Date": filtered["Visit Date"].dt.strftime("%b %d, %Y")})[
            ["Visit Date", "Country", "City", "Restaurant", "Rating", "Notes"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("### Add your next spot")
    st.markdown(
        """
        Ready to log another outing? Update `data/restaurants.csv` with the new country, restaurant, and coordinates.
        Streamlit automatically reloads the data when the file changes, so you'll see the new pin on the map instantly when the app reruns.
        """
    )

    st.markdown("#### Export your data")
    st.download_button(
        label="Download tasting log (CSV)",
        data=df.to_csv(index=False),
        file_name="africax_restaurants.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
