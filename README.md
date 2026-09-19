# APAC Metasearch Performance Analytics

Interview practice project for a Senior Analyst, Digital Marketing role in travel. All records are **synthetic** and do not represent Traveloka, its users, or its actual campaigns.

## Objective and workflow

Follow `impression → ad click → first-party session → booking → revenue / margin`, then compare observational marketing KPIs with a separate randomized incrementality experiment.

| # | Stage | Status | Deliverable |
|---:|---|---|---|
| 1 | Generate linked synthetic data | Complete | Five CSV tables in [`data/`](data/) and deterministic [`generate_data.py`](generate_data.py) |
| 2 | Load to BigQuery and build ELT model | Complete | BigQuery Bronze/Silver/Gold datasets, Dataform SQL and quality gates |
| 3 | Analyze campaign, market, and device performance | Next | Findings and CMP003 investigation |
| 4 | Analyze experiment | Planned | Incremental conversions, relative lift, uncertainty, decision caveats |
| 5 | Build dashboard and interview case narrative | Planned | Refreshable visuals and recommendations |

## Data contract

| # | CSV / grain | Key and joins | Notes |
|---:|---|---|---|
| 1 | [`ad_platform_performance.csv`](data/ad_platform_performance.csv) — date × market × channel × campaign × device | `campaign_id` plus date/market/channel/device to click events | Includes impressions, clicks, USD ad spend, confirmed paid conversions. |
| 2 | [`ad_click_events.csv`](data/ad_click_events.csv) — one ad click | `click_id`; nullable `session_id` to sessions | A click may bounce before a session. A user can click repeatedly across sessions. |
| 3 | [`user_sessions.csv`](data/user_sessions.csv) — one session | `session_id`; `user_id` to bookings | Includes paid metasearch and organic sessions. |
| 4 | [`bookings.csv`](data/bookings.csv) — one booking | `booking_id`; `session_id` to sessions | Confirmed/paid, cancelled/refunded, and pending states. Booking can occur up to 72 hours after session. |
| 5 | [`incrementality_experiment.csv`](data/incrementality_experiment.csv) — experiment × arm | `experiment_id`, `experiment_group` | Separate randomized summary population; **do not join** to click/session/booking rows. |

The generator covers **2026-08-01 to 2026-08-31** across Thailand (`TH`), Indonesia (`ID`), Singapore (`SG`), five metasearch channels, and mobile/desktop. Campaigns `CMP001`–`CMP015` are each tied to one market and channel. All monetary columns (`ad_spend`, `booking_value`, `gross_margin`, experiment `revenue`) are synthetic **USD equivalents**; `commission_rate` is a fraction. `gross_margin` is booking value × commission rate for confirmed paid bookings, before ad spend. Cancelled and pending bookings have zero realized margin.

## Implemented BigQuery ELT architecture

The local Python generator remains the synthetic source. Load its five CSV files into BigQuery Bronze tables, preserving source values. Perform transformations in BigQuery using Dataform SQLX, with versioned definitions and dependencies:

| # | Layer | Implemented content and gate |
|---:|---|---|
| 1 | Bronze | Five source-shaped tables, load metadata, row-count and schema checks. |
| 2 | Silver | Typed timestamps/numerics, standardized statuses, paid-click/session/booking attribution, explicit handling for unmatched clicks and organic sessions; assertions for unique keys, references, valid ranges, temporal order, and platform reconciliation. |
| 3 | Gold | Campaign × click date × market × channel × device KPI mart plus a separate experiment mart; assert mart grain, nonnegative metrics, and reconciliation to Silver. |

Gold actions explicitly depend on upstream Dataform assertions, so a failed gate skips Gold refresh. The experiment mart is separate from observational attribution. The workflow has been run successfully by manual invocation; no recurring schedule is configured because the current source is a static CSV snapshot.

### Deployed resources and runbook

| # | Resource | Value |
|---:|---|---|
| 1 | GCP project / region | `bq-dataform-sg` / `asia-southeast1` (Singapore) |
| 2 | BigQuery datasets | `apac_meta_bronze`, `apac_meta_silver`, `apac_meta_gold`, `apac_meta_assertions` |
| 3 | Dataform repository / workspace | `apac-metasearch-performance` / `development` |
| 4 | Dataform runner | `apac-metasearch-dataform@bq-dataform-sg.iam.gserviceaccount.com`; dataset-scoped read on Bronze, write on Silver/Gold/assertions, project-scoped BigQuery Job User |
| 5 | Local deployment files | [`load_bronze.py`](load_bronze.py), [`dataform/cloud_api.py`](dataform/cloud_api.py), [`dataform/definitions/`](dataform/definitions/) |

[Open this GCP project in BigQuery](https://console.cloud.google.com/bigquery?project=bq-dataform-sg). The active `gcloud` default project on this computer was **not** `bq-dataform-sg` when this project was deployed. Always specify the project explicitly in cloud commands; do not change or use another GCP project by accident.

With an authenticated Google Cloud CLI and BigQuery CLI, rerun the snapshot and transformation from this directory:

```powershell
python generate_data.py
python load_bronze.py
python dataform/cloud_api.py sync
python dataform/cloud_api.py run
python dataform/cloud_api.py status
```

`run` starts an asynchronous Dataform invocation. Repeat `status` until it reports `SUCCEEDED`; an in-progress invocation reports `RUNNING`. The `grant-access` action in `cloud_api.py` is a one-time dataset access setup for the already created runner. `load_bronze.py` replaces only the five dedicated Bronze tables. Dataform rebuilds its dedicated Silver and Gold tables.

The local [`dataform/`](dataform/) files are the source of truth for SQL and workflow settings. `sync` **overwrites matching files in the cloud Dataform development workspace** with these local files; cloud-only edits should be copied back here before running it. The Dataform repository is not connected to an external Git remote. The project Git repository tracks local code, SQLX, documentation, and the five synthetic CSV files. The latest invocation name is also saved locally in `dataform/.last_invocation.json`, which is ignored by Git.

### Verified cloud snapshot (2026-09-19, Asia/Bangkok)

| # | Check | Result |
|---:|---|---|
| 1 | Bronze row counts | 930 platform rows; 39,171 clicks; 36,792 sessions; 2,034 bookings; 30 experiment-arm rows. Loader checked each cloud count against its CSV. |
| 2 | Dataform execution | Latest invocation `1789818176-60d85246-33c5-4ed1-9d06-e0a3e1cfd98c` in `SUCCEEDED` state; 27 actions, zero failed/skipped. |
| 3 | Gold campaign mart | 930 rows; 39,171 clicks; 35,377 attributed sessions; 1,792 confirmed paid conversions; USD 28,062.17 ad spend; USD 296,589.98 booking value; USD 37,081.33 gross margin. |
| 4 | Gold experiment mart | 15 experiments; 5,133 modeled incremental conversions and USD 819,365.71 modeled incremental revenue across separate synthetic experiment populations. Do not add these figures to observational campaign totals. |

The first Dataform execution caught 28 booking-margin rounding mismatches and skipped Gold as designed. [`generate_data.py`](generate_data.py) now uses decimal `ROUND_HALF_UP`, matching the BigQuery check; the latest complete run passed. There is **no scheduled refresh**, because the input is currently a static generated snapshot. Cloud resources already exist; [`cloud_api.py`](dataform/cloud_api.py) does not recreate datasets or the service account from scratch.

## Power BI Desktop dashboard

The version-controlled Power BI project is [`APAC_Metasearch_Analytics.pbip`](bi/APAC_Metasearch_Analytics/APAC_Metasearch_Analytics.pbip). It uses import-mode CSV snapshots of the two verified BigQuery Gold marts so the Desktop report can be opened without storing Google credentials in Git. [`export_gold.py`](bi/export_gold.py) refreshes those snapshots from BigQuery, while [`build_powerbi.py`](bi/build_powerbi.py) generates the PBIP, TMDL semantic model, page layout, visuals, and theme. The report's data model has two intentionally disconnected tables: `Campaign` and `Experiment`. It opened successfully in Power BI Desktop on 2026-09-20 after resolving all measure/column name collisions.

| # | Page | Storytelling question | Key visuals |
|---:|---|---|---|
| 1 | Executive Pulse | Is spend creating profitable bookings, and in which market? | Spend, bookings, margin ROAS, contribution cards; market margin ROAS; daily spend versus booking value. |
| 2 | Funnel & Campaign | At which point does performance break, and which campaign needs action? | CTR, session rate, CVR, CPA cards; campaign CTR and CVR comparisons; detailed campaign table. |
| 3 | Incrementality | Did advertising create additional demand? | Treatment versus control CVR, incremental conversions, incremental revenue; market and channel comparisons. |

The visual design uses a clean analyst dashboard treatment: a navy header (`#102A43`), teal for positive performance (`#00A6A6`), coral for attention or deterioration (`#F76C5E`), gold for neutral emphasis (`#F5B841`), a pale background, and consistent USD formatting. All pages include only relevant slicers. Core ratios are DAX measures calculated from aggregated numerators and denominators, so filters do not average daily ratios incorrectly. `CMP003` is named in the Funnel page as the designed high-CTR/low-CVR investigation case.

### Power BI runbook

```powershell
python bi/export_gold.py
python bi/build_powerbi.py
Start-Process 'bi\APAC_Metasearch_Analytics\APAC_Metasearch_Analytics.pbip'
```

The project opens in Power BI Desktop and loads local snapshot files from [`bi/snapshot/`](bi/snapshot/). When updating the snapshot or PBIP generation, close Power BI Desktop first, run both Python commands, then reopen the PBIP. Do not add credentials or service-account JSON to this repository. A later production-style version can change the model source to the Power BI Google BigQuery connector; this practice version deliberately keeps the reproducible, verified Gold snapshot local.

### KPI definitions and attribution

| # | Metric | Definition |
|---:|---|---|
| 1 | CTR | `clicks / impressions` |
| 2 | CPC | `ad_spend / clicks` |
| 3 | Platform CVR | `conversions / clicks`, where conversions count confirmed paid bookings assigned to the click's session |
| 4 | CPA | `ad_spend / conversions` |
| 5 | ROAS | Confirmed paid `booking_value / ad_spend` |
| 6 | Margin ROAS | Confirmed paid `gross_margin / ad_spend` |
| 7 | Incremental conversions | `eligible_users_treatment × (treatment conversions / treatment eligible_users − control conversions / control eligible_users)` |

For booking attribution, join each click to its session, then join bookings on `session_id`. There is at most one generated booking per session. Filter to `booking_status = 'confirmed'` and `payment_status = 'paid'` for realized value and margin. Some bookings happen after August; use the click date for campaign attribution. The platform conversions intentionally reconcile to those confirmed paid bookings at click date/market/channel/campaign/device grain. Avoid joining aggregated platform rows directly to booking rows without reaggregation, which would multiply spend and impressions.

## Designed patterns and limitations

- Indonesia has the largest traffic, lower CPC, and high booking volume. Singapore has lower traffic, higher CPC, and higher booking value. Thailand has a stronger baseline conversion propensity than Indonesia.
- Mobile has higher CTR and slightly lower session conversion propensity than desktop.
- `CMP003` deliberately has high CTR and low CVR, creating an investigation case.
- Clicks with no recorded session and organic sessions support realistic attribution checks.
- Experiment arms are generated as a separate synthetic summary. Their causal interpretation is a practice scenario; the experiment rows are not linked to the observational population. Revenue in that table is gross booking value, not commission or margin.
- This version has generated CSVs and deployed BigQuery/Dataform tables. It has no live ad platform feed, automated ingestion, dashboard, or scheduled refresh yet.

## Run and validate

Requires Python 3.10+ and no external packages. From this folder:

```powershell
python generate_data.py
python generate_data.py --validate-only
```

Optional parameters: `--seed`, `--start-date YYYY-MM-DD`, `--days`, and `--output`. The default seed is `42`. Regenerating with the same parameters produces the same data. Validation checks schemas, unique IDs, references, click and conversion reconciliation, booking margin, and both experiment arms.

## Handoff for Codex or Claude Code

Read this README first. Continue from **stage 3** in the workflow table; stages 1–2 are complete. Use the local files as the versioned source, and inspect the current BigQuery/Dataform state before changing cloud resources.

1. Run `python generate_data.py --validate-only` to verify the checked-in CSV snapshot. Run `python dataform/cloud_api.py status` to inspect the last locally recorded invocation; on a fresh clone that has no `.last_invocation.json`, inspect the Dataform repository `apac-metasearch-performance` in project `bq-dataform-sg`, region `asia-southeast1`.
2. Investigate `CMP003` using [`gold_campaign_daily.sqlx`](dataform/definitions/gold_campaign_daily.sqlx) and the BigQuery Gold table `bq-dataform-sg.apac_meta_gold.gold_campaign_daily`. Compare CTR, session rate, CVR, CPA, ROAS, margin ROAS, and device splits with other Thailand campaigns and the same channel in Indonesia/Singapore. Write findings and evidence into this README's progress log or an analysis section here.
3. Analyze the 15 experiment rows in `bq-dataform-sg.apac_meta_gold.gold_incrementality_experiment`. Estimate conversion-rate lift and uncertainty from treatment/control denominators. State that experiment revenue is gross booking value from a separate synthetic population, not first-party campaign revenue.
4. Build a dashboard and an interview narrative only after the analysis is checked. Document any chosen BI tool, refresh mechanism, and remaining limits here. Keep the total number of project Markdown files at five or fewer; extend this README instead of splitting the blueprint.

Do not treat null `ad_click_events.session_id`, organic sessions, `CMP003`'s weak CVR, or bookings after the click month as dirty data; they are designed cases. Preserve the campaign/day/market/channel/device grain before combining aggregated platform metrics with click or booking rows. If data or SQL changes, rerun local validation, reload Bronze, sync Dataform, run the workflow, and confirm all actions pass before updating the verified snapshot above.

## Progress log

| # | Date (Asia/Bangkok) | Achieved | Next |
|---:|---|---|---|
| 1 | 2026-09-19 | Created generator and five CSV outputs; validated relationships and designed campaign/market patterns. | Build warehouse-style SQL tables and an analytical KPI mart. |
| 2 | 2026-09-19 | Selected BigQuery ELT with Dataform quality gates as the target architecture. | Load Bronze tables, then implement Silver and Gold SQL. |
| 3 | 2026-09-19 | Loaded five Bronze tables, built five Silver tables, two Gold marts, and 20 Dataform assertion actions; successful workflow execution had 27/27 actions pass. A gate initially caught 28 USD margin rounding errors and skipped Gold; fixed the generator using decimal rounding and reloaded. Gold campaign mart has 930 rows, 39,171 clicks, 1,792 conversions, and USD 37,081.33 gross margin. | Investigate CMP003 and derive market/device recommendations, then quantify experiment uncertainty. |
| 4 | 2026-09-19 | Consolidated the cloud snapshot, operational runbook, and Codex/Claude Code handoff into this README. Initialized the project Git repository and committed the baseline. | Stage 3: perform campaign/market/device analysis with reproducible SQL and record findings here. |
| 5 | 2026-09-19 | Generated an import-mode Power BI Desktop PBIP with a TMDL semantic model, 3 pages, 2 Gold-mart snapshots, DAX KPI measures, and a custom theme. Python compilation, 46 JSON/PBI definition files, and the TMDL model passed code-level validation. | Open and visually verify the report in Power BI Desktop; then complete the campaign and incrementality analysis. |
| 6 | 2026-09-20 | Fixed Power BI's case-insensitive measure/column collisions by renaming measures to `Total Impressions`, `Total Clicks`, `Total Sessions`, `CTR %`, `CVR %`, and `ROAS Multiple`; regenerated all definitions and passed code-level checks. Power BI Desktop opened the corrected PBIP without the prior definition error. | Visually inspect each rendered page and complete the campaign and incrementality analysis. |
