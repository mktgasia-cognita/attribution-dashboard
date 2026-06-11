import pandas as pd
import numpy as np
from datetime import datetime, timedelta

SEED = 42
RNG = np.random.default_rng(SEED)

SCHOOLS = {
    "AIS": {"weight": 0.60, "country": "Singapore", "currency": "SGD"},
    "BCS": {"weight": 0.10, "country": "Singapore", "currency": "SGD"},
    "SAIS": {"weight": 0.20, "country": "Singapore", "currency": "SGD"},
    "ISHCMC": {"weight": 0.10, "country": "Vietnam", "currency": "VND"},
}

DATE_START = datetime(2026, 1, 1)
DATE_END = datetime(2026, 6, 30)
TOTAL_DAYS = (DATE_END - DATE_START).days + 1
DATES = [DATE_START + timedelta(days=i) for i in range(TOTAL_DAYS)]

CHANNELS = [
    "Organic Search", "Direct", "Paid Social", "GenericPaidSearch",
    "BrandedPaidSearch", "Referral", "Email", "Social", "Display",
    "PaidVideo", "CompetitorPaidSearch", "PMaxPaidSearch", "Offline",
]

SOURCES = {
    "Organic Search": ["google", "bing", "yahoo", "duckduckgo"],
    "Direct": ["(direct)"],
    "Paid Social": ["facebook", "tiktok", "instagram"],
    "GenericPaidSearch": ["google", "bing"],
    "BrandedPaidSearch": ["google", "bing"],
    "Referral": ["chatgpt.com", "whichschooladvisor.com", "expatliving.sg", "honeykidsasia.com"],
    "Email": ["mailchimp", "hubspot"],
    "Social": ["facebook", "instagram", "linkedin", "tiktok"],
    "Display": ["stackadapt", "google"],
    "PaidVideo": ["google"],
    "CompetitorPaidSearch": ["google"],
    "PMaxPaidSearch": ["google"],
    "Offline": ["event", "campus_tour"],
}

MEDIUMS = {
    "Organic Search": "organic",
    "Direct": "(none)",
    "Paid Social": "paid-social",
    "GenericPaidSearch": "cpc",
    "BrandedPaidSearch": "cpc",
    "Referral": "referral",
    "Email": "email",
    "Social": "social",
    "Display": "display",
    "PaidVideo": "cpc",
    "CompetitorPaidSearch": "cpc",
    "PMaxPaidSearch": "cpc",
    "Offline": "offline",
}

CAMPAIGN_TEMPLATES = {
    "GenericPaidSearch": ["SG-Search-Generic-{school}", "SG-Search-Admissions-{school}", "SG-Search-IB-{school}"],
    "BrandedPaidSearch": ["SG-Search-Brand-{school}", "SG-Search-Brand-Campus-{school}"],
    "Paid Social": ["SG-FB-LeadGen-{school}", "SG-FB-Awareness-{school}", "SG-IG-Reels-{school}"],
    "CompetitorPaidSearch": ["SG-Search-Competition-{school}"],
    "PMaxPaidSearch": ["SG-PMax-Admissions-{school}", "SG-PMax-OpenDay-{school}"],
    "Display": ["SG-Display-Retargeting-{school}", "SG-Display-Prospecting-{school}"],
    "PaidVideo": ["SG-VD-BrandAwareness-{school}", "SG-VD-CampusTour-{school}"],
}

COUNTRIES_SG = {"Singapore": 0.40, "Australia": 0.10, "China": 0.08, "India": 0.10,
                "South Korea": 0.07, "Indonesia": 0.05, "Hong Kong": 0.05,
                "United Kingdom": 0.05, "Japan": 0.04, "United States": 0.03, "Other": 0.03}

COUNTRIES_VN = {"Vietnam": 0.35, "South Korea": 0.15, "Japan": 0.10, "Taiwan": 0.08,
                "Australia": 0.07, "Singapore": 0.05, "China": 0.05, "India": 0.05,
                "United States": 0.04, "Hong Kong": 0.03, "Other": 0.03}

CRM_STAGES = ["D1 Lead", "D2 Enquiry", "D3 Application", "D4 Offer", "D5 Enrolment"]

CLOSED_REASONS = {
    "Family Circumstances": 0.20, "No Response": 0.25, "Duplicate": 0.10,
    "Competitor School": 0.15, "Deferred": 0.10, "Budget Constraints": 0.08,
    "Relocation Cancelled": 0.07, "Other": 0.05,
}

CHANNEL_TOUCH_WEIGHTS = {
    "first": {"Organic Search": 0.30, "Direct": 0.10, "Paid Social": 0.20,
              "GenericPaidSearch": 0.12, "Referral": 0.10, "Social": 0.05,
              "Display": 0.05, "PaidVideo": 0.03, "BrandedPaidSearch": 0.03,
              "Email": 0.01, "CompetitorPaidSearch": 0.01, "PMaxPaidSearch": 0.00, "Offline": 0.00},
    "middle": {"Organic Search": 0.15, "Direct": 0.20, "Paid Social": 0.15,
               "GenericPaidSearch": 0.10, "BrandedPaidSearch": 0.10, "Email": 0.08,
               "Social": 0.05, "Referral": 0.05, "Display": 0.05, "PaidVideo": 0.02,
               "CompetitorPaidSearch": 0.02, "PMaxPaidSearch": 0.02, "Offline": 0.01},
    "last": {"Direct": 0.30, "BrandedPaidSearch": 0.20, "Organic Search": 0.15,
             "GenericPaidSearch": 0.10, "Paid Social": 0.08, "Email": 0.07,
             "Referral": 0.05, "Social": 0.02, "Display": 0.01, "PaidVideo": 0.01,
             "CompetitorPaidSearch": 0.01, "PMaxPaidSearch": 0.00, "Offline": 0.00},
}

SPEND_PER_CHANNEL = {
    "GenericPaidSearch": (80, 200), "BrandedPaidSearch": (20, 60),
    "Paid Social": (50, 150), "CompetitorPaidSearch": (40, 120),
    "PMaxPaidSearch": (60, 180), "Display": (30, 80), "PaidVideo": (25, 70),
    "Organic Search": (0, 0), "Direct": (0, 0), "Referral": (0, 0),
    "Email": (0, 0), "Social": (0, 0), "Offline": (0, 0),
}


def _pick_weighted(options_dict):
    keys = list(options_dict.keys())
    weights = np.array(list(options_dict.values()), dtype=float)
    weights /= weights.sum()
    return keys[RNG.choice(len(keys), p=weights)]


def _pick_channel(position):
    return _pick_weighted(CHANNEL_TOUCH_WEIGHTS[position])


def _make_campaign(channel, school):
    templates = CAMPAIGN_TEMPLATES.get(channel)
    if not templates:
        return "(not set)"
    return RNG.choice(templates).format(school=school)


def _get_countries(school):
    return COUNTRIES_VN if school == "ISHCMC" else COUNTRIES_SG


def generate_journeys(n_total=2000):
    rows = []
    journey_id = 0

    for school, cfg in SCHOOLS.items():
        n_school = int(n_total * cfg["weight"])
        countries = _get_countries(school)

        for _ in range(n_school):
            journey_id += 1
            n_touches = RNG.integers(2, 7)
            start_date = RNG.choice(DATES[:len(DATES) - 30])
            country = _pick_weighted(countries)

            touchpoints = []
            for t in range(n_touches):
                if t == 0:
                    ch = _pick_channel("first")
                elif t == n_touches - 1:
                    ch = _pick_channel("last")
                else:
                    ch = _pick_channel("middle")

                source = RNG.choice(SOURCES[ch])
                medium = MEDIUMS[ch]
                campaign = _make_campaign(ch, school)
                touch_date = start_date + timedelta(days=int(t * RNG.integers(1, 14)))

                touchpoints.append({
                    "journey_id": f"J-{journey_id:05d}",
                    "school": school,
                    "touchpoint": t + 1,
                    "total_touchpoints": n_touches,
                    "date": touch_date,
                    "channel_grouping": ch,
                    "source": source,
                    "medium": medium,
                    "campaign": campaign,
                    "country": country,
                })

            max_stage_idx = _funnel_stage()
            for tp in touchpoints:
                tp["max_stage"] = CRM_STAGES[max_stage_idx]
                tp["max_stage_idx"] = max_stage_idx
                tp["status"] = "Won" if max_stage_idx == 4 else ("Active" if RNG.random() < 0.4 else "Lost")
                if tp["status"] == "Lost" and max_stage_idx < 4:
                    tp["closed_reason"] = _pick_weighted(CLOSED_REASONS)
                else:
                    tp["closed_reason"] = None

            rows.extend(touchpoints)

    return pd.DataFrame(rows)


def _funnel_stage():
    r = RNG.random()
    if r < 0.40:
        return 0  # D1 only
    elif r < 0.64:
        return 1  # D2
    elif r < 0.80:
        return 2  # D3
    elif r < 0.92:
        return 3  # D4
    else:
        return 4  # D5


def apply_position_attribution(journeys_df):
    records = []
    for jid, group in journeys_df.groupby("journey_id"):
        n = len(group)
        group = group.sort_values("touchpoint")

        for i, (_, row) in enumerate(group.iterrows()):
            if n == 1:
                weight = 1.0
            elif n == 2:
                weight = 0.5
            else:
                if i == 0:
                    weight = 0.4
                elif i == n - 1:
                    weight = 0.4
                else:
                    weight = 0.2 / (n - 2)

            for stage_idx in range(row["max_stage_idx"] + 1):
                records.append({
                    "journey_id": row["journey_id"],
                    "school": row["school"],
                    "date": row["date"],
                    "channel_grouping": row["channel_grouping"],
                    "source": row["source"],
                    "medium": row["medium"],
                    "campaign": row["campaign"],
                    "country": row["country"],
                    "touchpoint": row["touchpoint"],
                    "total_touchpoints": row["total_touchpoints"],
                    "stage": CRM_STAGES[stage_idx],
                    "stage_idx": stage_idx,
                    "attribution_weight": weight,
                    "status": row["status"],
                    "closed_reason": row["closed_reason"],
                })

    return pd.DataFrame(records)


def generate_spend(journeys_df):
    rows = []
    for school in SCHOOLS:
        school_factor = SCHOOLS[school]["weight"]
        for date in DATES:
            for channel, (low, high) in SPEND_PER_CHANNEL.items():
                if low == 0 and high == 0:
                    continue
                daily_spend = RNG.uniform(low, high) * school_factor
                daily_spend *= (1 + 0.15 * np.sin(2 * np.pi * date.timetuple().tm_yday / 365))
                impressions = int(daily_spend * RNG.uniform(8, 25))
                clicks = int(impressions * RNG.uniform(0.01, 0.08))

                source = RNG.choice(SOURCES.get(channel, ["google"]))
                campaign = _make_campaign(channel, school)

                rows.append({
                    "school": school,
                    "date": date,
                    "channel_grouping": channel,
                    "source": source,
                    "medium": MEDIUMS[channel],
                    "campaign": campaign,
                    "spend": round(daily_spend, 2),
                    "impressions": impressions,
                    "clicks": clicks,
                    "cpc": round(daily_spend / max(clicks, 1), 2),
                })

    return pd.DataFrame(rows)


def generate_search_terms():
    keywords = [
        "international school singapore", "ib school singapore", "best international school",
        "australian international school", "stamford american school", "brighton college singapore",
        "international school ho chi minh", "ib diploma singapore", "early years programme",
        "international school fees singapore", "expat school singapore", "english medium school",
        "ap program singapore", "a levels singapore school", "igcse singapore",
        "international school open day", "school bus international school", "bilingual school singapore",
        "primary school international singapore", "secondary school international",
    ]
    match_types = ["EXACT", "PHRASE", "BROAD"]
    rows = []

    for school in SCHOOLS:
        school_factor = SCHOOLS[school]["weight"]
        campaigns = CAMPAIGN_TEMPLATES.get("GenericPaidSearch", []) + CAMPAIGN_TEMPLATES.get("BrandedPaidSearch", [])
        for kw in keywords:
            for mt in RNG.choice(match_types, size=RNG.integers(1, 3), replace=False):
                campaign = RNG.choice(campaigns).format(school=school)
                clicks = int(RNG.integers(5, 200) * school_factor)
                cost = round(clicks * RNG.uniform(0.5, 4.0), 2)
                rows.append({
                    "school": school,
                    "keyword": kw,
                    "search_term": kw + (" near me" if RNG.random() < 0.2 else ""),
                    "match_type": mt,
                    "campaign": campaign,
                    "clicks": clicks,
                    "cost": cost,
                    "cpc": round(cost / max(clicks, 1), 2),
                    "impressions": int(clicks * RNG.uniform(5, 20)),
                    "conversions": int(clicks * RNG.uniform(0.02, 0.12)),
                    "quality_score": int(RNG.integers(3, 10)),
                    "avg_position": round(RNG.uniform(1.0, 4.5), 1),
                })

    return pd.DataFrame(rows)


def generate_landing_pages():
    pages = [
        "/admissions", "/admissions/fees", "/admissions/apply-now",
        "/academics/ib-diploma", "/academics/ib-pyp", "/academics/ib-myp",
        "/school-life", "/school-life/campus-tour", "/about-us",
        "/contact", "/open-day", "/early-years", "/scholarships",
        "/boarding", "/bus-routes", "/parent-portal",
    ]
    rows = []
    for school in SCHOOLS:
        school_factor = SCHOOLS[school]["weight"]
        for page in pages:
            sessions = int(RNG.integers(100, 5000) * school_factor)
            conversions = int(sessions * RNG.uniform(0.005, 0.08))
            rows.append({
                "school": school,
                "landing_page": page,
                "sessions": sessions,
                "conversions": conversions,
                "conversion_rate": round(conversions / max(sessions, 1) * 100, 2),
                "bounce_rate": round(RNG.uniform(25, 75), 1),
                "avg_session_duration": round(RNG.uniform(30, 300), 0),
            })
    return pd.DataFrame(rows)


def generate_weekly_goals():
    rows = []
    week_start = DATE_START
    while week_start <= DATE_END:
        for school in SCHOOLS:
            school_factor = SCHOOLS[school]["weight"]
            lead_target = int(25 * school_factor)
            spend_target = round(3000 * school_factor, 0)
            cpa_target = round(spend_target / max(lead_target, 1), 2)

            lead_actual = int(lead_target * RNG.uniform(0.6, 1.4))
            spend_actual = round(spend_target * RNG.uniform(0.85, 1.15), 2)
            cpa_actual = round(spend_actual / max(lead_actual, 1), 2)

            rows.append({
                "school": school,
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "lead_target": lead_target,
                "lead_actual": lead_actual,
                "spend_target": spend_target,
                "spend_actual": spend_actual,
                "cpa_target": cpa_target,
                "cpa_actual": cpa_actual,
            })
        week_start += timedelta(days=7)
    return pd.DataFrame(rows)


def load_all_data():
    journeys_raw = generate_journeys(n_total=2000)
    attributed = apply_position_attribution(journeys_raw)
    spend = generate_spend(journeys_raw)
    search_terms = generate_search_terms()
    landing_pages = generate_landing_pages()
    weekly_goals = generate_weekly_goals()
    return {
        "journeys_raw": journeys_raw,
        "attributed": attributed,
        "spend": spend,
        "search_terms": search_terms,
        "landing_pages": landing_pages,
        "weekly_goals": weekly_goals,
    }
