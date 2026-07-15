import streamlit as st
import pandas as pd


DIMENSION_CONFIG = {
    "Ad Set (Meta)": {
        "channel_filter": ["PaidSocial"],
        "lookup_key": "meta_adset",
        "dimension_col": "ad_set_name",
        "platform": "meta",
    },
    "Ad Group (Google CPC)": {
        "channel_filter": ["PMaxPaidSearch", "BrandedPaidSearch", "GenericPaidSearch"],
        "lookup_key": "google_adgroup",
        "dimension_col": "ad_group_name",
        "platform": "google",
    },
    "Placement (Meta)": {
        "channel_filter": ["PaidSocial"],
        "lookup_key": None,
        "dimension_col": None,
        "platform": "meta",
    },
    "Ad Name (Meta)": {
        "channel_filter": ["PaidSocial"],
        "lookup_key": "meta_ad",
        "dimension_col": "ad_name",
        "platform": "meta",
    },
}


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)
    attr = attr[~attr["channel_grouping"].isin(["Offline", "(Other)"])]

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    sub_tab = st.radio(
        "View",
        ["Source/Medium/Campaign", "Over Time", "Ad Set (Meta)", "Ad Group (Google CPC)", "Placement (Meta)", "Ad Name (Meta)"],
        horizontal=True,
    )

    stages = ["D1 Lead", "D2 Enquiry", "D3 Application", "D4 Offer", "D5 Enrolment"]

    if sub_tab == "Source/Medium/Campaign":
        _render_main_matrix(attr, stages)
    elif sub_tab == "Over Time":
        _render_over_time(attr, stages)
    else:
        _render_dimension_matrix(attr, stages, sub_tab, data.get("ad_lookups", {}))


def _render_main_matrix(attr, stages):
    matrix = attr.pivot_table(
        index=["source", "medium", "campaign"],
        columns="stage",
        values="attribution_weight",
        aggfunc="sum",
        fill_value=0,
    ).reindex(columns=stages, fill_value=0)

    matrix = matrix.round(2)
    matrix["Total"] = matrix.sum(axis=1)
    matrix = matrix.sort_values("Total", ascending=False).head(50)

    st.subheader("Attribution Matrix: Source / Medium / Campaign")
    st.dataframe(
        matrix.style.format("{:.2f}").background_gradient(cmap="Blues", axis=None),
        width="stretch",
        height=600,
    )


def _render_over_time(attr, stages):
    attr_copy = attr.copy()
    attr_copy["month"] = attr_copy["date"].dt.to_period("M").astype(str)

    for stage in stages:
        st.subheader(stage)
        stage_data = attr_copy[attr_copy["stage"] == stage]
        monthly = stage_data.pivot_table(
            index=["source", "medium"],
            columns="month",
            values="attribution_weight",
            aggfunc="sum",
            fill_value=0,
        ).round(2)
        monthly["Total"] = monthly.sum(axis=1)
        monthly = monthly.sort_values("Total", ascending=False).head(20)
        st.dataframe(
            monthly.style.format("{:.2f}").background_gradient(cmap="Greens", axis=None),
            width="stretch",
        )


def _render_dimension_matrix(attr, stages, dimension_label, ad_lookups):
    config = DIMENSION_CONFIG[dimension_label]
    filtered = attr[attr["channel_grouping"].isin(config["channel_filter"])]

    if filtered.empty:
        st.info(f"No {'/'.join(config['channel_filter'])} data for selected filters.")
        return

    lookup_key = config["lookup_key"]
    dimension_col = config["dimension_col"]
    lookup_df = ad_lookups.get(lookup_key) if lookup_key else None
    name_map_df = ad_lookups.get("campaign_name_map")

    if lookup_df is None or dimension_col is None:
        st.subheader("Attribution Matrix: Campaign")
        st.caption(f"⚠️ {dimension_label} lookup data not available — showing campaign-level breakdown instead.")
        _fallback_campaign_matrix(filtered, stages)
        return

    st.subheader(f"Attribution Matrix: {dimension_label}")

    campaign_weights = filtered.groupby("campaign")["attribution_weight"].sum().reset_index()
    campaign_weights.columns = ["ga4_campaign", "attribution_weight"]

    if name_map_df is not None:
        platform_map = name_map_df[name_map_df["platform"] == config["platform"]]
        campaign_weights = campaign_weights.merge(
            platform_map[["ga4_campaign", "platform_campaign"]],
            on="ga4_campaign",
            how="left",
        )
        campaign_weights["platform_campaign"] = campaign_weights["platform_campaign"].fillna(
            campaign_weights["ga4_campaign"]
        )
    else:
        campaign_weights["platform_campaign"] = campaign_weights["ga4_campaign"]

    merged = campaign_weights.merge(
        lookup_df,
        left_on="platform_campaign",
        right_on="campaign_name",
        how="left",
    )

    matched = merged[merged["click_share"].notna()].copy()
    unmatched = merged[merged["click_share"].isna()]

    rows = []
    if not matched.empty:
        matched["distributed_weight"] = matched["attribution_weight"] * matched["click_share"]
        for _, row in matched.iterrows():
            rows.append({
                "dimension": row[dimension_col],
                "campaign": row["ga4_campaign"],
                "weight": row["distributed_weight"],
            })

    if not unmatched.empty:
        for _, row in unmatched.iterrows():
            rows.append({
                "dimension": f"[{row['ga4_campaign'][:40]}]",
                "campaign": row["ga4_campaign"],
                "weight": row["attribution_weight"],
            })

    if not rows:
        st.info("No matching data found.")
        return

    expanded = pd.DataFrame(rows)

    stage_weights = filtered.groupby(["campaign", "stage"])["attribution_weight"].sum().reset_index()
    stage_weights.columns = ["ga4_campaign", "stage", "stage_weight"]

    campaign_totals = stage_weights.groupby("ga4_campaign")["stage_weight"].sum().reset_index()
    campaign_totals.columns = ["ga4_campaign", "total_weight"]
    stage_weights = stage_weights.merge(campaign_totals, on="ga4_campaign")
    stage_weights["stage_share"] = stage_weights["stage_weight"] / stage_weights["total_weight"]

    dimension_rows = []
    for _, dim_row in expanded.iterrows():
        camp_stages = stage_weights[stage_weights["ga4_campaign"] == dim_row["campaign"]]
        for _, sr in camp_stages.iterrows():
            dimension_rows.append({
                "dimension": dim_row["dimension"],
                "stage": sr["stage"],
                "weight": dim_row["weight"] * sr["stage_share"],
            })

    if not dimension_rows:
        st.info("No stage data available.")
        return

    result_df = pd.DataFrame(dimension_rows)
    matrix = result_df.pivot_table(
        index="dimension",
        columns="stage",
        values="weight",
        aggfunc="sum",
        fill_value=0,
    ).reindex(columns=stages, fill_value=0).round(2)

    matrix["Total"] = matrix.sum(axis=1)
    matrix = matrix.sort_values("Total", ascending=False).head(30)

    st.dataframe(
        matrix.style.format("{:.2f}").background_gradient(cmap="Oranges", axis=None),
        width="stretch",
        height=500,
    )


def _fallback_campaign_matrix(filtered, stages):
    matrix = filtered.pivot_table(
        index=["campaign", "source"],
        columns="stage",
        values="attribution_weight",
        aggfunc="sum",
        fill_value=0,
    ).reindex(columns=stages, fill_value=0).round(2)

    matrix["Total"] = matrix.sum(axis=1)
    matrix = matrix.sort_values("Total", ascending=False).head(30)

    st.dataframe(
        matrix.style.format("{:.2f}").background_gradient(cmap="Oranges", axis=None),
        width="stretch",
        height=500,
    )
