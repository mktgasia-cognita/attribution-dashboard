# TODO: Replace synthetic data with live BigQuery connector
# Tables: ga4_sessions, ga4_events, google_ads, meta_ads, dynamics365_leads, windsor_attribution
# See WINDSOR_DATA_MAPPING.md for field-by-field schema


def load_from_bigquery(project_id, dataset, date_range, schools):
    raise NotImplementedError("BigQuery connector not yet implemented. Using synthetic data.")
