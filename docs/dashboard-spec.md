# Attribution System — Complete Rebuild Spec

If the pipeline, dashboard, and BQ tables were lost, this document is sufficient to rebuild the entire system. Read before modifying any component.

---

## Infrastructure

| Component | Value |
|-----------|-------|
| BQ output project | `sustained-truck-487013-g7` |
| GA4 export project | `project-064549ab-2f9a-4bc5-a7b` (all schools) |
| GCS bucket | `cognita-attribution-crm` (per-school prefix) |
| Per-school BQ datasets | `bcs_attribution`, `ais_attribution`, `sais_attribution`, `ishcmc_attribution` |
| Combined BQ dataset | `cognita_attribution` (location: `asia-southeast1`) |
| Dashboard repo | `mktgasia-cognita/attribution-dashboard` (GitHub) |
| Dashboard hosting | Streamlit Cloud, auto-deploys on push to main |
| Python version | 3.12.9 |

---

## School Configuration

```
BCS:  ga4=analytics_249899399  gads=bcs_google_ads  gads_id=9424958631  meta=bcs_meta_ads  domain=brightoncollege.edu.sg  prefix=BCS  country=Singapore  currencies=SGD/SGD
AIS:  ga4=analytics_330605498  gads=ais_google_ads  gads_id=8424446309  meta=ais_meta_ads  domain=ais.com.sg             prefix=AIS  country=Singapore  currencies=SGD/SGD
SAIS: ga4=analytics_348401125  gads=sais_google_ads gads_id=7737087564  meta=sais_meta_ads  domain=sais.edu.sg            prefix=SAIS country=Singapore  currencies=SGD/SGD
ISHCMC: ga4=analytics_324467120 gads=ishcmc_google_ads gads_id=3459829821 meta=ishcmc_meta_ads domain=ishcmc.com          prefix=ISHCMC country=Vietnam  currencies=VND/USD
```

All schools share the same GA4 project and conversion events: `generate_lead`, `form_submit`, `Brew_FormSubmit`, `BookATour`, `book_a_tour`.

---

## Pipeline Data Flow

```
Phase 0: CRM Ingest
  D365 CSV (GCS auto-pick newest, or local file, or ~/Downloads fallback)
  → parse leads: CID from Journey ID (strip GA1.X. prefix)
  → classify entry_type: webform (channel in {Webform}) or offline
  → append to crm_leads_raw table (dedup by d365_id, keep latest)

Phase 1: Stitch
  CID → user_pseudo_id matching (3 tiers, cascading on unmatched):
    tier1:    user_properties.custom_client_id == "{cid}." (trailing dot)
    tier1.5:  user_pseudo_id == cid (direct match on session_start)
    tier2:    prefix match — integer part of CID matches SPLIT(upid,'.')[0]
              (handles scientific notation: "1.36E9" → str(int(float)))
              picks earliest first_seen on collision

  Matched UIDs → fetch GA4 sessions (session_start events)
    source/medium/campaign: COALESCE(collected_traffic_source.manual_*, traffic_source.*)
    null defaults: source=(direct), medium=(none), campaign=(not set)
    sorted by timestamp per user

  Build journeys from matched sessions:
    - Offline leads: log to stitch_audit, SKIP (no digital signal)
    - Unknown leads (source+medium both (unknown)): log to stitch_audit, SKIP
    - BQ-matched leads: multi-touch journey from GA4 sessions
    - UTM-fallback leads: single-touch journey from UTM params

Phase 2: Markov Attribution
  prepare_markov_journeys: deduplicate consecutive same source|medium|campaign touchpoints
    (NOT channel-level — two touchpoints in the same channel but different campaigns are kept)
  run_attribution: per-stage Markov for stages 2-5 (Enquiry through Enrolment)
    Lead stage: null-journey injection (1-in-10 sampling of GA4 sessions
    without CRM conversion) to establish baseline conversion probability
    Rescale lead attribution to actual CRM lead count

Phase 3: Write
  save_journeys_to_bq: one row per touchpoint
  save_attributed_to_bq: one row per touchpoint x stage
    attribution_weight = position_weight x max(markov_channel_weight, 0.01)
  save_markov_to_bq: channel-level summary weights

Phase 4: Ad Data
  Google Ads spend from BQ transfer tables (ads_CampaignBasicStats)
    — already campaign-level, SUM GROUP BY campaign, date
  Meta Ads spend from BQ transfer tables (AdInsights)
    — AdInsights stores rows at ad+region breakdown level, NOT campaign-level
    — inner: MAX(Spend) GROUP BY CampaignId, CampaignName, DateStart (campaign total)
    — outer: SUM GROUP BY campaign, date (same pattern as Google)
    — same MAX aggregation applies to impressions and clicks
  Search terms from ads_SearchQueryStats + keyword resolution
  Ad lookups (ad group / ad set level performance)
  Spend validation: flag days over daily max threshold

Phase 5: Validation
  Abort (write "failed" marker) if: journeys/stitch/leads/attribution empty
  Warn if: stitch rate <5%, empty spend/search/landing, negative spend, future dates
```

### Date Range Logic
Parses `created_on` from CRM as `%Y-%m-%d` or `%d/%m/%y`. Aborts if >50% fail. Returns `(min_date - 30 days, max_date)` as YYYYMMDD. The 30-day lookback captures GA4 sessions before the earliest CRM lead.

### Pipeline Invocation
```bash
SCHOOL=BCS python3 attribution_pipeline.py              # GCS auto-pick
SCHOOL=BCS python3 attribution_pipeline.py --local-csv path/to/file.csv
SCHOOL=BCS python3 attribution_pipeline.py --gcs-uri gs://cognita-attribution-crm/bcs/file.csv
```
`PIPELINE_RUN_TS` stamped on every row. All tables are append-only. Views serve the latest run where `status='complete'`.

---

## CRM Stage Mapping

```
D365 raw value    Label              Index   Markov stage name
"1 Lead"       →  "D1 Lead"          0       "Lead"
"2 Enquiry"    →  "D2 Enquiry"       1       "Enquiry"
"3 Application"→  "D3 Application"   2       "Application"
"4 Offer"      →  "D4 Offer"         3       "Offer"
"5 Enrolment"  →  "D5 Enrolment"     4       "Enrolment"
```

Status logic: Won if stage_idx==4; Lost if admission_status in ("07 Withdrawn", "10 Rejected", "12 Cancelled"); else Active.

Required D365 headers: `Stage`, `(Do Not Modify) Cognita Opportunity`, `Created On`, `Journey ID`. Missing any → ValueError before any BQ write.

---

## Markov Attribution Algorithm

Pure-Python absorbing Markov chain (no numpy). Imported functions: `run_markov`, `_aggregate_to_channels`.

### Input
Journey dict: `{stage_num, stage_name, status_code, channels[], smc_labels[]}` (consecutive duplicate source|medium|campaign labels already removed).

Markov operates on `smc_labels` (source|medium|campaign strings), not channel groupings. Channel-level attribution is derived by aggregating smc-level results.

### Process
0. **All-converge fallback:** if zero null journeys exist (every journey converts), Markov is bypassed — proportional attribution: `weight = 1.0 / len(unique_states)`, normalised to `total_conversions`, then aggregated to channels. This fires for higher stages (2-5) when all touched journeys reached that stage
1. **Rare state collapse:** states appearing in <3 journeys collapsed to channel group via `split("|", maxsplit=2)` (campaign names may contain `|`)
2. **State space:** `["Start"] + sorted(states) + ["Conversion", "Null"]`
3. **Transition matrix:** count transitions between states, normalise rows to probabilities
4. **Baseline conversion probability:** absorbing chain math `B = (I - Q)^-1 * R`, read Start→Conversion cell. Matrix inversion via Gauss-Jordan (pivot threshold 1e-12)
5. **Removal effect per state:** redirect all inbound edges to Null, zero the state's row, recompute conversion probability. `effect = max(baseline - modified, 0)`
6. **Attribution:** `attr[state] = effect / sum(all_effects) * total_conversions`
7. **Aggregate:** smc-level attribution rolled up to channel level via `_aggregate_to_channels`

### Output
Dict `{channel_name: fractional_conversions}` per stage.

### Position Weighting (applied after Markov)
```
1 touchpoint:  weight = 1.0
2 touchpoints: weight = 0.5 each
3+ touchpoints: first = 0.4, last = 0.4, each middle = 0.2 / (n - 2)
```
Final: `attribution_weight = position_weight * max(markov_channel_share, 0.01)`

Where `markov_channel_share = channel_attributed / stage_total` (re-normalised to 0-1 per stage, not raw Markov output). The 0.01 floor ensures every touchpoint gets minimum weight even if its channel has near-zero Markov contribution.

### Degenerate cases
`run_markov` returns `{}` when: total_conversions==0, baseline<=0, total_effect==0, or matrix is singular. Downstream, empty dict makes all stage_weights default to 0, so `attribution_weight` collapses to `position_weight * 0.01`.

### Lead Stage — Null Journey Injection
Lead attribution uses a different method because all CRM leads are "converted" at the Lead stage by definition. The pipeline injects synthetic null (non-converting) journeys sampled from GA4 sessions that did NOT produce a CRM lead. Sampling rate: `round(n/10)` per source (sources with <5 sessions may contribute zero null journeys due to rounding). Lead attribution is then rescaled to actual CRM lead count.

---

## Channel Classification Rules

Order matters — first match wins. Two copies must stay in sync: `channel_grouping.py` (pipeline) and `attribution-dashboard/utils/channel_grouping.py` (dashboard).

```
Rule                                                    → Channel
google source + "vd-" in campaign                       → PaidVideo
stackadapt source                                       → Display
compet|rival in campaign                                → CompetitorPaidSearch
offline medium                                          → Offline
(unknown) source + (unknown) medium                     → Unknown
(direct) source + (not set)|(none) medium               → Direct
gmb medium                                              → Local
organic medium                                          → OrganicSearch
(cpc|paid-social) medium + (facebook|tiktok|instagram)  → PaidSocial
social in medium                                        → Social
email medium                                            → Email
referral medium                                         → Referral
cpc|ppc|paidsearch medium:
  brand|branded in campaign or ad_product_group         → BrandedPaidSearch
  pmax|performance.max in campaign                      → PMaxPaidSearch
  compet|rival in campaign or ad_product_group          → CompetitorPaidSearch
  else                                                  → GenericPaidSearch
display|cpm|banner medium                               → Display
fallthrough                                             → (Other)
```

`classify_channel_extended` (in attribution_pipeline.py L379) routes `gmb` medium → Local, then delegates to `classify_channel`.

### Channel Colours
```
OrganicSearch=#2ecc71  Direct=#95a5a6  PaidSocial=#3498db  GenericPaidSearch=#e74c3c
BrandedPaidSearch=#e67e22  Referral=#9b59b6  Email=#1abc9c  Social=#34495e
Display=#f39c12  PaidVideo=#d35400  CompetitorPaidSearch=#8e44ad  PMaxPaidSearch=#2980b9
Offline=#7f8c8d  Unknown=#d5dbdb  Local=#27ae60  DemandGen=#c0392b  (Other)=#bdc3c7
```

---

## Currency

### Pipeline (ingestion — converts TO SGD for storage)
```
FX_RATES_TO_SGD = {SGD: 1.0, USD: 1.32, VND: 0.0000528}
```
Staleness check: abort if FX_RATES_UPDATED >35 days old, warn if >25 days. All spend stored in SGD.

Spend daily max thresholds (SGD): BCS=5,000  AIS=15,000  SAIS=15,000  ISHCMC=10,000

### Dashboard (display — converts FROM SGD for user)
```
FX_FROM_SGD = {SGD: 1.0, USD: 1/1.32, VND: 19500/1.32, GBP: 1/1.72}
```
User-selectable display currency. Dashboard includes GBP; pipeline does not. Both must be maintained independently.

---

## BQ Tables and Schemas

All tables are append-only with `pipeline_run_ts` column. Views serve latest complete run per school.

### attributed
One row per touchpoint per stage per journey. Only webform leads with digital signal (excludes offline and unknown).

| Column | Type | Description |
|--------|------|-------------|
| pipeline_run_ts | STRING | Pipeline run timestamp |
| school | STRING | School code (BCS, AIS, SAIS, ISHCMC) |
| journey_id | STRING | Unique lead identifier (e.g. BCS-0001) |
| date | STRING | Touchpoint date (GA4 session or CRM created_on for UTM-fallback) |
| channel_grouping | STRING | Classified marketing channel |
| source | STRING | Traffic source |
| medium | STRING | Traffic medium |
| campaign | STRING | Campaign name |
| stage | STRING | CRM stage (D1 Lead through D5 Enrolment) |
| stage_idx | INT | Stage number (0-4) |
| attribution_weight | FLOAT | position_weight * max(markov_weight, 0.01) |
| touchpoint | INT | Position in journey (1-based) |
| total_touchpoints | INT | Total touchpoints in journey |
| country | STRING | Country from GA4 first session |
| status | STRING | Won / Lost / Active |

### stitch_audit
One row per CRM lead (ALL leads including offline and unknown). The completeness picture.

| Column | Type | Description |
|--------|------|-------------|
| school | STRING | School code |
| d365_id | STRING | D365 CRM lead ID |
| journey_id | STRING | Mapped journey ID |
| cid | STRING | GA4 client ID extracted from CRM Journey ID field |
| user_pseudo_id | STRING | GA4 upid matched from CID (empty if no match) |
| bq_sessions_found | INT | GA4 sessions matched (0 = no match) |
| entry_type | STRING | webform or offline |
| first_touch_source | STRING | First touchpoint source (empty for offline/unknown) |
| first_touch_medium | STRING | First touchpoint medium |
| first_touch_campaign | STRING | First touchpoint campaign |
| first_touch_date | DATE | First touchpoint date (nullable) |
| created_on | STRING | CRM lead creation timestamp (cast to STRING for cross-school schema compat) |
| match_tier | STRING | CID matching method (tier1, tier1.5, tier2) |
| stage | STRING | CRM stage label |
| admission_status | STRING | CRM admission status |

### crm_leads_raw
One row per CRM lead (deduped by d365_id in view). Raw CRM fields for Lead Source Mix and survey comparison.

| Column | Type | Description |
|--------|------|-------------|
| school | STRING | School code |
| d365_id | STRING | D365 CRM lead ID |
| channel | STRING | CRM entry channel (Webform, Email, Phone, etc.) — NOT marketing channel |
| entry_type | STRING | webform or offline |
| created_on | STRING | CRM lead creation date |
| utm_source/medium/campaign | STRING | UTM parameters from form submission |
| stage_raw | STRING | Raw CRM stage value |
| admission_status | STRING | CRM admission status |
| country | STRING | Lead country (address → phone inference → default) |
| applied_grade | STRING | Grade applied for |
| applied_year | INT | Academic year |
| nationality | STRING | Lead nationality |
| journey_id | STRING | Mapped journey ID |
| cid | STRING | GA4 client ID extracted from Journey ID |
| status | STRING | Won / Lost / Active |

### spend_combined
One row per campaign per date. Google Ads + Meta Ads merged. All amounts in SGD.

| Column | Type | Description |
|--------|------|-------------|
| school | STRING | School code |
| platform | STRING | google or meta |
| publisher_platform | STRING | Meta placement (nullable) |
| date | STRING | Spend date |
| spend | FLOAT | Amount in SGD |
| campaign | STRING | Campaign name |
| channel_grouping | STRING | Classified channel |
| source | STRING | Traffic source |
| medium | STRING | Traffic medium |
| impressions | INT | Ad impressions |
| clicks | INT | Ad clicks |
| cpc | FLOAT | Cost per click in SGD |
| conversions | FLOAT | Platform-reported conversions |
| conversions_value | FLOAT | Platform-reported conversion value |

### journeys_stitched
One row per touchpoint per journey. Written by `save_journeys_to_bq`. Dashboard loads this as `journeys_raw`.

| Column | Type | Description |
|--------|------|-------------|
| pipeline_run_ts | STRING | Pipeline run timestamp |
| school | STRING | School code |
| journey_id | STRING | Unique lead identifier |
| touchpoint | INT | Position in journey (1-based) |
| total_touchpoints | INT | Total touchpoints in journey |
| source | STRING | Traffic source |
| medium | STRING | Traffic medium |
| campaign | STRING | Campaign name |
| channel_grouping | STRING | Classified marketing channel |
| date | TIMESTAMP | Touchpoint date |
| country | STRING | Country from GA4 session |
| max_stage | STRING | Highest CRM stage reached (NOT per-touchpoint) |
| max_stage_idx | INT | Highest stage index (0-4) |

Note: uses `max_stage`/`max_stage_idx` (journey-level), unlike `attributed` which uses `stage`/`stage_idx` (per-stage rows).

### Other tables
- **markov_channel_weights:** channel-level Markov weights per stage (summary)
- **crm_leads:** enrichment data (journey_id, admission_status, nationality, applied_grade, academic_year, address_country) — joined to journeys/attributed in dashboard loader
- **search_terms:** Google Ads search terms (school, search_term, keyword, campaign, match_type, impressions, clicks, cost, conversions) — no date column
- **landing_pages:** landing page performance — no date column in combined view
- **ad_lookups:** ad group / ad set level performance (platform, level, campaign_name, group_name, impressions, clicks, spend, click_share)
- **pipeline_runs:** run metadata (pipeline_run_ts, school, status, leads, webform, offline, matched, stitch_rate_pct, date_start, date_end, error)

### BQ View Architecture
Views are created by `create_all_views.py` (the canonical generator). It programmatically builds both per-school and combined views, introspecting each school's schema via `get_common_columns()` and auto-casting mismatched types. Three static SQL files also exist but are secondary references:

1. **Per-school views** (`create_powerbi_views.sql`): BCS-hardcoded (11 views for BCS only, not parameterised). Pattern: `SELECT * EXCEPT(pipeline_run_ts) FROM {table} WHERE CAST(pipeline_run_ts AS STRING) = (latest where status='complete')`. `v_crm_leads_raw` deduplicates by d365_id via ROW_NUMBER.

2. **All-schools script** (`create_powerbi_views_all_schools.sql`): same 11 views for all 4 schools (44 views total).

3. **Combined views** (`create_combined_views.sql`): `cognita_attribution` dataset. UNION ALL each school's per-school views with explicit column lists and CASTs for cross-school schema compatibility (BCS has cid as FLOAT64/created_on as TIMESTAMP; others have STRING).

**Warning:** The static SQL files and `create_all_views.py` cast `pipeline_run_ts` in opposite directions (STRING vs TIMESTAMP). Do not mix generators.

---

## Dashboard Architecture

### Authentication
`streamlit-authenticator` with role-based school access. Secrets structure: `credentials.usernames.{user}` (email, first_name, last_name, password, roles[]), `cookie` (name, key, expiry_days). Role = first role in list; if role matches a school code, sidebar locks to that school.

### Data Loading
Two paths controlled by `DATA_SOURCE` env var or `data_source` secret:
- **bigquery** (live): queries combined views in `cognita_attribution`, merges enrichment from `v_crm_leads`. Cache key: `_bq_run_ts()` queries `MAX(pipeline_run_ts)` from `v_pipeline_latest` — when a new pipeline run completes, the next page load auto-refreshes data (no manual version bumps). Streamlit Cloud still needs a manual reboot for code pushes (not data pushes)
- **csv** (fallback): reads from `data/school_data/` directory. Files: journeys_raw.csv, attributed.csv, spend.csv, search_terms.csv, landing_pages.csv, weekly_goals.csv, plus optional enrichment and ad lookup CSVs

### Filtering

**`apply_filters(df, filters, date_col="date", apply_channel=True)`**
Works on tables with a `date` column: attributed, journeys_raw, spend_combined.
```
mask = school.isin(schools) AND date >= start AND date <= end
if apply_channel: mask AND= channel_grouping.isin(channels)
```

**Manual filtering** for stitch_audit and crm_leads_raw (use `created_on`, not `date`):
```python
if "school" in df.columns and filters.get("schools"):
    df = df[df["school"].isin(filters["schools"])]
df["created_on"] = pd.to_datetime(df["created_on"], errors="coerce", utc=True).dt.tz_localize(None)
df = df[(df["created_on"] >= start) & (df["created_on"] < end + 1day)]
```

### Dashboard Pages

| Page | Data sources | Filters applied |
|------|-------------|----------------|
| Overview | attributed, journeys_raw, stitch_audit, crm_leads_raw, spend | See section detail below |
| Conversion Matrix | attributed | school + date + channel (also excludes Offline and (Other)) |
| Opportunities | attributed, spend, search_terms, landing_pages | attr: school+date+channel; spend: school+date only (apply_channel=False); search/landing: school only (no date column) |
| Journeys | journeys_raw | school + date + channel (also excludes Offline and (Other)) |
| CRM Journeys | journeys_raw + attributed | school + date + channel |
| Search Terms | search_terms | school only. Caption: "not affected by date filter" |
| Weekly Goals | weekly_goals CSV | school + custom week_start/week_end date filter |

---

## Overview Page — Section Detail

### 1. Data Completeness
**Source:** stitch_audit. **Filters:** school + date (manual). No channel filter.

Shows the full CRM picture — how many leads can/cannot be digitally attributed. Numbers here do NOT match the funnel or channel table (different population).

| Card | Formula |
|------|---------|
| Total Leads | `count(stitch_audit)` — all leads including offline |
| Full Attribution | `count where bq_sessions_found > 0 AND entry_type = webform` |
| Partial Attribution | `count where bq_sessions_found = 0 AND has non-trivial UTM AND entry_type = webform` |
| Offline | `count where entry_type != webform` |
| Unknown | `webform_count - full - partial` |
| Trackable Leads | `count where bq_sessions_found > 0 AND entry_type = webform` — Full Attribution only (excludes Partial/UTM-only) |
| Trackable % | `trackable_leads / webform_count * 100` |
| Avg Days to Lead | `mean(created_on - first_touch_date)` for full-attribution leads, clipped >= 0 |

### 2. Lead Source Mix
**Source:** stitch_audit left-joined to crm_leads_raw for `channel` column. **Filters:** school + date (manual). No channel filter.

Population is scoped to stitch_audit (latest pipeline run), so total always equals the Data Completeness "Total Leads" card. Unmatched leads show as "Unknown" in the mix. Stacked bar of CRM entry channels (Webform, Email, Phone, Portal, etc.).

### 3. Enrolment Funnel (Markov-Attributed)
**Source:** `attr = apply_filters(data["attributed"], filters)`. **Filters:** school + date + channel.

| Card | Formula | Source |
|------|---------|--------|
| Leads | `sum(attribution_weight) where stage = D1 Lead` | attr |
| Enquiries | `sum(attribution_weight) where stage = D2 Enquiry` | attr |
| Applications | `sum(attribution_weight) where stage = D3 Application` | attr |
| Offers | `sum(attribution_weight) where stage = D4 Offer` | attr |
| Enrolments | `sum(attribution_weight) where stage = D5 Enrolment` | attr |

All cards are Markov-attributed. When CRM data available: Leads card also shows `CRM: {total}` as context subtitle.

### 4. Channel Attribution Table
**Source:** `attr` (same filtered dataframe as funnel). **Excludes:** Offline and Unknown from display.

| Column | Formula |
|--------|---------|
| Leads | `sum(attribution_weight) where stage = D1 Lead` per channel |
| Enquiries | `sum(attribution_weight) where stage = D2 Enquiry` per channel |
| Enquiry Rate | `enquiries / leads * 100` per channel (quality signal, NOT true conversion rate) |
| Enrolments | `sum(attribution_weight) where stage = D5 Enrolment` per channel |

**RULE: Table Total row must equal funnel card values.** Same data, same filters, same exclusions.

### 5. Cost Efficiency
**Source:** spend (apply_channel=False) + attr for counts. **Filters:** school + date. No channel.
**Behaviour:** Hides entirely when channel filter is active.

| KPI | Formula |
|-----|---------|
| Paid Ad Spend | `sum(spend)` |
| CPL | `total_spend / leads` |
| CPEn | `total_spend / enquiries` |
| CPEnrol Google | `google_spend / attr D5 Enrolment where channel in (GenericPaidSearch, BrandedPaidSearch, PMaxPaidSearch, CompetitorPaidSearch)` — N/A when < 1 attributed enrolment |
| CPEnrol Meta | `meta_spend / attr D5 Enrolment where channel = PaidSocial` — N/A when < 1 attributed enrolment |
| Leads/1k | `leads / total_spend * 1000` |

### 6. Attribution by Channel (Donut)
**Source:** attr, D1 Lead stage. **Excludes:** Offline, (Other), Unknown.

### 7. Leads Over Time
**Source:** attr, all stages. Weekly aggregation.

### 8. Top Sources of Enquiries
**Source:** attr, D2 Enquiry. **Excludes:** Offline, (Other), Unknown. Top 20 by campaign x channel.

### 9. Country Distribution
**Source:** journeys_raw, first touchpoint country. Bar chart.

### 10. Survey vs Digital Attribution (dormant)
**Activates when:** `heard_about` column exists in crm_leads_raw.
**Known issues to fix before activation:**
- Line 80: `apply_filters(crm_raw)` will crash — crm_leads_raw has `created_on` not `date`. Fix: manual filtering.
- Line 106: `attr["d365_id"]` will crash — attributed has no d365_id. Fix: join through journey_id.

---

## Design Decisions

### Why Offline is excluded from attribution
No digital touchpoints. Cannot match to GA4 sessions. Markov needs a channel path. Logged in stitch_audit for completeness only.

### Why Unknown is excluded from attribution
source=(unknown), medium=(unknown) means no GA4 sessions and no UTM parameters. A single-touchpoint "Unknown" journey contributes no signal to the Markov transition matrix. Same logic as offline.

### Why Enquiry Rate is not a conversion rate
Markov assigns credit independently per stage. Leads and Enquiries attributed to the same channel are two independent calculations. Their ratio is a quality signal, not a progression rate.

### Why CPEnrol is split by platform
Single CPEnrol dividing total spend by total enrolments double-counts. Split: Google Ads spend / Paid Search enrolments, Meta Ads spend / Paid Social enrolments.

### Why cost efficiency hides on channel filter
Ad spend cannot be split by attribution channel grouping. Filtered leads against unfiltered spend = wrong CPL.

### Card-to-table consistency rule
Funnel cards and channel table use the same `attr` dataframe with the same filters. If the table excludes channels, cards must apply the same exclusion. Mismatches undermine stakeholder trust.

---

## Deployment

### Push workflow
```bash
gh auth switch --user mktgasia-cognita
git -C /path/to/attribution-dashboard push origin main
gh auth switch --user urbanonesg
```
Streamlit Cloud auto-deploys on push.

### Dependencies (requirements.txt)
```
streamlit==1.59.1
streamlit-authenticator==0.4.2
plotly==5.24.1
pandas==2.3.3
numpy==2.4.6
matplotlib==3.11.0
google-cloud-bigquery==3.42.2
db-dtypes==1.7.1
bcrypt==5.0.0
```

### Streamlit secrets structure
```toml
data_source = "bigquery"
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key = "..."
# ... standard GCP SA fields

[credentials.usernames.{user}]
email = "..."
first_name = "..."
last_name = "..."
password = "$2b$12$..."   # bcrypt hash
roles = ["BCS"]           # or ["cognita"] for all-school access

[cookie]
name = "..."
key = "..."
expiry_days = 7
```

---

## File Locations

| Component | Path |
|-----------|------|
| Pipeline | `Cognita/data-dashboards/attribution_pipeline.py` |
| Markov algorithm | `Cognita/data-dashboards/markov_attribution.py` |
| Channel grouping (pipeline) | `Cognita/data-dashboards/channel_grouping.py` |
| Channel grouping (dashboard) | `attribution-dashboard/utils/channel_grouping.py` |
| View generator (canonical) | `Cognita/data-dashboards/create_all_views.py` |
| Per-school views SQL (BCS ref) | `Cognita/data-dashboards/create_powerbi_views.sql` |
| All-schools views SQL | `Cognita/data-dashboards/create_powerbi_views_all_schools.sql` |
| Combined views SQL | `Cognita/data-dashboards/create_combined_views.sql` |
| Dashboard app | `attribution-dashboard/app.py` |
| Filter logic | `attribution-dashboard/utils/filters.py` |
| Currency (display) | `attribution-dashboard/utils/currency.py` |
| BQ data loader | `attribution-dashboard/data/bigquery.py` |
| CSV fallback loader | `attribution-dashboard/data/real_data.py` |
| Overview view | `attribution-dashboard/views/overview.py` |
| This spec | `attribution-dashboard/docs/dashboard-spec.md` |

## Rebuild Gotchas

1. **Two channel_grouping.py files** — pipeline and dashboard copies must stay in sync manually
2. **Two FX rate tables** — pipeline `FX_RATES_TO_SGD` (ingestion, no GBP) vs dashboard `FX_FROM_SGD` (display, includes GBP). Both need independent maintenance
3. **stitch_audit created_on is STRING** — cast from TIMESTAMP for cross-school schema compatibility. Dashboard must parse with `pd.to_datetime(errors="coerce", utc=True).dt.tz_localize(None)`
4. **BQ table suffix bounds** — GA4 session queries use literal-interpolated date suffixes (not parameterised) for table pruning. CIDs passed as ArrayQueryParameter
5. **Append-only tables** — views filter to latest complete run. Never delete rows; re-run the pipeline to produce new rows with a fresh pipeline_run_ts
