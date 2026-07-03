import streamlit as st
from datetime import datetime, timedelta


def render_sidebar(data):
    st.sidebar.header("Filters")

    schools = sorted(data["attributed"]["school"].unique()) if len(data["attributed"]) else ["BCS"]
    selected_schools = st.sidebar.multiselect("School", schools, default=schools)

    if len(data["attributed"]) and "date" in data["attributed"].columns:
        dates = data["attributed"]["date"].dropna()
        if len(dates):
            data_min = dates.min()
            data_max = dates.max()
            if hasattr(data_min, "date"):
                data_min = data_min.date()
                data_max = data_max.date()
            default_start = data_min
            default_end = data_max
            min_val = data_min
            max_val = data_max
        else:
            default_start = datetime(2026, 3, 13)
            default_end = datetime(2026, 6, 11)
            min_val = datetime(2026, 1, 1)
            max_val = datetime(2026, 6, 30)
    else:
        default_start = datetime(2026, 3, 13)
        default_end = datetime(2026, 6, 11)
        min_val = datetime(2026, 1, 1)
        max_val = datetime(2026, 6, 30)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start", value=default_start, min_value=min_val,
                                   max_value=max_val)
    with col2:
        end_date = st.date_input("End", value=default_end, min_value=min_val,
                                 max_value=max_val)

    channels = sorted(data["attributed"]["channel_grouping"].unique()) if len(data["attributed"]) else []
    selected_channels = st.sidebar.multiselect("Channel", channels, default=channels)

    return {
        "schools": selected_schools,
        "start_date": start_date,
        "end_date": end_date,
        "channels": selected_channels,
    }


def apply_filters(df, filters, date_col="date", apply_channel=True):
    mask = (
        df["school"].isin(filters["schools"])
        & (df[date_col] >= datetime.combine(filters["start_date"], datetime.min.time()))
        & (df[date_col] <= datetime.combine(filters["end_date"], datetime.max.time()))
    )
    if apply_channel and "channel_grouping" in df.columns:
        mask = mask & df["channel_grouping"].isin(filters["channels"])
    return df[mask].copy()
