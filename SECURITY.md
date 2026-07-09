# Security Posture - Cognita Attribution Dashboard

## Authentication and Access Control

- Per-user login with username and password (hashed via streamlit-authenticator)
- Role-based school access: each user account is assigned a role that controls data visibility
- School-level users (e.g. BCS) see only their school's attribution data
- Cognita-level users can view and filter across all schools
- Session cookies with configurable expiry (default 7 days)
- Credentials managed via Streamlit Cloud encrypted secrets, not in source code

## Data Protection

- No student PII stored in the dashboard or BigQuery output tables
- CRM phone numbers used only for country-of-origin inference during pipeline processing, then discarded
- Pipeline outputs contain: nationality (aggregate demographic), grade level, admission status, and D365 opportunity GUIDs as anonymised identifiers
- No parent names, email addresses, or contact details are written to BigQuery or served by the dashboard
- All data is scoped per school - cross-school data isolation is enforced at the application layer

## Infrastructure

- **Dashboard hosting:** Streamlit Community Cloud (managed, HTTPS enforced, no direct server access)
- **Pipeline compute:** Google Cloud Run Job with a dedicated service account per pipeline
- **Data storage:** BigQuery datasets with IAM access scoped to specific datasets, not project-wide
- **CRM file storage:** Google Cloud Storage bucket with object-level access control
- **Container image:** Stored in Artifact Registry with git SHA-tagged versions (no mutable :latest in production)

## Pipeline Security

- Error messages are sanitised before writing to BigQuery - no file paths, credentials, or stack traces are stored in the pipeline_runs table
- Full diagnostic stack traces are restricted to Cloud Run logs, which are protected by GCP IAM
- BigQuery queries use parameterised inputs where user-supplied values are involved
- CRM file validation: required column headers are checked on every run; row count thresholds prevent silent data loss
- Pipeline container runs as a non-root user with no local filesystem write access

## Secrets Management

- GCP service account credentials stored in Streamlit Cloud encrypted secrets
- User passwords hashed at rest (streamlit-authenticator handles hashing)
- No credentials, API keys, or service account files in source code
- secrets.toml is gitignored and never committed
- Dashboard repository contains no sensitive configuration

## Known Limitations

- **No multi-factor authentication:** Streamlit does not support MFA natively. Mitigated by strong passwords and limited user count
- **No access audit log:** Streamlit Community Cloud does not provide per-user login audit trails. Pipeline runs are logged in BigQuery with timestamps
- **No rate limiting:** Rate limiting depends on Streamlit Cloud infrastructure. The small user base (under 10 accounts) makes this low risk
- **CSV fallback mode:** Bundled CSV files contain the same data as BigQuery. No additional data exposure, but the data is static until refreshed
- **Single-region deployment:** Pipeline and data reside in asia-southeast1. No cross-region redundancy for this proof of concept
