# Runbook, verified state, and progress

[Project overview](../README.md) · [Data model and metrics](data-model.md) · [Power BI report](report.md)

## Current state

Stages 1 and 2 are complete: six linked synthetic CSV sources were loaded into BigQuery Bronze, six Silver tables and two Gold marts were built with Dataform, and the four-page Power BI Desktop project was generated. Campaign analysis, the budget decision memo, and a refreshed Incrementality screenshot remain open. The current source is a static August 2026 snapshot; there is no recurring ingestion or refresh schedule.

| # | Resource | Location |
|---:|---|---|
| 1 | Google Cloud project and region | `bq-dataform-sg`, `asia-southeast1` (Singapore) |
| 2 | [BigQuery project](https://console.cloud.google.com/bigquery?project=bq-dataform-sg) | [Bronze](https://console.cloud.google.com/bigquery?project=bq-dataform-sg&d=apac_meta_bronze&page=dataset), [Silver](https://console.cloud.google.com/bigquery?project=bq-dataform-sg&d=apac_meta_silver&page=dataset), [Gold](https://console.cloud.google.com/bigquery?project=bq-dataform-sg&d=apac_meta_gold&page=dataset), and `apac_meta_assertions` datasets |
| 3 | [Dataform workspace](https://console.cloud.google.com/bigquery/dataform/locations/asia-southeast1/repositories/apac-metasearch-performance/workspaces/development?project=bq-dataform-sg) | Repository `apac-metasearch-performance`, workspace `development` |
| 4 | Dataform runner | `apac-metasearch-dataform@bq-dataform-sg.iam.gserviceaccount.com`; Bronze read, Silver/Gold/assertions write, and BigQuery Job User |
| 5 | Local deployment files | [Bronze loader](../load_bronze.py), [Dataform cloud helper](../dataform/cloud_api.py), [SQLX definitions](../dataform/definitions/) |
| 6 | [Power BI Desktop project](../bi/APAC_Metasearch_Analytics/APAC_Metasearch_Analytics.pbip) | [Gold export](../bi/export_gold.py), [project builder](../bi/build_powerbi.py), [CSV snapshots](../bi/snapshot/) |

### First BigQuery query

A table reference needs all three parts, `project.dataset.table`. Enclose this project's hyphenated ID in backticks:

```sql
SELECT *
FROM `bq-dataform-sg.apac_meta_bronze.ad_click_events`
LIMIT 100;
```

For the KPI-ready campaign mart:

```sql
SELECT *
FROM `bq-dataform-sg.apac_meta_gold.gold_campaign_daily`
ORDER BY date, market, channel, campaign_id, device_type
LIMIT 100;
```

## Verified cloud snapshot (2026-09-20, Asia/Bangkok)

| # | Check | Result |
|---:|---|---|
| 1 | Bronze source counts | 930 platform rows, 39,171 clicks, 36,792 sessions, 2,034 bookings, 150,000 experiment assignments, and 150,000 user outcomes. |
| 2 | Dataform execution | Invocation `1789905980-ef8a4782-fceb-4dbf-8e8e-c75ce1e89ab6` succeeded: 31 actions, including 23 assertions, with zero failed or skipped. |
| 3 | Gold Campaign Daily | 930 rows, 39,171 clicks, 35,377 attributed sessions, 1,792 confirmed paid conversions, USD 28,062.17 spend, USD 296,589.98 booking value, USD 37,081.33 gross margin. |
| 4 | Gold Incrementality Experiment | 15 experiments, 5,000 assigned users per arm per experiment, 656 incremental conversions, USD 145,309.26 incremental booking revenue. This is a separate synthetic population. |

The first Dataform execution caught 28 booking-margin rounding mismatches and correctly skipped Gold. The [generator](../generate_data.py) now uses decimal `ROUND_HALF_UP`, matching the BigQuery check. These snapshot figures reflect the last verified run; check the cloud workflow before calling them current.

## Validate and rebuild

Python 3.10+ is required. The data generator uses the default seed `42` and supports `--seed`, `--start-date`, `--days`, and `--output`. Run from the repository root:

```powershell
python generate_data.py --validate-only
```

Validation checks schemas, unique IDs, references, click and conversion reconciliation, booking margin, 5,000 eligible users per experiment arm, and assignment/outcome rules. To regenerate and redeploy the same snapshot, use authenticated Google Cloud and BigQuery CLIs:

```powershell
python generate_data.py
python load_bronze.py
python dataform/cloud_api.py sync
python dataform/cloud_api.py run
python dataform/cloud_api.py status
```

The `run` command starts an asynchronous invocation. Repeat `status` until it reports `SUCCEEDED`. The active `gcloud` default project on this computer was not `bq-dataform-sg` during deployment, so always specify the intended project in direct cloud commands. The one-time `grant-access` action in [cloud_api.py](../dataform/cloud_api.py) sets dataset permissions for the existing runner.

`load_bronze.py` replaces the six active Bronze tables and removes the retired aggregate experiment source after a complete successful load. Dataform then rebuilds Silver and Gold. The local [Dataform files](../dataform/) are the SQL and workflow source of truth. `sync` overwrites matching cloud development-workspace files and removes retired experiment definitions; copy any cloud-only edits back before syncing. The Dataform repository itself is not connected to GitHub, while this project repository tracks the local SQLX. The helper stores the last invocation in ignored `dataform/.last_invocation.json`.

## Refresh the report

After a successful warehouse run, close Power BI Desktop, then run:

```powershell
python dataform/cloud_api.py dashboard-status
python bi/export_gold.py
python bi/build_powerbi.py
Start-Process 'bi\APAC_Metasearch_Analytics\APAC_Metasearch_Analytics.pbip'
```

Use **Home > Refresh** in Power BI Desktop to load the CSV Import tables. The Power BI project does not version its local Import cache. The checked-in snapshots make the project portable without Google credentials, although its generated import paths point to this computer's project directory and must be adjusted after cloning elsewhere. Do not add service-account keys to Git. A production version could use the Power BI Google BigQuery connector and scheduled Power BI Service refresh; this demo has neither.

The [report guide](report.md#screenshot-reconciliation-issue-to-resolve) records an unresolved mismatch between the user-supplied Incrementality screenshot and the current Gold snapshot. Reconcile the Desktop model before using its experiment KPI cards as evidence.

## Handoff for Codex or Claude Code

Read the [project overview](../README.md), [data model](data-model.md), and [report guide](report.md), then inspect the current BigQuery/Dataform state before changing cloud resources. Continue with campaign analysis and the budget decision memo.

1. Run local validation and inspect the Dataform status. On a fresh clone without `.last_invocation.json`, inspect the deployed Dataform repository in project `bq-dataform-sg`, region `asia-southeast1`.
2. Investigate `CMP003` in [Gold Campaign Daily SQLX](../dataform/definitions/gold_campaign_daily.sqlx) and BigQuery. Compare click-through rate, session rate, conversion rate, cost per acquisition, return on ad spend, margin return, and device splits with Thailand peers and the same channel in Indonesia/Singapore. Record evidence and recommended action here.
3. Recompute the 15 experiment results from assignments and outcomes using `experiment_id` + `user_id`; review lift and uncertainty. Keep experiment revenue separate from campaign margin.
4. Refresh the Desktop model so the Incrementality page reads the 15-row Gold snapshot, and replace the screenshot when the visible totals match.
5. Write the budget decision memo. Record each major result and next action in this log. Keep the project at five Markdown files or fewer.

Do not classify null click `session_id`, organic sessions, `CMP003`'s weak conversion rate, or bookings after August as dirty records: they are designed cases. Preserve the campaign daily grain before joining aggregates. If data or SQL changes, validate locally, reload Bronze, sync and run Dataform, and confirm all assertions before updating the verified snapshot.

## Progress log

| # | Date (Asia/Bangkok) | Achieved | Next |
|---:|---|---|---|
| 1 | 2026-09-19 | Created generator and five CSV outputs; validated relationships and designed campaign/market patterns. | Build warehouse-style SQL tables and an analytical KPI mart. |
| 2 | 2026-09-19 | Selected BigQuery ELT with Dataform quality gates as the target architecture. | Load Bronze tables, then implement Silver and Gold SQL. |
| 3 | 2026-09-19 | Loaded five Bronze tables, built five Silver tables, two Gold marts, and 20 Dataform assertion actions; successful workflow execution had 27/27 actions pass. A gate initially caught 28 USD margin rounding errors and skipped Gold; fixed the generator using decimal rounding and reloaded. Gold campaign mart has 930 rows, 39,171 clicks, 1,792 conversions, and USD 37,081.33 gross margin. | Investigate CMP003 and derive market/device recommendations, then quantify experiment uncertainty. |
| 4 | 2026-09-19 | Consolidated the cloud snapshot, operational runbook, and Codex/Claude Code handoff into this README. Initialized the project Git repository and committed the baseline. | Stage 3: perform campaign/market/device analysis with reproducible SQL and record findings here. |
| 5 | 2026-09-19 | Generated an import-mode Power BI Desktop PBIP with a TMDL semantic model, 3 pages, 2 Gold-mart snapshots, DAX KPI measures, and a custom theme. Python compilation, 46 JSON/PBI definition files, and the TMDL model passed code-level validation. | Open and visually verify the report in Power BI Desktop; then complete the campaign and incrementality analysis. |
| 6 | 2026-09-20 | Fixed Power BI's case-insensitive measure/column collisions by renaming measures to `Total Impressions`, `Total Clicks`, `Total Sessions`, `CTR %`, `CVR %`, and `ROAS Multiple`; regenerated all definitions and passed code-level checks. Power BI Desktop opened the corrected PBIP without the prior definition error. | Visually inspect each rendered page and complete the campaign and incrementality analysis. |
| 7 | 2026-09-20 | Enabled multi-select plus Select all on every dashboard slicer. Diagnosed blank visuals as an empty local Power BI Import cache, refreshed the active model, and verified 930 Campaign rows, 15 Experiment rows, USD 28,062.17 spend, 1,792 bookings, and 1.32 margin ROAS with DAX. | Complete the campaign and incrementality analysis. |
| 8 | 2026-09-20 | Added the Power BI Data Quality Gate page. `build_powerbi.py` now derives eight reproducible checks from the Gold snapshots, writes a data-quality snapshot, adds the DataQuality semantic-model table and measures, and surfaces pass/fail evidence by category and severity. All eight current checks pass. | Complete the campaign and incrementality analysis. |
| 9 | 2026-09-20 | Reviewed all four report pages against the budget decision flow. Corrected the quality page's date label to historical period coverage and made the overall gate/count cards ignore category and severity filters. Recorded a prioritized report backlog with observed campaign and device evidence. | Add the loss-making segment action queue and a margin-versus-spend trend, then build the funnel and experiment uncertainty views. |
| 10 | 2026-09-20 | Completed the five report upgrades: decision action queue, gross-margin versus spend trend, funnel volume/rate and `CMP003` peer analysis, experiment sample-size/CI views, and Data Quality Gate integration with the latest Dataform workflow/assertion status plus refresh metadata. Regenerated the PBIP and snapshots; all 10 quality checks pass. | Refresh and visually review the report in Power BI Desktop, then use the evidence to write the budget decision memo. |
| 11 | 2026-09-20 | Replaced the 30-row aggregate experiment source with 150,000 assignments and 150,000 user-level outcomes: 15 experiments × 5,000 Treatment and 5,000 Control users. Added Bronze/Silver models and Dataform gates for arms and assignment/outcome integrity; rebuilt Gold, snapshots, and PBIP. The verified cloud invocation passed 31/31 actions with 23 assertions and zero problems. | Open the refreshed report, use the Incrementality page to trace the user-level calculation, then complete the campaign and experiment decision memo. |
| 12 | 2026-09-20 | Added a version-controlled white-background SVG that maps the six Bronze source tables through Silver transformations to the Campaign Daily and Incrementality Experiment Gold marts. Embedded it in this README for GitHub rendering. | Continue the Bronze → Silver → Gold technical walkthrough, then review DAX and TMDL. |
| 13 | 2026-09-20 | Polished this root README as the GitHub front page: added an at-a-glance overview, direct BigQuery/Dataform/Power BI links, and corrected copy-ready BigQuery table queries. | Complete the DAX and TMDL technical walkthrough, then write the budget decision memo from the Gold marts. |
| 14 | 2026-09-20 | Captured the refreshed Power BI Executive Pulse report and embedded the screenshot in this GitHub README. It shows populated cards, visualizations, and the action queue with all slicers set to All. | Complete the DAX and TMDL technical walkthrough, then write the budget decision memo from the Gold marts. |
| 15 | 2026-09-21 | Replaced the single Desktop-window capture with four clean report-canvas screenshots supplied from Power BI: Executive Pulse, Funnel and Campaign Diagnostics, Incrementality, and Data Quality Gate. Embedded all four in this README. | Complete the DAX and TMDL technical walkthrough, then write the budget decision memo from the Gold marts. |
| 16 | 2026-09-21 | Reworked the GitHub front page to start with the business objective and retain four report screenshots; moved the detailed data model, report, runbook, and full progress record into three linked guides. Identified the Incrementality screenshot mismatch against the 15-row Gold snapshot. | Reconcile the Power BI experiment totals, then complete campaign analysis and the budget decision memo. |
| 17 | 2026-09-27 | Traced the Incrementality screenshot to a stale Import cache holding the retired aggregate experiment (commit `f2994e5`, 600K users per arm). | Refresh Power BI and recapture the Incrementality and Data Quality pages. |
