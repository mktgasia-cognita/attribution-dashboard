import streamlit as st
import pandas as pd


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)
    spend_df = apply_filters(data["spend"], filters, apply_channel=False)
    search_df = data["search_terms"][data["search_terms"]["school"].isin(filters["schools"])]
    landing_df = data["landing_pages"][data["landing_pages"]["school"].isin(filters["schools"])]

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    campaign_perf = _build_campaign_performance(attr, spend_df)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("INCREASE - Scale These Campaigns")
        st.caption("Below-median CPA at below-median spend")
        has_conv = campaign_perf[campaign_perf["conversions"] > 0].sort_values("cpa")
        if len(has_conv) >= 4:
            increase = has_conv[
                (has_conv["cpa"] < has_conv["cpa"].median())
                & (has_conv["spend"] <= has_conv["spend"].median())
            ].head(10)
        else:
            mid = max(1, len(has_conv) // 2)
            increase = has_conv.head(mid)
        if increase.empty:
            st.info("No channels currently meet the scale criteria.")
        else:
            st.dataframe(_format_perf(increase), use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("DECREASE - Review These Campaigns")
        st.caption("High spend, low conversion, poor CPA")
        # Channels burning spend with zero attributed conversions are the
        # strongest decrease candidates - list them first (CPA shows N/A).
        zero_conv = campaign_perf[
            (campaign_perf["spend"] > 0) & (campaign_perf["conversions"] == 0)
        ].sort_values("spend", ascending=False)
        review_candidates = campaign_perf[campaign_perf["cpa"].notna()].sort_values("cpa", ascending=False)
        if len(review_candidates) >= 4:
            decrease = review_candidates[
                (review_candidates["cpa"] > review_candidates["cpa"].median())
                & (review_candidates["spend"] >= review_candidates["spend"].median())
            ]
        else:
            mid = max(1, len(review_candidates) // 2)
            decrease = review_candidates.head(mid)
        decrease = pd.concat([zero_conv, decrease]).head(10)
        if decrease.empty:
            st.info("No channels currently flagged for review.")
        else:
            st.dataframe(_format_perf(decrease), use_container_width=True, hide_index=True)

    st.divider()

    col_kw, col_content = st.columns(2)

    with col_kw:
        st.subheader("Keywords")
        st.caption("Full period - not affected by the date filter")
        kw_agg = search_df.groupby("keyword").agg(
            conversions=("conversions", "sum"),
            cost=("cost", "sum"),
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
        ).reset_index()
        kw_agg["cpa"] = kw_agg.apply(
            lambda r: r["cost"] / r["conversions"] if r["conversions"] > 0 else None, axis=1
        )
        kw_agg["ctr"] = kw_agg.apply(
            lambda r: round(r["clicks"] / r["impressions"] * 100, 1) if r["impressions"] > 0 else 0.0, axis=1
        )
        kw_agg = kw_agg.sort_values("conversions", ascending=False).head(20)
        kw_agg["cost"] = kw_agg["cost"].apply(lambda x: f"SGD {x:,.0f}")
        kw_agg["cpa"] = kw_agg["cpa"].apply(lambda x: f"SGD {x:,.0f}" if pd.notna(x) else "N/A")
        kw_agg = kw_agg[["keyword", "conversions", "cost", "clicks", "impressions", "ctr", "cpa"]]
        kw_agg.columns = ["Keyword", "Conversions", "Cost", "Clicks", "Impressions", "CTR %", "CPA"]
        st.dataframe(kw_agg, use_container_width=True, hide_index=True)

    with col_content:
        st.subheader("Top Content")
        st.caption("Full period - not affected by the date filter")
        landing_df = landing_df.copy()
        landing_df["landing_page"] = landing_df["landing_page"].fillna("(not set)")
        lp = landing_df.sort_values("conversions", ascending=False).head(15).copy()
        # Pipeline writes conversion_rate as a 0-1 ratio; the legacy manual
        # extract stored percentages. Normalise to percent for display.
        if not lp.empty and lp["conversion_rate"].max() <= 1:
            lp["conversion_rate"] = lp["conversion_rate"] * 100
        lp["conversion_rate"] = lp["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        lp = lp[["landing_page", "sessions", "conversions", "conversion_rate"]]
        lp.columns = ["Landing Page", "Sessions", "Conversions", "Conv Rate"]
        st.dataframe(lp, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Keyword x Content Combinations")
    st.caption("Full period - not affected by the date filter")
    combos = search_df.groupby(["keyword", "campaign"]).agg(
        cost=("cost", "sum"),
        conversions=("conversions", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    combos = combos[combos["conversions"] > 0].sort_values("conversions", ascending=False).head(20)
    combos["cost"] = combos["cost"].apply(lambda x: f"SGD {x:,.0f}")
    combos.columns = ["Keyword", "Campaign", "Cost", "Conversions", "Clicks"]
    st.dataframe(combos, use_container_width=True, hide_index=True)


def _build_campaign_performance(attr, spend_df):
    # Legacy manual-extract spend taxonomy. The BQ pipeline writes spend with
    # the same channel names as attribution, so translation is only needed
    # when the spend data still uses the old labels.
    ATTR_TO_SPEND = {
        "BrandedPaidSearch": "PaidSearch",
        "GenericPaidSearch": "PaidSearch",
        "CompetitorPaidSearch": "PaidSearch",
        "PMaxPaidSearch": "PMax",
        "PaidSocial": "PaidSocial",
    }
    spend_channels = set(spend_df["channel_grouping"].dropna().unique())
    taxonomies_aligned = bool(spend_channels & {
        "BrandedPaidSearch", "GenericPaidSearch", "PMaxPaidSearch", "CompetitorPaidSearch",
    })
    attr_digital = attr[~attr["channel_grouping"].isin(["Offline", "(Other)", "Direct"])]
    attr_digital = attr_digital.copy()
    if taxonomies_aligned:
        attr_digital["spend_channel"] = attr_digital["channel_grouping"]
    else:
        attr_digital["spend_channel"] = attr_digital["channel_grouping"].map(ATTR_TO_SPEND).fillna(attr_digital["channel_grouping"])
    conv = attr_digital[attr_digital["stage"] == "D1 Lead"].groupby("spend_channel")["attribution_weight"].sum().reset_index()
    conv.columns = ["channel_grouping", "conversions"]
    spend = spend_df.groupby("channel_grouping").agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    perf = spend.merge(conv, on="channel_grouping", how="left").fillna(0)
    perf["cpa"] = perf.apply(
        lambda r: r["spend"] / r["conversions"] if r["conversions"] > 0 else None, axis=1
    )
    # Share of our own impressions across channels - NOT auction
    # impression share from Google Ads.
    perf["impression_share"] = perf["impressions"] / max(perf["impressions"].sum(), 1) * 100
    return perf


def _format_perf(df):
    out = df[["channel_grouping", "spend", "conversions", "cpa", "impression_share"]].copy()
    out["spend"] = out["spend"].apply(lambda x: f"SGD {x:,.0f}")
    out["conversions"] = out["conversions"].apply(lambda x: f"{x:.2f}" if x < 1 else f"{x:.1f}")
    out["cpa"] = out["cpa"].apply(lambda x: f"SGD {x:,.0f}" if pd.notna(x) else "N/A")
    out["impression_share"] = out["impression_share"].apply(lambda x: f"{x:.1f}%")
    out.columns = ["Channel", "Spend", "Conversions", "CPA", "Share of Impressions"]
    return out
