import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "bcs_real"



def load_bcs_data():
    journeys_raw = pd.read_csv(DATA_DIR / "journeys_raw.csv", parse_dates=["date"])
    attributed = pd.read_csv(DATA_DIR / "attributed.csv", parse_dates=["date"])

    spend = pd.read_csv(DATA_DIR / "spend.csv", parse_dates=["date"])
    search_terms = pd.read_csv(DATA_DIR / "search_terms.csv")
    landing_pages = pd.read_csv(DATA_DIR / "landing_pages.csv")
    weekly_goals = pd.read_csv(DATA_DIR / "weekly_goals.csv", parse_dates=["week_start", "week_end"])

    ad_lookups = {}
    for name, filename in [
        ("google_adgroup", "google_adgroup_lookup.csv"),
        ("meta_adset", "meta_adset_lookup.csv"),
        ("meta_ad", "meta_ad_lookup.csv"),
        ("campaign_name_map", "campaign_name_map.csv"),
    ]:
        path = DATA_DIR / filename
        if path.exists():
            ad_lookups[name] = pd.read_csv(path)

    return {
        "journeys_raw": journeys_raw,
        "attributed": attributed,
        "spend": spend,
        "search_terms": search_terms,
        "landing_pages": landing_pages,
        "weekly_goals": weekly_goals,
        "ad_lookups": ad_lookups,
    }
