import streamlit as st
import pandas as pd


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)
    spend_df = apply_filters(data["spend"], filters)
    search_df = data["search_terms"]
    search_df = search_df[search_df["school"].isin(filters["schools"])]
    landing_df = data["landing_pages"]
    landing_df = landing_df[landing_df["school"].isin(filters["schools"])]

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    campaign_perf = _build_campaign_performance(attr, spend_df)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("INCREASE - Scale These Campaigns")
        st.caption("Low spend, high impression share, good CPA")
        increase = campaign_perf[
            (campaign_perf["cpa"] < campaign_perf["cpa"].median())
            & (campaign_perf["spend"] < campaign_perf["spend"].median())
            & (campaign_perf["conversions"] > 0)
        ].sort_values("cpa").head(10)
        st.dataframe(_format_perf(increase), use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("DECREASE - Review These Campaigns")
        st.caption("High spend, low conversion, poor CPA")
        decrease = campaign_perf[
            (campaign_perf["cpa"] > campaign_perf["cpa"].median())
            & (campaign_perf["spend"] > campaign_perf["spend"].median())
        ].sort_values("cpa", ascending=False).head(10)
        st.dataframe(_format_perf(decrease), use_container_width=True, hide_index=True)

    st.divider()

    col_kw, col_content = st.columns(2)

    with col_kw:
        st.subheader("Keywords")
        kw_agg = search_df.groupby("keyword").agg(
            conversions=("conversions", "sum"),
            cost=("cost", "sum"),
            clicks=("clicks", "sum"),
            avg_position=("avg_position", "mean"),
            quality_score=("quality_score", "mean"),
        ).reset_index()
        kw_agg["cpa"] = kw_agg["cost"] / kw_agg["conversions"].replace(0, 1)
        kw_agg = kw_agg.sort_values("conversions", ascending=False).head(20)
        kw_agg["avg_position"] = kw_agg["avg_position"].round(1)
        kw_agg["quality_score"] = kw_agg["quality_score"].round(0).astype(int)
        kw_agg["cost"] = kw_agg["cost"].apply(lambda x: f"${x:,.0f}")
        kw_agg["cpa"] = kw_agg["cpa"].apply(lambda x: f"${x:,.0f}")
        kw_agg.columns = ["Keyword", "Conversions", "Cost", "Clicks", "Avg Position", "Quality Score", "CPA"]
        st.dataframe(kw_agg, use_container_width=True, hide_index=True)

    with col_content:
        st.subheader("Top Content")
        lp = landing_df.sort_values("conversions", ascending=False).head(15).copy()
        lp["conversion_rate"] = lp["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        lp.columns = ["School", "Landing Page", "Sessions", "Conversions", "Conv Rate", "Bounce Rate", "Avg Duration"]
        st.dataframe(lp[["Landing Page", "Sessions", "Conversions", "Conv Rate"]], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Keyword x Content Combinations")
    combos = search_df.groupby(["keyword", "campaign"]).agg(
        cost=("cost", "sum"),
        conversions=("conversions", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    combos = combos[combos["conversions"] > 0].sort_values("conversions", ascending=False).head(20)
    combos["cost"] = combos["cost"].apply(lambda x: f"${x:,.0f}")
    combos.columns = ["Keyword", "Campaign", "Cost", "Conversions", "Clicks"]
    st.dataframe(combos, use_container_width=True, hide_index=True)


def _build_campaign_performance(attr, spend_df):
    conv = attr[attr["stage"] == "D1 Lead"].groupby("campaign")["attribution_weight"].sum().reset_index()
    conv.columns = ["campaign", "conversions"]
    spend = spend_df.groupby("campaign").agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    perf = spend.merge(conv, on="campaign", how="left").fillna(0)
    perf["cpa"] = perf["spend"] / perf["conversions"].replace(0, 1)
    perf["impression_share"] = perf["impressions"] / max(perf["impressions"].sum(), 1) * 100
    return perf


def _format_perf(df):
    out = df[["campaign", "spend", "conversions", "cpa", "impression_share"]].copy()
    out["spend"] = out["spend"].apply(lambda x: f"${x:,.0f}")
    out["conversions"] = out["conversions"].round(1)
    out["cpa"] = out["cpa"].apply(lambda x: f"${x:,.0f}")
    out["impression_share"] = out["impression_share"].apply(lambda x: f"{x:.1f}%")
    out.columns = ["Campaign", "Spend", "Conversions", "CPA", "Impression Share"]
    return out
