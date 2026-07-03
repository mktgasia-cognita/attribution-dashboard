import pandas as pd
from pathlib import Path
from google.cloud import bigquery

PROJECT = "sustained-truck-487013-g7"
DATASET = "bcs_attribution"
CSV_DIR = Path(__file__).resolve().parent / "bcs_real"


def _get_client():
    import streamlit as st
    try:
        sa_section = st.secrets["gcp_service_account"]
        sa = {k: str(v) for k, v in sa_section.items()}
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(sa)
        return bigquery.Client(project=PROJECT, credentials=creds)
    except KeyError:
        pass
    except Exception as e:
        st.error(f"BQ auth failed: {type(e).__name__}: {e}")
    return bigquery.Client(project=PROJECT)


def _query(client, table):
    ref = f"`{PROJECT}.{DATASET}.{table}`"
    return client.query(f"SELECT * FROM {ref}").to_dataframe()


def load_bcs_data_from_bq():
    client = _get_client()

    journeys_raw = _query(client, "journeys_stitched")
    journeys_raw["date"] = pd.to_datetime(journeys_raw["date"])

    attributed = _query(client, "attributed")
    attributed["date"] = pd.to_datetime(attributed["date"])

    d365_enrichment = _query(client, "crm_leads")

    enr_cols = ["journey_id", "applied_grade", "nationality",
                "admission_status", "academic_year", "address_country"]
    enr = d365_enrichment[[c for c in enr_cols if c in d365_enrichment.columns]]
    if not enr.empty:
        journeys_raw = journeys_raw.merge(enr, on="journey_id", how="left")
        attributed = attributed.merge(enr, on="journey_id", how="left")

    spend = _query(client, "spend_combined")
    spend["date"] = pd.to_datetime(spend["date"])

    search_terms = _query(client, "search_terms")
    landing_pages = _query(client, "landing_pages")

    ad_lookups_raw = _query(client, "ad_lookups")
    ad_lookups = {}
    if not ad_lookups_raw.empty:
        google = ad_lookups_raw[ad_lookups_raw["platform"] == "google"].copy()
        meta = ad_lookups_raw[ad_lookups_raw["platform"] == "meta"].copy()
        if not google.empty:
            if "group_name" in google.columns:
                google = google.rename(columns={"group_name": "ad_group_name"})
            ad_lookups["google_adgroup"] = google
        if not meta.empty:
            if "group_name" in meta.columns:
                meta = meta.rename(columns={"group_name": "ad_set_name"})
            ad_lookups["meta_adset"] = meta

    for name, filename in [("campaign_name_map", "campaign_name_map.csv"),
                           ("meta_ad", "meta_ad_lookup.csv")]:
        path = CSV_DIR / filename
        if path.exists():
            ad_lookups[name] = pd.read_csv(path)

    weekly_goals_path = CSV_DIR / "weekly_goals.csv"
    if weekly_goals_path.exists():
        weekly_goals = pd.read_csv(weekly_goals_path, parse_dates=["week_start", "week_end"])
    else:
        weekly_goals = pd.DataFrame(columns=["school", "week_start", "week_end",
                                             "lead_target", "lead_actual",
                                             "spend_target", "spend_actual",
                                             "cpa_target", "cpa_actual"])

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
