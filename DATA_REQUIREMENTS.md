# BCS Attribution Dashboard — Data Requirements

## Core Data (Phase 1-3 Pipeline)

| File | Source | Pipeline Phase |
|---|---|---|
| `journeys_raw.csv` | BigQuery + D365 stitch | Phase 1 |
| `attributed.csv` | Markov attribution model | Phase 2 |
| `markov_results.csv` | Markov channel weights | Phase 2 |
| `spend.csv` | Google Ads + Meta Ads APIs | Phase 3 |
| `search_terms.csv` | Google Ads search terms report | Phase 3 |
| `landing_pages.csv` | GA4 landing page report | Phase 3 |
| `weekly_goals.csv` | Manual targets | Manual |
| `d365_bq_stitched.csv` | BigQuery + D365 join | Phase 1 |

## Ad-Level Lookups (Phase 4)

| File | Source | API | Date Range |
|---|---|---|---|
| `google_adgroup_lookup.csv` | Google Ads GAQL | `run_gaql` (account `9424958631`) | Align to attributed.csv |
| `meta_adset_lookup.csv` | Meta Ads Insights | `get_insights` per campaign (account `act_719913488541244`) | Align to attributed.csv |
| `campaign_name_map.csv` | Manual mapping | Cross-reference GA4 campaign names with platform names | N/A |

### Google Ads GAQL Query

```sql
SELECT campaign.name, ad_group.name, metrics.clicks, metrics.impressions, metrics.cost_micros
FROM ad_group
WHERE segments.date BETWEEN '{start}' AND '{end}'
```

Aggregate by campaign.name + ad_group.name. Compute `click_share = clicks / campaign_total_clicks`.

Note: PMax campaigns return minimal ad group data. These fall back to campaign-level display.

### Meta Ads Fetch Sequence

1. `get_campaign_performance` at campaign level → campaign IDs + names
2. `list_ad_sets` for account → ad set IDs + names + campaign_id mapping
3. `get_insights` per campaign_id at adset level → adset_id + metrics
4. Join insights with list_ad_sets by adset_id to get names
5. Compute `click_share = clicks / campaign_total_clicks`

Note: Meta Insights API strips entity names from results — join with list endpoints required.

### Campaign Name Map

GA4 uses tracking template names; ad platforms use their own names. The map bridges these.
Update whenever new campaigns are added. Unmapped campaigns fall back to campaign-level display.

## Validation Checks

- `click_share` sums to 1.0 (±0.01) per campaign in each lookup
- All GA4 paid campaigns in attributed.csv have a campaign_name_map entry
- Lookup CSV date ranges align with attributed.csv date range

## Account IDs

- Google Ads BCS: `9424958631`
- Meta Ads BCS: `act_719913488541244`
- GA4 BCS: `249899399`
