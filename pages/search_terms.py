import streamlit as st
import pandas as pd


def render(data, filters):
    search_df = data["search_terms"]
    search_df = search_df[search_df["school"].isin(filters["schools"])]

    if search_df.empty:
        st.warning("No search term data for selected filters.")
        return

    st.subheader("Match Type Costs")
    match_agg = search_df.groupby("match_type").agg(
        cost=("cost", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    match_agg["cpc"] = (match_agg["cost"] / match_agg["clicks"].replace(0, 1)).round(2)
    match_agg["cost"] = match_agg["cost"].apply(lambda x: f"${x:,.0f}")
    match_agg["cpc"] = match_agg["cpc"].apply(lambda x: f"${x:.2f}")
    match_agg.columns = ["Match Type", "Cost", "Clicks", "Impressions", "CPC"]
    st.dataframe(match_agg, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Match Rate by Campaign")
    campaign_match = search_df.groupby(["match_type", "campaign"]).agg(
        search_terms=("search_term", "nunique"),
        keyword=("keyword", "first"),
        cost=("cost", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    campaign_match = campaign_match.sort_values("cost", ascending=False).head(30)
    campaign_match["cost"] = campaign_match["cost"].apply(lambda x: f"${x:,.0f}")
    campaign_match.columns = ["Match Type", "Campaign", "Search Terms", "Keyword", "Cost", "Clicks"]
    st.dataframe(campaign_match, use_container_width=True, hide_index=True)
