import streamlit as st
import pandas as pd
from utils.currency import fmt
from utils.help import section_guide


def render(data, filters):
    search_df = data["search_terms"]
    search_df = search_df[search_df["school"].isin(filters["schools"])]

    if search_df.empty:
        st.warning("No search term data for selected filters.")
        return

    st.caption("Full period - not affected by the date filter")

    st.subheader("Match Type Costs")
    section_guide(
        "How closely a user's actual search matches your target keywords. "
        "<strong>Exact</strong> = precise match (e.g. 'international school singapore'). "
        "<strong>Phrase</strong> = contains your keywords in order. "
        "<strong>Broad</strong> = loosely related searches Google decides to show your ad for. "
        "Tighter match types usually cost more per click but convert better."
    )
    match_agg = search_df.groupby("match_type").agg(
        cost=("cost", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    match_agg["cpc"] = match_agg.apply(
        lambda r: round(r["cost"] / r["clicks"], 2) if r["clicks"] > 0 else None, axis=1
    )
    c = filters["currency"]
    match_agg["cost"] = match_agg["cost"].apply(lambda x: fmt(x, c))
    match_agg["cpc"] = match_agg["cpc"].apply(lambda x: fmt(x, c, decimals=2) if pd.notna(x) else "N/A")
    match_agg.columns = ["Match Type", "Cost", "Clicks", "Impressions", "CPC"]
    st.dataframe(match_agg, width="stretch", hide_index=True)

    st.divider()

    st.subheader("Match Rate by Campaign")
    section_guide(
        "How many different search queries triggered each campaign. "
        "A high <strong>Search Terms</strong> count on a broad match campaign may indicate "
        "wasted spend on irrelevant searches — review the actual search terms in Google Ads "
        "and add negative keywords for irrelevant queries."
    )
    campaign_match = search_df.groupby(["match_type", "campaign"]).agg(
        search_terms=("search_term", "nunique"),
        keyword=("keyword", "first"),
        cost=("cost", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    campaign_match = campaign_match.sort_values("cost", ascending=False).head(30)
    campaign_match["cost"] = campaign_match["cost"].apply(lambda x: fmt(x, c))
    campaign_match.columns = ["Match Type", "Campaign", "Search Terms", "Keyword", "Cost", "Clicks"]
    st.dataframe(campaign_match, width="stretch", hide_index=True)
