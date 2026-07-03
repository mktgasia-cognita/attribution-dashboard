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

    st.markdown("""<style>
    .kpi-grid { display: grid; gap: 12px; margin-bottom: 20px; }
    .kpi-grid-6 { grid-template-columns: repeat(6, 1fr); }
    .kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
    .kpi-sect { font-size: 14px; font-weight: 600; color: #31333F; margin: 0 0 8px; }
    .kpi-card { padding: 16px; border-radius: 8px; border: 1px solid rgba(0,0,0,0.06);
                box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .kpi-lbl { font-size: 13px; font-weight: 500; margin-bottom: 4px; opacity: 0.8; }
    .kpi-val { font-size: 24px; font-weight: 600; }
    @media (max-width: 768px) {
        .kpi-grid-6 { grid-template-columns: repeat(3, 1fr); }
        .kpi-grid-4 { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 480px) {
        .kpi-grid-6, .kpi-grid-4 { grid-template-columns: repeat(2, 1fr); }
        .kpi-val { font-size: 18px; }
        .kpi-lbl { font-size: 12px; }
    }
    </style>""", unsafe_allow_html=True)

    funnel = [
        ("Journeys", f"{unique_journeys:,}", "#E3EDF7", "#1a2a3a"),
        ("Leads", f"{total_leads:,.0f}", "#C3D8ED", "#1a2a3a"),
        ("Enquiries", f"{total_enquiries:,.0f}", "#8CB4DB", "#1e3a50"),
        ("Applications", f"{total_applications:,.0f}", "#5A91C4", "#ffffff"),
        ("Offers", f"{total_offers:,.0f}", "#3472A8", "#ffffff"),
        ("Enrolments", f"{total_enrolments:,.0f}", "#1A5276", "#ffffff"),
    ]
    cards = ""
    for lbl, val, bg, fg in funnel:
        cards += (
            f'<div class="kpi-card" style="background:{bg};color:{fg}">'
            f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div></div>'
        )
    st.markdown(
        f'<div class="kpi-sect">Funnel</div>'
        f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
        unsafe_allow_html=True,
    )

    spend_df = apply_filters(data["spend"], filters)
    if not spend_df.empty:
        total_spend = spend_df["spend"].sum()
        cpl = total_spend / total_leads if total_leads > 0 else 0
        cpen = total_spend / total_enquiries if total_enquiries > 0 else 0
        mer = (total_leads / total_spend * 1000) if total_spend > 0 else 0
        costs = [
            ("Spend (SGD)", f"${total_spend:,.0f}", ""),
            ("CPL (SGD)", f"${cpl:,.0f}" if total_leads > 0 else "N/A",
             "Cost Per Lead (total spend / leads)"),
            ("CPEn (SGD)", f"${cpen:,.0f}" if total_enquiries > 0 else "N/A",
             "Cost Per Enquiry (total spend / enquiries)"),
            ("MER", f"{mer:.1f}" if total_spend > 0 else "N/A",
             "Leads per SGD 1,000 spend"),
        ]
        cards = ""
        for lbl, val, tip in costs:
            title_attr = f' title="{tip}"' if tip else ""
            cards += (
                f'<div class="kpi-card" style="background:#f8f9fa;color:#1a2a3a"{title_attr}>'
                f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div></div>'
            )
        st.markdown(
            f'<div class="kpi-sect">Cost Efficiency</div>'
            f'<div class="kpi-grid kpi-grid-4">{cards}</div>',
            unsafe_allow_html=True,
        )

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
