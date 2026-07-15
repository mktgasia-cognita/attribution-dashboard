import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "school_data"



def load_data():
    journeys_raw = pd.read_csv(DATA_DIR / "journeys_raw.csv", parse_dates=["date"])
    attributed = pd.read_csv(DATA_DIR / "attributed.csv", parse_dates=["date"])

    enrichment_path = DATA_DIR / "d365_enrichment.csv"
    d365_enrichment = None
    if enrichment_path.exists():
        d365_enrichment = pd.read_csv(enrichment_path)
        enr_cols = ["journey_id", "applied_grade", "nationality",
                    "admission_status", "academic_year", "address_country"]
        enr = d365_enrichment[[c for c in enr_cols if c in d365_enrichment.columns]]
        journeys_raw = journeys_raw.merge(enr, on="journey_id", how="left")
        attributed = attributed.merge(enr, on="journey_id", how="left")

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
        "d365_enrichment": d365_enrichment,
    }
