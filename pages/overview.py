import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.channel_grouping import CHANNEL_COLORS


def render(data, filters):
    from utils.filters import apply_filters

    attr = apply_filters(data["attributed"], filters)
    spend_df = apply_filters(data["spend"], filters)

    if attr.empty:
        st.warning("No data for selected filters.")
        return

    # KPI cards
    total_conversions = attr[attr["stage"] == "D1 Lead"]["attribution_weight"].sum()
    total_investment = spend_df["spend"].sum()
    overall_cpa = total_investment / max(total_conversions, 1)
    d5_conversions = attr[attr["stage"] == "D5 Enrolment"]["attribution_weight"].sum()
    cost_per_joiner = total_investment / max(d5_conversions, 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Attributed Conversions", f"{total_conversions:,.0f}")
    c2.metric("Total Investment", f"${total_investment:,.0f}")
    c3.metric("Overall CPA", f"${overall_cpa:,.0f}")
    c4.metric("Cost per Joiner", f"${cost_per_joiner:,.0f}")

    st.divider()

    # Charts row
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Investment by Channel")
        channel_spend = spend_df.groupby("channel_grouping")["spend"].sum().reset_index()
        channel_spend = channel_spend.sort_values("spend", ascending=False)
        colors = [CHANNEL_COLORS.get(ch, "#bdc3c7") for ch in channel_spend["channel_grouping"]]
        short_labels = {
            "BrandedPaidSearch": "Branded",
            "GenericPaidSearch": "Generic",
            "CompetitorPaidSearch": "Competitor",
            "PMaxPaidSearch": "PMax",
            "Organic Search": "Organic",
            "Paid Social": "Paid Social",
        }
        display_labels = [short_labels.get(ch, ch) for ch in channel_spend["channel_grouping"]]
        fig_donut = go.Figure(go.Pie(
            labels=display_labels,
            values=channel_spend["spend"],
            hole=0.5,
            marker=dict(colors=colors),
            textinfo="label+percent",
            textposition="outside",
        ))
        fig_donut.add_annotation(
            text=f"${total_investment:,.0f}",
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

    # Top Sources table
    st.subheader("Top Sources of Enquiries")
    d2_attr = attr[attr["stage"] == "D2 Enquiry"]
    top_sources = d2_attr.groupby(["channel_grouping", "campaign"]).agg(
        attributed_conversions=("attribution_weight", "sum"),
    ).reset_index()

    spend_by_campaign = spend_df.groupby(["channel_grouping", "campaign"])["spend"].sum().reset_index()
    top_sources = top_sources.merge(spend_by_campaign, on=["channel_grouping", "campaign"], how="left").fillna(0)
    top_sources["attributed_cpa"] = top_sources["spend"] / top_sources["attributed_conversions"].replace(0, 1)
    top_sources = top_sources.sort_values("attributed_conversions", ascending=False).head(20)

    top_sources.columns = ["Channel", "Campaign", "Attributed Conversions", "Spend", "Attributed CPA"]
    top_sources["Attributed Conversions"] = top_sources["Attributed Conversions"].round(1)
    top_sources["Spend"] = top_sources["Spend"].apply(lambda x: f"${x:,.0f}")
    top_sources["Attributed CPA"] = top_sources["Attributed CPA"].apply(lambda x: f"${x:,.0f}")

    st.dataframe(top_sources, use_container_width=True, hide_index=True)
