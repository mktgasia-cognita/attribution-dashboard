import streamlit as st
import plotly.express as px
import pandas as pd


GRADE_SORT_ORDER = [
    "PreNursery", "Nursery", "Reception",
    "Year 1", "Year 2", "PCP - Year 2", "Year 3", "Year 4", "PCP - Year 4",
    "Year 5", "Year 6", "Year 7", "Year 8", "Year 9",
    "Year 10", "Year 11", "Year 12",
]


def _grade_sort_key(grade):
    try:
        return GRADE_SORT_ORDER.index(grade)
    except ValueError:
        return 999


def render(data, filters):
    from utils.filters import apply_filters

    journeys = apply_filters(data["journeys_raw"], filters)
    attr = apply_filters(data["attributed"], filters)

    if journeys.empty:
        st.warning("No data for selected filters.")
        return

    _render_coverage_metric(data, journeys)

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

    detail_cols = ["journey_id", "school", "date", "country", "max_stage", "status"]
    display_names = ["Journey ID", "School", "Date", "Country", "Stage", "Status"]

    if "applied_grade" in first_touches_detail.columns:
        detail_cols.extend(["applied_grade", "nationality", "admission_status"])
        display_names.extend(["Grade", "Nationality", "Adm. Status"])

    detail = first_touches_detail[detail_cols].merge(
        journey_detail, on="journey_id", how="left"
    )
    display_names.extend(["Source Path", "Medium Path", "Campaign Path"])
    detail = detail.sort_values("date", ascending=False).head(100)
    detail.columns = display_names
    if "Date" in detail.columns:
        detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    for col in ["Grade", "Nationality", "Adm. Status"]:
        if col in detail.columns:
            detail[col] = detail[col].fillna("")

    st.dataframe(detail, use_container_width=True, hide_index=True, height=400)

    _render_d365_enrichment(journeys, attr)


def _render_coverage_metric(data, journeys):
    d365_enr = data.get("d365_enrichment")
    if d365_enr is None or d365_enr.empty:
        return

    total_d365 = len(d365_enr)
    matched = d365_enr["journey_id"].isin(journeys["journey_id"].unique()).sum()
    pct = matched / total_d365 * 100 if total_d365 > 0 else 0

    st.info(
        f"D365 Attribution Coverage: **{matched}** of **{total_d365}** "
        f"D365 records matched to marketing journeys (**{pct:.0f}%**). "
        f"Unmatched records are offline leads or forms without GA tracking."
    )


def _render_d365_enrichment(journeys, attr):
    if "applied_grade" not in journeys.columns:
        return

    first_touches = journeys[journeys["touchpoint"] == 1].copy()
    enriched = first_touches.dropna(subset=["applied_grade"])

    if enriched.empty:
        return

    st.divider()
    st.subheader("Applicant Profile (D365-Attributed)")

    available_grades = sorted(enriched["applied_grade"].unique(), key=_grade_sort_key)
    available_years = sorted(enriched["academic_year"].dropna().unique())

    fc1, fc2 = st.columns(2)
    with fc1:
        selected_grades = st.multiselect(
            "Filter by Grade", available_grades, default=available_grades,
            key="d365_grade_filter"
        )
    with fc2:
        selected_years = st.multiselect(
            "Filter by Academic Year", available_years, default=available_years,
            key="d365_year_filter"
        )

    if selected_grades:
        enriched = enriched[enriched["applied_grade"].isin(selected_grades)]
    if selected_years:
        enriched = enriched[enriched["academic_year"].isin(selected_years)]

    if enriched.empty:
        st.warning("No records match the selected grade/year filters.")
        return

    row1_left, row1_right = st.columns(2)

    with row1_left:
        st.markdown("**Grade Distribution**")
        grade_counts = enriched["applied_grade"].value_counts().reset_index()
        grade_counts.columns = ["Grade", "Count"]
        grade_counts["sort_key"] = grade_counts["Grade"].apply(_grade_sort_key)
        grade_counts = grade_counts.sort_values("sort_key")
        fig = px.bar(
            grade_counts, x="Grade", y="Count",
            color_discrete_sequence=["#3498db"],
        )
        fig.update_layout(
            margin=dict(t=20, b=80, l=20, r=20),
            height=350,
            xaxis=dict(tickangle=-45, categoryorder="array", categoryarray=grade_counts["Grade"].tolist()),
        )
        st.plotly_chart(fig, use_container_width=True)

    with row1_right:
        st.markdown("**Admission Status**")
        status_counts = enriched["admission_status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        status_counts["sort_key"] = status_counts["Status"].apply(
            lambda x: int(x.split()[0]) if x.split()[0].isdigit() else 99
        )
        status_counts = status_counts.sort_values("sort_key")
        fig = px.bar(
            status_counts, x="Count", y="Status",
            orientation="h",
            color_discrete_sequence=["#2ecc71"],
        )
        fig.update_layout(
            margin=dict(t=20, b=20, l=100, r=20),
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Nationality Breakdown**")
    nat_counts = enriched["nationality"].value_counts().reset_index()
    nat_counts.columns = ["Nationality", "Count"]
    fig = px.pie(
        nat_counts, values="Count", names="Nationality", hole=0.3,
    )
    fig.update_traces(textposition="inside", textinfo="percent")
    fig.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="top", y=-0.1,
            x=0.5, xanchor="center", font=dict(size=11),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Grade x Channel**")
    enriched_attr = attr.dropna(subset=["applied_grade"])
    if selected_grades:
        enriched_attr = enriched_attr[enriched_attr["applied_grade"].isin(selected_grades)]
    if selected_years:
        enriched_attr = enriched_attr[enriched_attr["academic_year"].isin(selected_years)]

    if not enriched_attr.empty:
        grade_channel = pd.crosstab(
            enriched_attr["applied_grade"],
            enriched_attr["channel_grouping"],
            values=enriched_attr["attribution_weight"],
            aggfunc="sum",
        ).fillna(0).round(2)
        grade_channel["Total"] = grade_channel.sum(axis=1)
        grade_channel = grade_channel.reindex(
            sorted(grade_channel.index, key=_grade_sort_key)
        )
        st.dataframe(
            grade_channel.style.format("{:.2f}").background_gradient(cmap="Blues", axis=None),
            use_container_width=True,
        )
    else:
        st.info("No attributed data for the selected filters.")
