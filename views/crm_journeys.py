import streamlit as st
import plotly.express as px
import pandas as pd


def render(data, filters):
    from utils.filters import apply_filters

    journeys = apply_filters(data["journeys_raw"], filters)
    attr = apply_filters(data["attributed"], filters)

    if journeys.empty:
        st.warning("No data for selected filters.")
        return

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Closed Reasons")
        lost = journeys[journeys["status"] == "Lost"].dropna(subset=["closed_reason"])
        if not lost.empty:
            reasons = lost["closed_reason"].value_counts().reset_index()
            reasons.columns = ["Reason", "Count"]
            fig = px.pie(reasons, values="Count", names="Reason", hole=0.3)
            fig.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, x=0.5, xanchor="center"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No lost journeys in selected range.")

    with col_right:
        st.subheader("Country x Stage Matrix")
        first_touches = journeys[journeys["touchpoint"] == 1].copy()
        first_touches["stage_status"] = first_touches["max_stage"] + " - " + first_touches["status"]

        matrix = pd.crosstab(first_touches["country"], first_touches["stage_status"])
        matrix["Total"] = matrix.sum(axis=1)
        matrix = matrix.sort_values("Total", ascending=False).head(15)

        desired_cols = []
        for stage in ["D1 Lead", "D2 Enquiry", "D3 Application", "D4 Offer", "D5 Enrolment"]:
            for status in ["Active", "Lost", "Won"]:
                col = f"{stage} - {status}"
                if col in matrix.columns:
                    desired_cols.append(col)
        desired_cols.append("Total")
        matrix = matrix.reindex(columns=[c for c in desired_cols if c in matrix.columns], fill_value=0)

        short_names = {
            "D1 Lead - Active": "D1 Act",
            "D1 Lead - Lost": "D1 Lost",
            "D1 Lead - Won": "D1 Won",
            "D2 Enquiry - Active": "D2 Act",
            "D2 Enquiry - Lost": "D2 Lost",
            "D2 Enquiry - Won": "D2 Won",
            "D3 Application - Active": "D3 Act",
            "D3 Application - Lost": "D3 Lost",
            "D3 Application - Won": "D3 Won",
            "D4 Offer - Active": "D4 Act",
            "D4 Offer - Lost": "D4 Lost",
            "D4 Offer - Won": "D4 Won",
            "D5 Enrolment - Active": "D5 Act",
            "D5 Enrolment - Lost": "D5 Lost",
            "D5 Enrolment - Won": "D5 Won",
        }
        matrix = matrix.rename(columns=short_names)

        st.dataframe(
            matrix.style.background_gradient(cmap="YlOrRd", axis=None),
            use_container_width=True,
            height=400,
        )

    st.divider()
    st.subheader("Journey Detail")
    first_touches_detail = journeys[journeys["touchpoint"] == 1].copy()
    journey_detail = journeys.groupby("journey_id").agg(
        source_path=("source", lambda x: " > ".join(x)),
        medium_path=("medium", lambda x: " > ".join(x)),
        campaign_path=("campaign", lambda x: " > ".join(x.unique())),
    ).reset_index()

    detail = first_touches_detail[["journey_id", "school", "date", "country", "max_stage", "status"]].merge(
        journey_detail, on="journey_id", how="left"
    )
    detail = detail.sort_values("date", ascending=False).head(100)
    detail.columns = ["Journey ID", "School", "Date", "Country", "Stage", "Status",
                       "Source Path", "Medium Path", "Campaign Path"]

    st.dataframe(detail, use_container_width=True, hide_index=True, height=400)
