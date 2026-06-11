import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.channel_grouping import CHANNEL_COLORS


def render(data, filters):
    from utils.filters import apply_filters

    journeys = apply_filters(data["journeys_raw"], filters)

    if journeys.empty:
        st.warning("No data for selected filters.")
        return

    journeys = _add_position_bucket(journeys)

    _render_ai_referral_callout(journeys)

    st.subheader("Channel Grouping Journey")
    st.caption("How marketing channels connect across the customer journey. Each column is a touchpoint position. Wider flows = more journeys through that path. Colours match the source channel.")
    _render_sankey(journeys, "channel_grouping", CHANNEL_COLORS, threshold_pct=0.01)
    st.caption("All channels with first-touch, last-touch, and total touchpoint counts:")
    _render_detail_table(journeys, "channel_grouping", "Channel")

    st.divider()

    st.subheader("Source-Level Journey")
    st.caption("Same journey view at the source level (google, facebook, chatgpt.com etc.). Filter by channel to isolate referral partners or paid sources.")
    all_channels = sorted(journeys["channel_grouping"].unique())
    selected_channel = st.selectbox(
        "Filter by channel", ["All"] + all_channels, index=0
    )
    source_journeys = journeys
    if selected_channel != "All":
        filtered_jids = journeys[journeys["channel_grouping"] == selected_channel]["journey_id"].unique()
        source_journeys = journeys[journeys["journey_id"].isin(filtered_jids)]

    source_colors = _generate_source_colors(source_journeys["source"].unique())
    _render_sankey(source_journeys, "source", source_colors, threshold_pct=0.01)
    st.caption("All sources with attribution position breakdown:")
    _render_detail_table(source_journeys, "source", "Source")


def _add_position_bucket(journeys):
    df = journeys.copy()

    def _bucket(row):
        if row["touchpoint"] == 1:
            return 1
        if row["touchpoint"] == row["total_touchpoints"]:
            return 4
        if row["touchpoint"] == 2:
            return 2
        return 3

    df["position"] = df.apply(_bucket, axis=1)
    pos_labels = {1: "First", 2: "Second", 3: "Middle", 4: "Last"}
    df["position_label"] = df["position"].map(pos_labels)
    return df


def _render_ai_referral_callout(journeys):
    ai_sources = ["chatgpt.com", "perplexity.ai", "claude.ai", "gemini.google.com", "copilot.microsoft.com"]
    ai_journeys = journeys[journeys["source"].isin(ai_sources)]
    if ai_journeys.empty:
        return
    ai_unique = ai_journeys["journey_id"].nunique()
    total_unique = journeys["journey_id"].nunique()
    ai_pct = ai_unique / max(total_unique, 1) * 100
    if ai_pct >= 0.5:
        sources_list = ", ".join(sorted(ai_journeys["source"].unique()))
        st.info(f"AI Referrals: {ai_unique} journeys ({ai_pct:.1f}% of total) from {sources_list}")


def _render_sankey(journeys, dimension, color_map, threshold_pct=0.01):
    pivoted = journeys[journeys["position"].between(1, 4)].copy()

    total_touches = len(pivoted)
    value_counts = pivoted[dimension].value_counts()
    min_count = max(total_touches * threshold_pct, 1)
    top_values = value_counts[value_counts >= min_count].index.tolist()

    pivoted["dim_clean"] = pivoted[dimension].where(
        pivoted[dimension].isin(top_values),
        f"Other ({len(value_counts) - len(top_values)} sources)"
    )

    pivoted["node_id"] = pivoted["position"].astype(str) + "|" + pivoted["dim_clean"]

    links = []
    for _, group in pivoted.groupby("journey_id"):
        group = group.sort_values("position")
        group = group.drop_duplicates(subset=["position"], keep="first")
        ids = group["node_id"].tolist()
        for i in range(len(ids) - 1):
            links.append({"source": ids[i], "target": ids[i + 1], "value": 1})

    if not links:
        st.info("Not enough multi-touch journeys for Sankey.")
        return

    link_df = pd.DataFrame(links)
    link_agg = link_df.groupby(["source", "target"])["value"].sum().reset_index()
    min_threshold = max(5, link_agg["value"].quantile(0.10))
    link_agg = link_agg[link_agg["value"] >= min_threshold]

    if link_agg.empty:
        st.info("Not enough journey volume for Sankey at current filters.")
        return

    all_node_ids = sorted(
        set(link_agg["source"].tolist() + link_agg["target"].tolist()),
        key=lambda x: (int(x.split("|")[0]), x.split("|")[1]),
    )
    node_idx = {n: i for i, n in enumerate(all_node_ids)}
    node_labels = [n.split("|", 1)[1] for n in all_node_ids]
    node_colors = [color_map.get(label, "#bdc3c7") for label in node_labels]

    link_colors = []
    for _, row in link_agg.iterrows():
        source_label = row["source"].split("|", 1)[1]
        base = color_map.get(source_label, "#bdc3c7")
        r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
        link_colors.append(f"rgba({r},{g},{b},0.25)")

    pos_labels = {1: "First Touch", 2: "Second Touch", 3: "Middle Touches", 4: "Last Touch"}
    annotations = []
    for pos_num, header in pos_labels.items():
        pos_nodes = [nid for nid in all_node_ids if nid.startswith(f"{pos_num}|")]
        if pos_nodes:
            x_pos = (pos_num - 1) / 3
            annotations.append(dict(
                x=x_pos, y=1.06, xref="paper", yref="paper",
                text=f"<b>{header}</b>", showarrow=False,
                font=dict(size=12, color="#2c3e50"),
            ))

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=45,
            thickness=22,
            label=node_labels,
            color=node_colors,
            line=dict(width=0),
            hovertemplate="%{label}: %{value} journeys<extra></extra>",
        ),
        link=dict(
            source=[node_idx[s] for s in link_agg["source"]],
            target=[node_idx[t] for t in link_agg["target"]],
            value=link_agg["value"].tolist(),
            color=link_colors,
            hovertemplate="%{source.label} > %{target.label}: %{value}<extra></extra>",
        ),
        textfont=dict(size=11, color="#1a1a1a", family="Arial, Helvetica, sans-serif"),
    ))
    fig.update_layout(
        height=600,
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        annotations=annotations,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_detail_table(journeys, dimension, label):
    first_touch = journeys[journeys["position"] == 1]
    first_counts = first_touch[dimension].value_counts().reset_index()
    first_counts.columns = [label, "First Touch"]

    last_idx = journeys.groupby("journey_id")["touchpoint"].idxmax()
    last_touch = journeys.loc[last_idx]
    last_counts = last_touch[dimension].value_counts().reset_index()
    last_counts.columns = [label, "Last Touch"]

    all_counts = journeys[dimension].value_counts().reset_index()
    all_counts.columns = [label, "All Touchpoints"]

    unique_journeys = journeys.groupby(dimension)["journey_id"].nunique().reset_index()
    unique_journeys.columns = [label, "Unique Journeys"]

    table = first_counts.merge(last_counts, on=label, how="outer").merge(
        all_counts, on=label, how="outer"
    ).merge(unique_journeys, on=label, how="outer").fillna(0)

    for col in ["First Touch", "Last Touch", "All Touchpoints", "Unique Journeys"]:
        table[col] = table[col].astype(int)

    table = table.sort_values("Last Touch", ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True)


def _generate_source_colors(sources):
    base_palette = [
        "#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#34495e", "#d35400", "#c0392b",
        "#16a085", "#8e44ad", "#27ae60", "#2980b9", "#f1c40f",
    ]
    colors = {}
    for i, s in enumerate(sorted(sources)):
        colors[s] = base_palette[i % len(base_palette)]
    return colors
