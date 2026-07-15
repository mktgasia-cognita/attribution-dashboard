import pandas as pd
from pathlib import Path
from google.cloud import bigquery

PROJECT = "sustained-truck-487013-g7"
DATASET = "cognita_attribution"
CSV_DIR = Path(__file__).resolve().parent / "school_data"

RUN_STAMPED_TABLES = {
    "v_journeys_stitched", "v_attributed", "v_crm_leads", "v_spend_combined",
    "v_search_terms", "v_landing_pages", "v_ad_lookups",
}


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
    return bigquery.Client(project=PROJECT, credentials=creds)


def _latest_complete_run(client):
    """Return the pipeline_run_ts of the latest complete run, or None.

    None means the pipeline_runs marker table does not exist yet (legacy
    truncate-era data) - tables are then read unfiltered.
    """
    sql = f"""
        SELECT MIN(latest_ts) AS run_ts FROM (
            SELECT school, MAX(pipeline_run_ts) AS latest_ts
            FROM `{PROJECT}.{DATASET}.v_pipeline_latest`
            WHERE status = 'complete'
            GROUP BY school
        )
    """
    try:
        df = client.query(sql).to_dataframe()
    except Exception:
        return None
    if df.empty or pd.isna(df["run_ts"].iloc[0]):
        return None
    return str(df["run_ts"].iloc[0])


def _query(client, table, run_ts=None):
    ref = f"`{PROJECT}.{DATASET}.{table}`"
    if run_ts and table in RUN_STAMPED_TABLES:
        # pipeline_runs stores the ts as STRING; stamped tables hold TIMESTAMP.
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("run_ts", "STRING", run_ts),
        ])
        sql = f"SELECT * FROM {ref} WHERE pipeline_run_ts = TIMESTAMP(@run_ts)"
        return client.query(sql, job_config=job_config).to_dataframe()
    return client.query(f"SELECT * FROM {ref}").to_dataframe()


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

    journeys_raw = _naive_dates(_query(client, "v_journeys_stitched", run_ts))
    attributed = _naive_dates(_query(client, "v_attributed", run_ts))

    d365_enrichment = _query(client, "v_crm_leads", run_ts)

    enr_cols = ["journey_id", "applied_grade", "nationality",
                "admission_status", "academic_year", "address_country"]
    enr = d365_enrichment[[c for c in enr_cols if c in d365_enrichment.columns]]
    if not enr.empty and "journey_id" in enr.columns:
        journeys_raw = journeys_raw.merge(enr, on="journey_id", how="left")
        attributed = attributed.merge(enr, on="journey_id", how="left")

    spend = _naive_dates(_query(client, "v_spend_combined", run_ts))

    search_terms = _query(client, "v_search_terms", run_ts)
    landing_pages = _query(client, "v_landing_pages", run_ts)

    ad_lookups_raw = _query(client, "v_ad_lookups", run_ts)
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
        # Freshness metadata for the UI: BQ run being served, plus which
        # datasets still come from repo CSVs in BQ mode.
        "bq_run_ts": run_ts,
        "csv_sourced": ["weekly_goals", "campaign_name_map", "meta_ad lookup"],
    }
