"""
Canonical channel grouping logic for attribution pipeline and dashboard.
Single source of truth - keep in sync with attribution-dashboard/utils/channel_grouping.py
"""

import re

BRAND_PATTERN = re.compile(r"brand|branded", re.IGNORECASE)
PMAX_PATTERN = re.compile(r"pmax|performance.max", re.IGNORECASE)
COMPETITOR_PATTERN = re.compile(r"compet|rival", re.IGNORECASE)


def classify_channel(source, medium, campaign, ad_product_group=""):
    s = str(source).lower().strip()
    m = str(medium).lower().strip()
    c = str(campaign).lower().strip()
    apg = str(ad_product_group).lower().strip()

    if s == "google" and "vd-" in c:
        return "PaidVideo"
    if s == "stackadapt":
        return "Display"
    if COMPETITOR_PATTERN.search(c):
        return "CompetitorPaidSearch"
    if m == "offline":
        return "Offline"
    if s == "(unknown)" and m == "(unknown)":
        return "Unknown"
    if s == "(direct)" and m in ("(not set)", "(none)"):
        return "Direct"
    if m == "gmb":
        return "Local"
    if m == "organic":
        return "OrganicSearch"
    if m in ("cpc", "paid-social") and s in ("facebook", "tiktok", "instagram"):
        return "PaidSocial"
    if "social" in m:
        return "Social"
    if m == "email":
        return "Email"
    if m == "referral":
        return "Referral"
    if m in ("cpc", "ppc", "paidsearch"):
        if BRAND_PATTERN.search(c) or BRAND_PATTERN.search(apg):
            return "BrandedPaidSearch"
        if PMAX_PATTERN.search(c):
            return "PMaxPaidSearch"
        if COMPETITOR_PATTERN.search(c) or COMPETITOR_PATTERN.search(apg):
            return "CompetitorPaidSearch"
        return "GenericPaidSearch"
    if m in ("display", "cpm", "banner"):
        return "Display"
    return "(Other)"


CHANNEL_COLORS = {
    "OrganicSearch": "#2ecc71",
    "Direct": "#95a5a6",
    "PaidSocial": "#3498db",
    "GenericPaidSearch": "#e74c3c",
    "BrandedPaidSearch": "#e67e22",
    "Referral": "#9b59b6",
    "Email": "#1abc9c",
    "Social": "#34495e",
    "Display": "#f39c12",
    "PaidVideo": "#d35400",
    "CompetitorPaidSearch": "#8e44ad",
    "PMaxPaidSearch": "#2980b9",
    "Offline": "#7f8c8d",
    "Unknown": "#d5dbdb",
    "Local": "#27ae60",
    "DemandGen": "#c0392b",
    "(Other)": "#bdc3c7",
}
