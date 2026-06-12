import re

BRAND_PATTERN = re.compile(r"brand|branded", re.IGNORECASE)
PMAX_PATTERN = re.compile(r"pmax|performance.max", re.IGNORECASE)
COMPETITOR_PATTERN = re.compile(r"compet|rival", re.IGNORECASE)


def classify_channel(source, medium, campaign):
    source = str(source).lower().strip()
    medium = str(medium).lower().strip()
    campaign = str(campaign).lower().strip()

    if source == "google" and "vd-" in campaign:
        return "PaidVideo"
    if source == "stackadapt":
        return "Display"
    if "competition" in campaign:
        return "PaidSearchCompetitor"
    if medium == "offline":
        return "Offline"
    if source == "(direct)" and medium in ("(not set)", "(none)"):
        return "Direct"
    if medium == "organic":
        return "Organic Search"
    if medium in ("cpc", "paid-social") and source in ("facebook", "tiktok", "instagram"):
        return "Paid Social"
    if "social" in medium:
        return "Social"
    if medium == "email":
        return "Email"
    if medium == "referral":
        return "Referral"

    if medium in ("cpc", "ppc", "paidsearch"):
        if BRAND_PATTERN.search(campaign):
            return "BrandedPaidSearch"
        if PMAX_PATTERN.search(campaign):
            return "PMaxPaidSearch"
        if COMPETITOR_PATTERN.search(campaign):
            return "CompetitorPaidSearch"
        return "GenericPaidSearch"

    return "Other"


CHANNEL_COLORS = {
    "Organic Search": "#2ecc71",
    "Direct": "#95a5a6",
    "Paid Social": "#3498db",
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
    "Other": "#bdc3c7",
}
