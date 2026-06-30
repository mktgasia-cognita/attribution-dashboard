import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.channel_grouping import CHANNEL_COLORS

COUNTRY_SHORT_NAMES = {
    "Myanmar, Republic of the Union of": "Myanmar",
    "Korea, Republic of": "South Korea",
    "Taiwan, Province of China": "Taiwan",
    "Viet Nam": "Vietnam",
    "United States of America": "USA",
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
}


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)
    journeys = apply_filters(data["journeys_raw"], filters)

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    total_leads = attr[attr["stage"] == "D1 Lead"]["attribution_weight"].sum()
    total_enquiries = attr[attr["stage"] == "D2 Enquiry"]["attribution_weight"].sum()
    total_applications = attr[attr["stage"] == "D3 Application"]["attribution_weight"].sum()
    total_offers = attr[attr["stage"] == "D4 Offer"]["attribution_weight"].sum()
    total_enrolments = attr[attr["stage"] == "D5 Enrolment"]["attribution_weight"].sum()
    unique_journeys = journeys["journey_id"].nunique() if not journeys.empty else 0

    st.markdown("##### Funnel")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Journeys", f"{unique_journeys:,}")
    c2.metric("Leads", f"{total_leads:,.0f}")
    c3.metric("Enquiries", f"{total_enquiries:,.0f}")
    c4.metric("Applications", f"{total_applications:,.0f}")
    c5.metric("Offers", f"{total_offers:,.0f}")
    c6.metric("Enrolments", f"{total_enrolments:,.0f}")

    spend_df = data["spend"][data["spend"]["school"].isin(filters["schools"])]
    if not spend_df.empty:
        total_spend = spend_df["spend"].sum()
        cpl = total_spend / total_leads if total_leads > 0 else 0
        cpen = total_spend / total_enquiries if total_enquiries > 0 else 0
        mer = (total_leads / total_spend * 1000) if total_spend > 0 else 0
        st.markdown("##### Cost Efficiency")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Spend (SGD)", f"{total_spend:,.0f}")
        s2.metric("CPL (SGD)", f"{cpl:,.0f}" if total_leads > 0 else "N/A", help="Cost Per Lead (total spend / leads)")
        s3.metric("CPEn (SGD)", f"{cpen:,.0f}" if total_enquiries > 0 else "N/A", help="Cost Per Enquiry (total spend / enquiries)")
        s4.metric("MER", f"{mer:.1f}" if total_spend > 0 else "N/A", help="Leads per SGD 1,000 spend")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Attribution by Channel")
        lead_attr = attr[(attr["stage"] == "D1 Lead") & (~attr["channel_grouping"].isin(["Offline", "(Other)"]))]
        channel_attr = lead_attr.groupby("channel_grouping")["attribution_weight"].sum().reset_index()
        channel_attr = channel_attr.sort_values("attribution_weight", ascending=False)
        colors = [CHANNEL_COLORS.get(ch, "#bdc3c7") for ch in channel_attr["channel_grouping"]]
        short_labels = {
            "BrandedPaidSearch": "Branded",
            "GenericPaidSearch": "Generic",
            "CompetitorPaidSearch": "Competitor",
            "PMaxPaidSearch": "PMax",
            "OrganicSearch": "Organic",
            "PaidSocial": "Paid Social",
        }
        display_labels = [short_labels.get(ch, ch) for ch in channel_attr["channel_grouping"]]
        fig_donut = go.Figure(go.Pie(
            labels=display_labels,
            values=channel_attr["attribution_weight"],
            hole=0.5,
            marker=dict(colors=colors),
            textinfo="label+percent",
            textposition="outside",
        ))
        fig_donut.add_annotation(
            text=f"{total_leads:,.0f}<br>Leads",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#2c3e50"),
        )
        fig_donut.update_layout(
            showlegend=False,
            margin=dict(t=40, b=40, l=60, r=60),
            height=420,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        st.subheader("Leads Over Time")
        stages_of_interest = ["D1 Lead", "D2 Enquiry", "D3 Application", "D4 Offer", "D5 Enrolment"]
        leads_time = attr[attr["stage"].isin(stages_of_interest)].copy()
        leads_time["week"] = leads_time["date"].dt.to_period("W").apply(lambda x: x.start_time)
        weekly = leads_time.groupby(["week", "stage"])["attribution_weight"].sum().reset_index()

        stage_colors = {
            "D1 Lead": "#3498db", "D2 Enquiry": "#2ecc71", "D3 Application": "#f39c12",
            "D4 Offer": "#e74c3c", "D5 Enrolment": "#9b59b6",
        }
        fig_line = px.line(
            weekly, x="week", y="attribution_weight", color="stage",
            color_discrete_map=stage_colors,
            labels={"attribution_weight": "Attributed Conversions", "week": ""},
        )
        fig_line.update_layout(
            margin=dict(t=20, b=60, l=20, r=20),
            height=450,
            legend=dict(orientation="h", yanchor="top", y=-0.15, x=0.5, xanchor="center"),
            xaxis=dict(tickformat="%b %d", tickangle=-45),
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("Top Sources of Enquiries")
    d2_attr = attr[(attr["stage"] == "D2 Enquiry") & (~attr["channel_grouping"].isin(["Offline", "(Other)"]))]
    top_sources = d2_attr.groupby(["channel_grouping", "campaign"]).agg(
        attributed_conversions=("attribution_weight", "sum"),
    ).reset_index()
    top_sources = top_sources.sort_values("attributed_conversions", ascending=False).head(20)
    top_sources["attributed_conversions"] = top_sources["attributed_conversions"].round(2)
    top_sources.columns = ["Channel", "Campaign", "Attributed Conversions"]
    st.dataframe(top_sources, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Country Distribution")
    if not journeys.empty:
        first_touches = journeys[journeys["touchpoint"] == 1]
        country_counts = first_touches["country"].value_counts().reset_index()
        country_counts.columns = ["Country", "Leads"]
        country_counts["Country"] = country_counts["Country"].map(
            lambda x: COUNTRY_SHORT_NAMES.get(x, x)
        )
        fig_bar = px.bar(
            country_counts, x="Country", y="Leads",
            color_discrete_sequence=["#3498db"],
        )
        fig_bar.update_layout(
            margin=dict(t=20, b=60, l=20, r=20),
            height=350,
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig_bar, use_container_width=True)
