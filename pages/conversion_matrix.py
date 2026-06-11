import streamlit as st
import pandas as pd


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    sub_tab = st.radio(
        "View",
        ["Source/Medium/Campaign", "Over Time", "Placement (FB)", "Ad Name (FB)", "Ad Group (Google CPC)", "Ad Set (FB)"],
        horizontal=True,
    )

    stages = ["D1 Lead", "D2 Enquiry", "D3 Application", "D4 Offer", "D5 Enrolment"]

    if sub_tab == "Source/Medium/Campaign":
        _render_main_matrix(attr, stages)
    elif sub_tab == "Over Time":
        _render_over_time(attr, stages)
    else:
        _render_dimension_matrix(attr, stages, sub_tab)


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
        use_container_width=True,
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
            use_container_width=True,
        )


def _render_dimension_matrix(attr, stages, dimension_label):
    dimension_map = {
        "Placement (FB)": "Paid Social",
        "Ad Name (FB)": "Paid Social",
        "Ad Set (FB)": "Paid Social",
        "Ad Group (Google CPC)": "GenericPaidSearch",
    }
    channel_filter = dimension_map.get(dimension_label, "Paid Social")
    filtered = attr[attr["channel_grouping"] == channel_filter]

    if filtered.empty:
        st.info(f"No {channel_filter} data for selected filters.")
        return

    st.subheader(f"Attribution Matrix: {dimension_label}")
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
        use_container_width=True,
        height=500,
    )
