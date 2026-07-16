import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.channel_grouping import CHANNEL_COLORS
from utils.currency import fmt
from utils.help import section_guide, info_icon

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

    # --- Data Completeness Section ---
    stitch = data.get("stitch_audit", pd.DataFrame())
    tracked_count = 0
    if not stitch.empty:
        if "school" in filters and filters.get("schools"):
            stitch = stitch[stitch["school"].isin(filters["schools"])]
        stitch_total = len(stitch)
        full_attr = stitch[stitch["bq_sessions_found"] > 0]
        partial_attr = stitch[
            (stitch["bq_sessions_found"] == 0)
            & (~stitch["first_touch_source"].isin(["(direct)", "offline", ""]))
            & (stitch["first_touch_source"].notna())
        ]
        unknown_attr = stitch_total - len(full_attr) - len(partial_attr)
        tracked_count = len(full_attr) + len(partial_attr)
        trackable_pct = (tracked_count / stitch_total * 100) if stitch_total > 0 else 0

        avg_days = None
        if "created_on" in stitch.columns and "first_touch_date" in stitch.columns:
            dated = full_attr.copy()
            dated["created_on"] = pd.to_datetime(dated["created_on"], errors="coerce")
            dated["first_touch_date"] = pd.to_datetime(dated["first_touch_date"], errors="coerce")
            valid = dated.dropna(subset=["created_on", "first_touch_date"])
            if not valid.empty:
                avg_days = (valid["created_on"] - valid["first_touch_date"]).dt.days.mean()

        days_str = f"{avg_days:.0f}" if avg_days is not None else "N/A"
        completeness = [
            ("Total Leads", f"{stitch_total:,}", "#f8f9fa", "#1a2a3a"),
            ("Full Attribution", f"{len(full_attr):,}", "#d4edda", "#155724"),
            ("Partial Attribution", f"{len(partial_attr):,}", "#fff3cd", "#856404"),
            ("Unknown Attribution", f"{unknown_attr:,}", "#f8d7da", "#721c24"),
        ]
        cards = ""
        for lbl, val, bg, fg in completeness:
            cards += (
                f'<div class="kpi-card" style="background:{bg};color:{fg}">'
                f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div></div>'
            )
        st.markdown(
            f'<div class="kpi-sect">How Complete Is Our Data?</div>'
            f'<div class="kpi-grid kpi-grid-4">{cards}</div>',
            unsafe_allow_html=True,
        )
        section_guide(
            "<strong>Full Attribution</strong> = visitor matched to GA4 sessions (multi-touch journey). "
            "<strong>Partial</strong> = UTM data but no session match (single-touch). "
            "<strong>Unknown</strong> = no digital signal, defaults to Direct. "
            "<strong>Trackable %</strong> = Full + Partial as % of total."
        )
        summary = [
            ("Trackable Journeys", f"{trackable_pct:.0f}%", "#f8f9fa", "#1a2a3a"),
            ("Avg. Days to Lead", days_str, "#f8f9fa", "#1a2a3a"),
        ]
        cards = ""
        for lbl, val, bg, fg in summary:
            cards += (
                f'<div class="kpi-card" style="background:{bg};color:{fg}">'
                f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div></div>'
            )
        st.markdown(
            f'<div class="kpi-grid" style="grid-template-columns: repeat(2, 1fr); max-width: 400px;">{cards}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    # --- Enrolment Funnel ---
    crm_raw = data.get("crm_leads_raw", pd.DataFrame())
    has_crm_data = not stitch.empty and not crm_raw.empty

    if has_crm_data:
        if "school" in filters and filters.get("schools"):
            crm_raw = crm_raw[crm_raw["school"].isin(filters["schools"])]
        crm_total = len(crm_raw)

        section_guide(
            "<strong>Leads</strong> shows CRM total ({crm:,}) vs digitally tracked ({trk:,}). "
            "The gap ({gap:,} leads) reflects visitors without digital tracking. "
            "Other funnel stages show attributed totals only.".format(
                crm=crm_total, trk=tracked_count, gap=crm_total - tracked_count
            )
        )

        funnel = [
            ("Journeys", f"{unique_journeys:,}", "#E3EDF7", "#1a2a3a", None),
            ("Leads", f"{tracked_count:,}", "#C3D8ED", "#1a2a3a", f"CRM: {crm_total:,}"),
            ("Enquiries", f"{total_enquiries:,.0f}", "#8CB4DB", "#1e3a50", None),
            ("Applications", f"{total_applications:,.0f}", "#5A91C4", "#ffffff", None),
            ("Offers", f"{total_offers:,.0f}", "#3472A8", "#ffffff", None),
            ("Enrolments", f"{total_enrolments:,.0f}", "#1A5276", "#ffffff", None),
        ]
        cards = ""
        for lbl, val, bg, fg, subtitle in funnel:
            sub_html = f'<div style="font-size:11px;opacity:0.7;margin-top:2px">{subtitle}</div>' if subtitle else ""
            cards += (
                f'<div class="kpi-card" style="background:{bg};color:{fg}">'
                f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div>{sub_html}</div>'
            )
        st.markdown(
            f'<div class="kpi-sect">Enrolment Funnel</div>'
            f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
            unsafe_allow_html=True,
        )
    else:
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
            f'<div class="kpi-sect">Enrolment Funnel</div>'
            f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
            unsafe_allow_html=True,
        )

    # Spend uses the ad-platform taxonomy, so it cannot follow the channel
    # filter. Showing filtered leads against unfiltered spend produces wrong
    # CPL/CPEn - hide the block instead when a channel filter is active.
    all_channels = set(data["attributed"]["channel_grouping"].dropna().unique())
    channel_filter_active = set(filters["channels"]) < all_channels

    spend_df = apply_filters(data["spend"], filters, apply_channel=False)
    if channel_filter_active:
        st.caption(
            "Cost Efficiency hidden while a channel filter is active: spend "
            "cannot be split by these channels, so CPL/CPEn would divide "
            "filtered leads by total spend."
        )
    elif not spend_df.empty:
        total_spend = spend_df["spend"].sum()
        cpl = total_spend / total_leads if total_leads > 0 else 0
        cpen = total_spend / total_enquiries if total_enquiries > 0 else 0
        mer = (total_leads / total_spend * 1000) if total_spend > 0 else 0
        c = filters["currency"]

        section_guide(
            "How ad spend relates to lead volume. Hover the ℹ icon on each card for its formula. "
            "These metrics show cost efficiency, but a low CPL does not always mean better results — "
            "it depends on lead quality and campaign goals. "
            "All metrics use combined spend across Google Ads and Meta Ads."
        )

        costs = [
            ("Spend", fmt(total_spend, c), ""),
            ("CPL", fmt(cpl, c) if total_leads > 0 else "N/A",
             "Cost Per Lead — total ad spend divided by number of leads"),
            ("CPEn", fmt(cpen, c) if total_enquiries > 0 else "N/A",
             "Cost Per Enquiry — total ad spend divided by enquiries (further down the funnel than leads)"),
            (f"Leads/{c} 1k", f"{mer:.1f}" if total_spend > 0 else "N/A",
             f"How many leads generated per {c} 1,000 spent"),
        ]
        cards = ""
        for lbl, val, tip in costs:
            icon = info_icon(tip) if tip else ""
            cards += (
                f'<div class="kpi-card" style="background:#f8f9fa;color:#1a2a3a">'
                f'<div class="kpi-lbl">{lbl}{icon}</div><div class="kpi-val">{val}</div></div>'
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
        section_guide(
            "Which marketing channels are driving leads. Credit is split across "
            "channels using <strong>Markov attribution</strong> — a model that measures "
            "each channel's actual contribution to conversions, rather than giving "
            "all credit to the last click."
        )
        lead_attr = attr[(attr["stage"] == "D1 Lead") & (~attr["channel_grouping"].isin(["Offline", "(Other)"]))]
        channel_attr = lead_attr.groupby("channel_grouping")["attribution_weight"].sum().reset_index()
        channel_attr = channel_attr.sort_values("attribution_weight", ascending=False)
        # Centre count and percentages must share the same base as the
        # visible slices - Offline/(Other) are excluded above.
        visible_leads = channel_attr["attribution_weight"].sum()
        excluded_leads = total_leads - visible_leads
        if excluded_leads > 0.5:
            st.caption(f"Digital channels only - excludes Offline/(Other) ({excluded_leads:,.0f} of {total_leads:,.0f} leads)")
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
            text=f"{visible_leads:,.0f}<br>Leads",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#2c3e50"),
        )
        fig_donut.update_layout(
            showlegend=False,
            margin=dict(t=40, b=40, l=60, r=60),
            height=420,
        )
        st.plotly_chart(fig_donut, width="stretch")

    with col_right:
        st.subheader("Leads Over Time")
        section_guide(
            "Weekly trend of new prospects at each pipeline stage. "
            "Look for spikes (campaign launches, events) and dips (holidays, budget pauses). "
            "All lines rising together suggests healthy pipeline flow."
        )
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
        st.plotly_chart(fig_line, width="stretch")

    st.subheader("Top Sources of Enquiries")
    section_guide(
        "Campaigns ranked by their contribution to enquiries (not just leads). "
        "Decimal values (e.g. 2.50) mean credit is shared — this campaign contributed "
        "to 2-3 enquiries but shares credit with other channels those prospects also interacted with."
    )
    d2_attr = attr[(attr["stage"] == "D2 Enquiry") & (~attr["channel_grouping"].isin(["Offline", "(Other)"]))]
    top_sources = d2_attr.groupby(["channel_grouping", "campaign"]).agg(
        attributed_conversions=("attribution_weight", "sum"),
    ).reset_index()
    top_sources = top_sources.sort_values("attributed_conversions", ascending=False).head(20)
    top_sources["attributed_conversions"] = top_sources["attributed_conversions"].round(2)
    top_sources.columns = ["Channel", "Campaign", "Attributed Conversions"]
    st.dataframe(top_sources, width="stretch", hide_index=True)

    st.divider()

    st.subheader("Country Distribution")
    section_guide(
        "Based on the country detected in the visitor's first website session. "
        "Helps identify which markets are generating the most interest."
    )
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
        st.plotly_chart(fig_bar, width="stretch")
