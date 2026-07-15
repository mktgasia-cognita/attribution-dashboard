import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def render_sidebar(data, role=None):
    st.sidebar.header("Filters")

    all_schools = sorted(data["attributed"]["school"].unique()) if len(data["attributed"]) else ["BCS"]

    if role and role.upper() in [s.upper() for s in all_schools]:
        selected_schools = [role.upper()]
        st.sidebar.info(f"School: {role.upper()}")
    else:
        selected_schools = st.sidebar.multiselect("School", all_schools, default=all_schools)

    all_dates = []
    school_start_dates = {}
    for key in ("attributed", "journeys_raw", "spend"):
        df = data.get(key)
        if df is not None and len(df) and "date" in df.columns:
            if "school" in df.columns:
                filtered = df[df["school"].isin(selected_schools)]
            else:
                filtered = df
            if len(filtered):
                all_dates.append(filtered["date"].dropna())
            if "school" in df.columns:
                for school, grp in df.groupby("school"):
                    d = grp["date"].dropna().min()
                    if pd.notna(d):
                        d = d.date() if hasattr(d, "date") else d
                        if school not in school_start_dates or d < school_start_dates[school]:
                            school_start_dates[school] = d

    if all_dates:
        combined = pd.concat(all_dates)
        data_min = combined.min()
        data_max = combined.max()
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

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start", value=default_start, min_value=min_val,
                                   max_value=max_val)
    with col2:
        end_date = st.date_input("End", value=default_end, min_value=min_val,
                                 max_value=max_val)

    for school in sorted(selected_schools):
        if school in school_start_dates:
            st.sidebar.caption(
                f"{school} data available from {school_start_dates[school].strftime('%d/%m/%Y')}"
            )

    channels = sorted(data["attributed"]["channel_grouping"].unique()) if len(data["attributed"]) else []
    selected_channels = st.sidebar.multiselect("Channel", channels, default=channels)

    from utils.currency import CURRENCIES
    currency = st.sidebar.selectbox("Display Currency", CURRENCIES, index=0)

    return {
        "schools": selected_schools,
        "start_date": start_date,
        "end_date": end_date,
        "channels": selected_channels,
        "currency": currency,
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
