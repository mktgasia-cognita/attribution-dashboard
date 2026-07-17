import pandas as pd
from pathlib import Path
from google.cloud import bigquery

PROJECT = "sustained-truck-487013-g7"
DATASET = "cognita_attribution"
CSV_DIR = Path(__file__).resolve().parent / "school_data"

def _get_client():
    import streamlit as st
    try:
        sa_section = st.secrets["gcp_service_account"]
    except KeyError:
        raise RuntimeError(
            "Missing [gcp_service_account] in Streamlit secrets. "
            "Set data_source = 'csv' to use CSV fallback."
        )
    sa = {k: str(v) for k, v in sa_section.items()}
    if "private_key" in sa:
        sa["private_key"] = sa["private_key"].replace("\\n", "\n")
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(sa)
    return bigquery.Client(project=PROJECT, credentials=creds, location="asia-southeast1")


def _latest_complete_run(client):
    """Return the oldest per-school latest run timestamp for UI display.

    The cognita_attribution views already filter to the latest complete
    run per school, so this is metadata only — not used for query filtering.
    """
    sql = f"""
        SELECT MIN(latest_ts) AS run_ts FROM (
            SELECT school, MAX(pipeline_run_ts) AS latest_ts
            FROM `{PROJECT}.{DATASET}.v_pipeline_latest`
            GROUP BY school
        )
    """
    try:
        rows = client.query(sql).result()
        df = pd.DataFrame([dict(row) for row in rows])
    except Exception:
        return None
    if df.empty or pd.isna(df["run_ts"].iloc[0]):
        return None
    return str(df["run_ts"].iloc[0])


def _query(client, table):
    ref = f"`{PROJECT}.{DATASET}.{table}`"
    rows = client.query(f"SELECT * FROM {ref}").result()
    return pd.DataFrame([dict(row) for row in rows])


def _naive_dates(df, col="date"):
    """Parse a date column defensively: tz-aware values become naive."""
    df[col] = pd.to_datetime(df[col])
    try:
        df[col] = df[col].dt.tz_localize(None)
    except TypeError:
        pass  # already naive
    return df


def load_data_from_bq():
    client = _get_client()
    run_ts = _latest_complete_run(client)

    journeys_raw = _naive_dates(_query(client, "v_journeys_stitched"))
    attributed = _naive_dates(_query(client, "v_attributed"))

    d365_enrichment = _query(client, "v_crm_leads")

    enr_cols = ["journey_id", "applied_grade", "nationality",
                "admission_status", "academic_year", "address_country"]
    enr = d365_enrichment[[c for c in enr_cols if c in d365_enrichment.columns]]
    if not enr.empty and "journey_id" in enr.columns:
        journeys_raw = journeys_raw.merge(enr, on="journey_id", how="left")
        attributed = attributed.merge(enr, on="journey_id", how="left")

    spend = _naive_dates(_query(client, "v_spend_combined"))

    search_terms = _query(client, "v_search_terms")
    landing_pages = _query(client, "v_landing_pages")

    stitch_err = None
    try:
        stitch_audit = _query(client, "v_stitch_audit")
        stitch_err = f"v11-query:{len(stitch_audit)}rows"
    except Exception as e:
        stitch_err = f"v11-err:{type(e).__name__}:{e}"
        stitch_audit = pd.DataFrame()
    crm_err = None
    try:
        crm_leads_raw = _query(client, "v_crm_leads_raw")
    except Exception as e:
        crm_err = str(e)
        print(f"crm_leads_raw load failed: {e}")
        crm_leads_raw = pd.DataFrame()

    ad_lookups_raw = _query(client, "v_ad_lookups")
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
        "stitch_audit": stitch_audit,
        "crm_leads_raw": crm_leads_raw,
        "bq_run_ts": run_ts,
        "csv_sourced": ["weekly_goals", "campaign_name_map", "meta_ad lookup"],
        "_stitch_err": stitch_err,
        "_crm_err": crm_err,
    }
