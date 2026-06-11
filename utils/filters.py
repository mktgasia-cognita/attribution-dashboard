import streamlit as st
from datetime import datetime, timedelta


def render_sidebar(data):
    st.sidebar.header("Filters")

    schools = sorted(data["attributed"]["school"].unique())
    selected_schools = st.sidebar.multiselect("School", schools, default=schools)

    default_start = datetime(2026, 3, 13)
    default_end = datetime(2026, 6, 11)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start", value=default_start, min_value=datetime(2026, 1, 1),
                                   max_value=datetime(2026, 6, 30))
    with col2:
        end_date = st.date_input("End", value=default_end, min_value=datetime(2026, 1, 1),
                                 max_value=datetime(2026, 6, 30))

    channels = sorted(data["attributed"]["channel_grouping"].unique())
    selected_channels = st.sidebar.multiselect("Channel", channels, default=channels)

    return {
        "schools": selected_schools,
        "start_date": start_date,
        "end_date": end_date,
        "channels": selected_channels,
    }


def apply_filters(df, filters, date_col="date"):
    mask = (
        df["school"].isin(filters["schools"])
        & (df[date_col] >= datetime.combine(filters["start_date"], datetime.min.time()))
        & (df[date_col] <= datetime.combine(filters["end_date"], datetime.max.time()))
    )
    if "channel_grouping" in df.columns:
        mask = mask & df["channel_grouping"].isin(filters["channels"])
    return df[mask].copy()
