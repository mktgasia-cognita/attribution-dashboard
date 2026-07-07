# BCS Attribution Dashboard - Data Refresh Guide

How to update the dashboard data without modifying the dashboard code. All files go in `data/bcs_real/`.

## Account IDs

| Platform | Account ID |
|----------|-----------|
| Google Ads BCS | `9424958631` |
| Meta Ads BCS | `act_719913488541244` |
| GA4 BCS | `249899399` |

---

## Core Data Files (11 CSVs)

### 1. `journeys_raw.csv` (Phase 1 - BQ + D365 stitch)

Source: BigQuery GA4 sessions joined with D365 CRM stages.

| Column | Type | Description |
|--------|------|-------------|
| journey_id | string | D365 opportunity ID |
| school | string | Always `BCS` |
| touchpoint | int | Touchpoint position in journey (1-based) |
| total_touchpoints | int | Total touchpoints for this journey |
| date | date (YYYY-MM-DD) | Session date |
| channel_grouping | string | Channel label (see Channel Values below) |
| source | string | GA4 source |
| medium | string | GA4 medium |
| campaign | string | GA4 campaign name |
| country | string | User country |
| max_stage | string | Highest CRM stage reached (see Stage Values below) |
| max_stage_idx | int | Stage index (1-5) |
| status | string | `Active`, `Won`, or `Lost` |
| closed_reason | string | Loss reason (nullable) |

### 2. `attributed.csv` (Phase 2 - Markov model output)

Source: Markov attribution model run on journeys_raw.

| Column | Type | Description |
|--------|------|-------------|
| journey_id | string | D365 opportunity ID |
| school | string | Always `BCS` |
| date | date (YYYY-MM-DD) | Session date |
| channel_grouping | string | Channel label |
| source | string | GA4 source |
| medium | string | GA4 medium |
| campaign | string | GA4 campaign name |
| country | string | User country |
| touchpoint | int | Touchpoint position |
| total_touchpoints | int | Total touchpoints |
| stage | string | Stage being attributed (see Stage Values) |
| stage_idx | int | Stage index (1-5) |
| attribution_weight | float | Markov-attributed weight for this touchpoint+stage |
| status | string | `Active`, `Won`, or `Lost` |
| closed_reason | string | Loss reason (nullable) |

### 3. `d365_bq_stitched.csv` (Phase 1 - join audit)

Source: D365 CRM records matched to BigQuery GA4 sessions.

| Column | Type | Description |
|--------|------|-------------|
| d365_id | string | D365 record ID |
| journey_id | string | Opportunity ID |
| cid | string | GA4 client ID |
| user_pseudo_id | string | GA4 user pseudo ID |
| stage | string | CRM stage |
| admission_status | string | Admission status |
| created_on | datetime | Record creation date |
| bq_sessions_found | int | Number of matched BQ sessions |
| first_touch_source | string | First-touch source |
| first_touch_medium | string | First-touch medium |
| first_touch_campaign | string | First-touch campaign |
| first_touch_date | date | First-touch date |

### 4. `markov_results.csv` (Phase 2 - channel weights)

Source: Markov model channel-level attribution weights.

| Column | Type | Description |
|--------|------|-------------|
| channel | string | Channel grouping label |
| stage | string | Stage name |
| attributed_conversions | float | Attributed conversion count |
| percentage | float | Share of conversions for this stage |

### 5. `spend.csv` (Phase 3 - ad platform spend)

Source: Google Ads + Meta Ads campaign performance APIs.

| Column | Type | Description |
|--------|------|-------------|
| school | string | Always `BCS` |
| campaign | string | Campaign name (must match GA4 campaign names) |
| spend | float | Spend in SGD |
| impressions | int | Total impressions |
| clicks | int | Total clicks |
| conversions | float | Platform-reported conversions |
| conversions_value | float | Conversion value |
| date | date (YYYY-MM-DD) | Reporting date |
| channel_grouping | string | Channel label |
| source | string | Platform source |
| medium | string | Platform medium |
| cpc | float | Cost per click |

### 6. `search_terms.csv` (Phase 3 - Google Ads)

Source: Google Ads search terms report via `run_gaql`.

| Column | Type | Description |
|--------|------|-------------|
| school | string | Always `BCS` |
| search_term | string | Actual search query |
| keyword | string | Matched keyword |
| campaign | string | Campaign name |
| match_type | string | Keyword match type |
| cost | float | Cost in SGD |
| clicks | int | Clicks |
| impressions | int | Impressions |
| conversions | float | Conversions |

### 7. `landing_pages.csv` (Phase 3 - GA4)

Source: GA4 landing page report via `ga4_run_report`.

| Column | Type | Description |
|--------|------|-------------|
| school | string | Always `BCS` |
| landing_page | string | Landing page path |
| sessions | int | Sessions |
| users | int | Users |
| conversions | float | Conversions |
| conversion_rate | float | Conversion rate (0-1) |
| bounce_rate | float | Bounce rate (0-1) |
| avg_session_duration | float | Avg session duration (seconds) |

### 8. `weekly_goals.csv` (Manual)

Source: Manually maintained weekly targets vs actuals.

| Column | Type | Description |
|--------|------|-------------|
| school | string | Always `BCS` |
| week_start | date (YYYY-MM-DD) | Week start date |
| week_end | date (YYYY-MM-DD) | Week end date |
| lead_target | int | Lead target |
| lead_actual | int | Actual leads |
| spend_target | float | Spend target (SGD) |
| spend_actual | float | Actual spend (SGD) |
| cpa_target | float | CPA target (SGD) |
| cpa_actual | float | Actual CPA (SGD) |

---

## Ad-Level Lookup Files (Phase 4)

These are optional - the dashboard falls back to campaign-level display when missing.

### 9. `google_adgroup_lookup.csv`

Source: Google Ads GAQL query on account `9424958631`.

```sql
SELECT campaign.name, ad_group.name, metrics.clicks, metrics.impressions, metrics.cost_micros
FROM ad_group
WHERE segments.date BETWEEN '{start}' AND '{end}'
```

| Column | Type | Description |
|--------|------|-------------|
| campaign_name | string | Google Ads campaign name |
| ad_group_name | string | Ad group name |
| clicks | int | Clicks |
| impressions | int | Impressions |
| spend | float | Spend (convert cost_micros / 1,000,000) |
| click_share | float | clicks / campaign_total_clicks (must sum to 1.0 per campaign) |

Note: PMax campaigns return minimal ad group data and fall back to `[campaign_name]` display.

### 10. `meta_adset_lookup.csv`

Source: Meta Ads API on account `act_719913488541244`.

Fetch sequence:
1. `list_ad_sets` for account -> ad set IDs + names + campaign_id
2. `get_insights` per campaign at adset level -> adset_id + metrics
3. Join by adset_id to get names
4. Compute click_share per campaign

| Column | Type | Description |
|--------|------|-------------|
| campaign_name | string | Meta campaign name |
| ad_set_name | string | Ad set name |
| clicks | int | Clicks |
| impressions | int | Impressions |
| spend | float | Spend |
| click_share | float | clicks / campaign_total_clicks (must sum to 1.0 per campaign) |

### 11. `campaign_name_map.csv`

Source: Manual mapping between GA4 tracking names and ad platform names.

| Column | Type | Description |
|--------|------|-------------|
| ga4_campaign | string | Campaign name as it appears in GA4 / `attributed.csv` |
| platform_campaign | string | Campaign name as it appears in Google Ads or Meta Ads |
| platform | string | `google` or `meta` |

Update whenever new campaigns are created. Unmapped campaigns show with `[campaign_name]` prefix.

---

## Hardcoded Value References

### Stage Values (order matters)
1. `D1 Lead`
2. `D2 Enquiry`
3. `D3 Application`
4. `D4 Offer`
5. `D5 Enrolment`

### Channel Grouping Values
`OrganicSearch`, `Direct`, `PaidSocial`, `BrandedPaidSearch`, `GenericPaidSearch`, `CompetitorPaidSearch`, `PMaxPaidSearch`, `Referral`, `Email`, `Social`, `Display`, `Offline`, `Local`, `(Other)`, `Other`

### AI Referral Sources (detected in Journeys view)
`chatgpt.com`, `perplexity.ai`, `claude.ai`, `gemini.google.com`, `copilot.microsoft.com`

---

## Validation Checklist

Before replacing data files:

- [ ] `click_share` sums to 1.0 (+-0.01) per campaign in `google_adgroup_lookup.csv`
- [ ] `click_share` sums to 1.0 (+-0.01) per campaign in `meta_adset_lookup.csv`
- [ ] All paid campaigns in `attributed.csv` have an entry in `campaign_name_map.csv`
- [ ] All date columns parse as YYYY-MM-DD
- [ ] `school` column is consistently `BCS` across all files
- [ ] `stage` values match the 5 hardcoded stages exactly
- [ ] `channel_grouping` values match the hardcoded set (no spaces in compound names)
- [ ] `attributed.csv` date range aligns with lookup CSV date ranges
- [ ] `weekly_goals.csv` week ranges cover the attributed.csv date range

## Refresh Procedure

1. Run BQ+D365 stitch pipeline -> `d365_bq_stitched.csv`, `journeys_raw.csv`
2. Run Markov attribution model -> `attributed.csv`, `markov_results.csv`
3. Pull ad platform data -> `spend.csv`, `search_terms.csv`
4. Pull GA4 landing pages -> `landing_pages.csv`
5. Update weekly goals -> `weekly_goals.csv`
6. Pull ad-level lookups -> `google_adgroup_lookup.csv`, `meta_adset_lookup.csv`
7. Update campaign name map if new campaigns exist -> `campaign_name_map.csv`
8. Run validation checklist
9. Replace files in `data/bcs_real/`, commit, push
