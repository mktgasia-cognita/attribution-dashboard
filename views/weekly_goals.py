import streamlit as st
import pandas as pd
from utils.currency import fmt


def render(data, filters):
    from datetime import datetime

    goals = data["weekly_goals"]
    goals = goals[goals["school"].isin(filters["schools"])]
    start_dt = pd.Timestamp(filters["start_date"])
    end_dt = pd.Timestamp(filters["end_date"])
    goals = goals[(goals["week_end"] >= start_dt) & (goals["week_start"] <= end_dt)]

    if goals.empty:
        st.warning("No weekly goals data for selected filters.")
        return

    for school in sorted(goals["school"].unique()):
        st.subheader(school)
        school_goals = goals[goals["school"] == school].sort_values("week_start", ascending=False).copy()

        school_goals["lead_status"] = school_goals.apply(
            lambda r: _traffic_light(r["lead_actual"], r["lead_target"]), axis=1
        )
        school_goals["spend_status"] = school_goals.apply(
            lambda r: _traffic_light_spend(r["spend_actual"], r["spend_target"]), axis=1
        )
        school_goals["cpa_status"] = school_goals.apply(
            lambda r: _traffic_light_cpa(r["cpa_actual"], r["cpa_target"]), axis=1
        )

        display = school_goals[[
            "week_start", "lead_target", "lead_actual", "lead_status",
            "spend_target", "spend_actual", "spend_status",
            "cpa_target", "cpa_actual", "cpa_status",
        ]].copy()

        display["week_start"] = display["week_start"].dt.strftime("%d %b")
        display["lead_target"] = display["lead_target"].apply(lambda x: f"{x:.1f}")
        display["lead_actual"] = display["lead_actual"].apply(lambda x: f"{x:.1f}")
        c = filters["currency"]
        display["spend_target"] = display["spend_target"].apply(lambda x: fmt(x, c))
        display["spend_actual"] = display["spend_actual"].apply(lambda x: fmt(x, c))
        display["cpa_target"] = display["cpa_target"].apply(lambda x: fmt(x, c))
        display["cpa_actual"] = display["cpa_actual"].apply(lambda x: fmt(x, c))

        display.columns = [
            "Week", "Lead Target", "Lead Actual", "Leads",
            "Spend Target", "Spend Actual", "Spend",
            "CPA Target", "CPA Actual", "CPA",
        ]

        def _color_status(val):
            colors = {
                "On Track": "background-color: #d4edda; color: #155724",
                "At Risk": "background-color: #fff3cd; color: #856404",
                "Behind": "background-color: #f8d7da; color: #721c24",
            }
            return colors.get(val, "")

        styled = display.style.map(
            _color_status, subset=["Leads", "Spend", "CPA"]
        )
        st.dataframe(styled, width="stretch", hide_index=True)


def _traffic_light(actual, target):
    if target == 0:
        return "---"
    ratio = actual / target
    if ratio >= 0.9:
        return "On Track"
    elif ratio >= 0.7:
        return "At Risk"
    return "Behind"


def _traffic_light_spend(actual, target):
    if target == 0:
        return "---"
    ratio = actual / target
    if 0.85 <= ratio <= 1.15:
        return "On Track"
    elif 0.7 <= ratio <= 1.3:
        return "At Risk"
    return "Behind"


def _traffic_light_cpa(actual, target):
    if target == 0:
        return "---"
    if actual <= target:
        return "On Track"
    elif actual <= target * 1.2:
        return "At Risk"
    return "Behind"
