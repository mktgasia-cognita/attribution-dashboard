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


def _channel_stage_table(attr):
    stages = [
        ("D1 Lead", "Leads"),
        ("D2 Enquiry", "Enquiries"),
        ("D5 Enrolment", "Enrolments"),
    ]
    table_attr = attr[~attr["channel_grouping"].isin(["Offline"])]
    channels = sorted(
        table_attr["channel_grouping"].dropna().unique()
    )
    if not channels:
        return

    rows = []
    for ch in channels:
        ch_data = table_attr[table_attr["channel_grouping"] == ch]
        leads = ch_data[ch_data["stage"] == "D1 Lead"]["attribution_weight"].sum()
        enqs = ch_data[ch_data["stage"] == "D2 Enquiry"]["attribution_weight"].sum()
        enrols = ch_data[ch_data["stage"] == "D5 Enrolment"]["attribution_weight"].sum()
        eq_rate = f"{enqs / leads * 100:.0f}%" if leads > 0 else "—"
        rows.append({"Channel": ch, "Leads": round(leads, 1), "Enquiries": round(enqs, 1),
                      "Enquiry Rate": eq_rate, "Enrolments": round(enrols, 1)})

    df = pd.DataFrame(rows).sort_values("Leads", ascending=False)
    total_leads = df["Leads"].sum()
    total_enqs = df["Enquiries"].sum()
    total_enrols = df["Enrolments"].sum()
    total_rate = f"{total_enqs / total_leads * 100:.0f}%" if total_leads > 0 else "—"
    totals = {"Channel": "Total", "Leads": total_leads, "Enquiries": total_enqs,
              "Enquiry Rate": total_rate, "Enrolments": total_enrols}
    df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


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
    webform_base = 0
    if not stitch.empty:
        if "school" in stitch.columns and filters.get("schools"):
            stitch = stitch[stitch["school"].isin(filters["schools"])]
        if "created_on" in stitch.columns:
            stitch = stitch.copy()
            stitch["created_on"] = pd.to_datetime(stitch["created_on"], errors="coerce", utc=True).dt.tz_localize(None)
            stitch = stitch[stitch["created_on"].notna()]
            stitch = stitch[
                (stitch["created_on"] >= pd.Timestamp(filters["start_date"]))
                & (stitch["created_on"] < pd.Timestamp(filters["end_date"]) + pd.Timedelta(days=1))
            ]
        stitch_total = len(stitch)
        has_entry_type = "entry_type" in stitch.columns
        if has_entry_type:
            webform_stitch = stitch[stitch["entry_type"] == "webform"]
            offline_attr = stitch[stitch["entry_type"] != "webform"]
        else:
            webform_stitch = stitch
            offline_attr = pd.DataFrame()
        full_attr = webform_stitch[webform_stitch["bq_sessions_found"] > 0]
        partial_attr = webform_stitch[
            (webform_stitch["bq_sessions_found"] == 0)
            & (~webform_stitch["first_touch_source"].isin(["(direct)", "(unknown)", "offline", ""]))
            & (webform_stitch["first_touch_source"].notna())
        ]
        unknown_attr = len(webform_stitch) - len(full_attr) - len(partial_attr)
        tracked_count = len(full_attr) + len(partial_attr)
        webform_base = len(webform_stitch)
        trackable_pct = (tracked_count / webform_base * 100) if webform_base > 0 else 0

        avg_days = None
        if "created_on" in stitch.columns and "first_touch_date" in stitch.columns:
            dated = full_attr.copy()
            dated["created_on"] = pd.to_datetime(dated["created_on"], errors="coerce", utc=True).dt.tz_localize(None)
            dated["first_touch_date"] = pd.to_datetime(dated["first_touch_date"], errors="coerce", utc=True).dt.tz_localize(None)
            valid = dated.dropna(subset=["created_on", "first_touch_date"])
            if not valid.empty:
                days_series = (valid["created_on"] - valid["first_touch_date"]).dt.days.clip(lower=0)
                avg_days = days_series.mean()

        days_str = f"{avg_days:.0f}" if avg_days is not None else "N/A"
        completeness = [
            ("Total Leads", f"{stitch_total:,}", "#f8f9fa", "#1a2a3a"),
            ("Full Attribution", f"{len(full_attr):,}", "#d4edda", "#155724"),
            ("Partial Attribution", f"{len(partial_attr):,}", "#fff3cd", "#856404"),
        ]
        if has_entry_type:
            completeness.append(("Offline", f"{len(offline_attr):,}", "#e8ecf0", "#4a5568"))
        completeness.append(("Unknown", f"{unknown_attr:,}", "#f8d7da", "#721c24"))

        grid_cols = len(completeness)
        cards = ""
        for lbl, val, bg, fg in completeness:
            cards += (
                f'<div class="kpi-card" style="background:{bg};color:{fg}">'
                f'<div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}</div></div>'
            )
        st.markdown(
            f'<div class="kpi-sect">How Complete Is Our Data?</div>'
            f'<div class="kpi-grid" style="grid-template-columns: repeat({grid_cols}, 1fr);">{cards}</div>',
            unsafe_allow_html=True,
        )
        if has_entry_type:
            section_guide(
                "<strong>Full Attribution</strong> = matched to GA4 sessions (multi-touch journey). "
                "<strong>Partial</strong> = UTM data but no session match (single-touch). "
                "<strong>Offline</strong> = phone, email, portal, or direct application leads — "
                "these never pass through a webform and cannot be digitally attributed. "
                "<strong>Unknown</strong> = webform leads with no digital signal (consent-blocked or cookie failure). "
                "<strong>Trackable %</strong> = Full + Partial as % of webform leads only."
            )
        else:
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
        st.caption(
            "Avg. Days to Lead = days between first tracked website visit and form submission "
            "(BQ-matched leads only). Cookie resets, browser switches, and private browsing mean "
            "the true consideration period is likely longer."
        )
        st.markdown("")

    # --- Lead Source Mix (CRM entry channels) ---
    crm_raw = data.get("crm_leads_raw", pd.DataFrame())
    if not crm_raw.empty:
        if "d365_id" in crm_raw.columns:
            crm_raw = crm_raw.drop_duplicates(subset=["d365_id"], keep="last")
        crm_filtered = crm_raw.copy()
        if "school" in crm_filtered.columns and filters.get("schools"):
            crm_filtered = crm_filtered[crm_filtered["school"].isin(filters["schools"])]
        if "created_on" in crm_filtered.columns:
            crm_filtered["created_on"] = pd.to_datetime(crm_filtered["created_on"], errors="coerce", utc=True).dt.tz_localize(None)
            crm_filtered = crm_filtered[crm_filtered["created_on"].notna()]
            crm_filtered = crm_filtered[
                (crm_filtered["created_on"] >= pd.Timestamp(filters["start_date"]))
                & (crm_filtered["created_on"] < pd.Timestamp(filters["end_date"]) + pd.Timedelta(days=1))
            ]
    else:
        crm_filtered = pd.DataFrame()

    if not crm_filtered.empty and "channel" in crm_filtered.columns:
        channel_counts = crm_filtered["channel"].fillna("Unknown").value_counts()
        crm_total_mix = len(crm_filtered)

        ENTRY_CHANNEL_COLORS = {
            "Webform": "#3472A8",
            "Email": "#E8A87C",
            "Direct Application": "#95B8D1",
            "Phone": "#B5CA8D",
            "Walk-in": "#D4A5A5",
            "Website": "#9CADCE",
            "Referral": "#C9B1D0",
            "Parent Application Portal": "#A8D5BA",
            "Sibling": "#D4C5A9",
            "Unknown": "#C4C4C4",
        }
        ordered = ["Webform", "Email", "Direct Application", "Phone",
                    "Walk-in", "Website", "Referral", "Parent Application Portal",
                    "Sibling"]
        labels_ordered = [ch for ch in ordered if ch in channel_counts.index]
        extras = [ch for ch in channel_counts.index if ch not in ordered]
        labels_ordered.extend(extras)

        fig_mix = go.Figure()
        for ch in labels_ordered:
            count = channel_counts[ch]
            pct = count / crm_total_mix * 100
            fig_mix.add_trace(go.Bar(
                y=[""],
                x=[count],
                name=ch,
                orientation="h",
                marker_color=ENTRY_CHANNEL_COLORS.get(ch, "#bdc3c7"),
                hovertemplate=f"<b>{ch}</b><br>{count:,} leads ({pct:.1f}%)<extra></extra>",
                text=f"{ch} ({pct:.0f}%)" if pct >= 5 else "",
                textposition="inside",
                textfont=dict(color="white" if ch == "Webform" else "#1a2a3a", size=12),
            ))

        webform_count = channel_counts.get("Webform", 0)
        webform_pct = webform_count / crm_total_mix * 100 if crm_total_mix > 0 else 0

        fig_mix.update_layout(
            barmode="stack",
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="left", x=0,
                        font=dict(size=11)),
            height=120,
            margin=dict(l=0, r=0, t=0, b=40),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )

        st.markdown(
            f'<div class="kpi-sect">Lead Source Mix ({crm_total_mix:,} leads)</div>',
            unsafe_allow_html=True,
        )
        section_guide(
            "How leads enter the CRM. <strong>Webform</strong> leads ({wf:,}, {pct:.0f}%) "
            "come through website forms and are the only leads that can be digitally "
            "attributed via the stitch pipeline and Markov model. "
            "All other channels (email, phone, portal, direct application) are recorded "
            "in the CRM but cannot be matched to website sessions.".format(
                wf=webform_count, pct=webform_pct
            )
        )
        st.plotly_chart(fig_mix, use_container_width=True, config={"displayModeBar": False})
        st.markdown("")

    # --- Enrolment Funnel ---
    has_crm_data = not stitch.empty and not crm_filtered.empty

    if has_crm_data:
        crm_raw = crm_filtered
        crm_total = len(crm_raw)

        st.markdown(
            f'<div class="kpi-sect">Enrolment Funnel (Markov-Attributed)</div>',
            unsafe_allow_html=True,
        )
        section_guide(
            "<strong>Leads</strong> shows digitally tracked ({trk:,}) vs CRM total ({crm:,}). "
            "The gap ({gap:,} leads) includes offline entries and webform leads with no digital signal. "
            "All stages show Markov-attributed totals — credit is split across channels, "
            "so values are fractional.".format(
                crm=crm_total, trk=tracked_count, gap=crm_total - tracked_count
            )
        )

        funnel = [
            ("Journeys", f"{webform_base:,}", "#E3EDF7", "#1a2a3a", None),
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
            f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
            unsafe_allow_html=True,
        )
    else:
        funnel = [
            ("Journeys", f"{webform_base:,}", "#E3EDF7", "#1a2a3a"),
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
            f'<div class="kpi-sect">Enrolment Funnel (Markov-Attributed)</div>'
            f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
            unsafe_allow_html=True,
        )
    # Channel attribution table
    section_guide(
        "Markov-attributed volume by channel for the selected date range. "
        "<strong>Enquiry Rate</strong> is a lead quality signal — the ratio of attributed enquiries "
        "to attributed leads per channel. It indicates how well each channel's leads progress, "
        "but is not a true conversion rate since attribution is assigned independently at each stage. "
        "<strong>Enrolments</strong> may appear low or zero — the lead-to-enrolment cycle is typically "
        "3+ months, so enrolment attribution requires data well beyond the selected date range."
    )
    _channel_stage_table(attr)

    st.divider()

    # Spend uses the ad-platform taxonomy, so it cannot follow the channel
    # filter. Showing filtered leads against unfiltered spend produces wrong
    # CPL/CPEn - hide the block instead when a channel filter is active.
    all_channels = set(data["attributed"]["channel_grouping"].dropna().unique())
    channel_filter_active = set(filters["channels"]) < all_channels

    spend_df = apply_filters(data["spend"], filters, apply_channel=False)
    if channel_filter_active:
        st.caption(
            "Cost Efficiency hidden while a channel filter is active: spend "
            "cannot be split by these channels, so CPL/CPEn/CPEnrol would divide "
            "filtered leads by total spend."
        )
    elif not spend_df.empty:
        total_spend = spend_df["spend"].sum()
        google_spend = spend_df[spend_df["platform"] == "google"]["spend"].sum() if "platform" in spend_df.columns else 0
        meta_spend = spend_df[spend_df["platform"] == "meta"]["spend"].sum() if "platform" in spend_df.columns else 0
        cpl = total_spend / total_leads if total_leads > 0 else 0
        cpen = total_spend / total_enquiries if total_enquiries > 0 else 0
        enrol_ps = attr[(attr["stage"] == "D5 Enrolment") & (attr["channel_grouping"] == "Paid Search")]["attribution_weight"].sum()
        enrol_psoc = attr[(attr["stage"] == "D5 Enrolment") & (attr["channel_grouping"] == "Paid Social")]["attribution_weight"].sum()
        cpenrol_google = google_spend / enrol_ps if enrol_ps > 0 and google_spend > 0 else 0
        cpenrol_meta = meta_spend / enrol_psoc if enrol_psoc > 0 and meta_spend > 0 else 0
        mer = (total_leads / total_spend * 1000) if total_spend > 0 else 0
        c = filters["currency"]

        section_guide(
            "How ad spend relates to lead volume and enrolments. Hover the ℹ icon on each card for its formula. "
            "These metrics show cost efficiency, but lower costs do not always mean better results — "
            "it depends on lead quality and campaign goals. "
            "CPEnrol is split by platform: Google Ads (Paid Search) and Meta Ads (Paid Social)."
        )

        costs = [
            ("Paid Ad Spend", fmt(total_spend, c), ""),
            ("CPL", fmt(cpl, c) if total_leads > 0 else "N/A",
             "Cost Per Lead — total ad spend divided by number of leads"),
            ("CPEn", fmt(cpen, c) if total_enquiries > 0 else "N/A",
             "Cost Per Enquiry — total ad spend divided by enquiries (further down the funnel than leads)"),
            ("CPEnrol Google", fmt(cpenrol_google, c) if cpenrol_google > 0 else "N/A",
             "Cost Per Enrolment — Google Ads spend divided by enrolments attributed to Paid Search"),
            ("CPEnrol Meta", fmt(cpenrol_meta, c) if cpenrol_meta > 0 else "N/A",
             "Cost Per Enrolment — Meta Ads spend divided by enrolments attributed to Paid Social"),
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
            f'<div class="kpi-grid kpi-grid-6">{cards}</div>',
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
        visible_leads = channel_attr["attribution_weight"].sum()
        excluded_leads = total_leads - visible_leads
        if excluded_leads > 0.5:
            st.caption(f"Webform leads only - excludes Offline ({excluded_leads:,.0f} of {total_leads:,.0f} leads)")
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
