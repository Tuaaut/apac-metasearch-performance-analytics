# Power BI report and interpretation

[Project overview and four screenshots](../README.md) · [Data model and metrics](data-model.md) · [Runbook and progress](operations.md)

## Report purpose

The [Power BI Desktop project](../bi/APAC_Metasearch_Analytics/APAC_Metasearch_Analytics.pbip) presents campaign economics, a funnel investigation, the separate incrementality experiment, and a data quality gate. The screenshots remain together on the [GitHub front page](../README.md#report-preview).

| # | Page | Decision question | Main visuals |
|---:|---|---|---|
| 1 | Executive Pulse | Is spend creating profitable bookings, and where should an analyst investigate? | Spend, bookings, gross margin return on ad spend, contribution, market comparison, daily margin versus spend, and segment action queue. |
| 2 | Funnel and Campaign | Where does the impression-to-booking journey weaken? | Stage volumes and rates, `CMP003` versus other Thailand campaigns, and campaign/device detail. |
| 3 | Incrementality | Did advertising create additional demand? | Treatment and Control users, conversion rates, rate difference, 95% confidence interval, incremental conversions, and revenue. |
| 4 | Data Quality Gate | Is the current snapshot trustworthy for a budget discussion? | Gate state, Dataform execution, import state, pass/fail counts, and check evidence. |

All slicers are dropdowns with multiple selection and Select all. Campaign, Experiment, DataQuality, FunnelStage, and RefreshMetadata are intentionally separate semantic-model tables. The campaign and experiment populations must remain separate in interpretation.

## Data source and semantic model

[Export script](../bi/export_gold.py) writes local CSV snapshots of the two verified BigQuery Gold marts into [`bi/snapshot/`](../bi/snapshot/). [Build script](../bi/build_powerbi.py) generates the Power BI project, Tabular Model Definition Language (TMDL) semantic model, Data Analysis Expressions (DAX) measures, page layouts, visuals, and theme. The Desktop report uses Import mode. A newly opened project needs **Home > Refresh** to populate its local cache; otherwise the slicers may have values while measure cards are blank.

TMDL defines tables, columns, types, measures, formats, partitions, and model structure. DAX is the formula language used inside measures such as gross margin return on ad spend and conversion rate. The report definition and [theme](../bi/theme.json) define page visuals, layout, and color. The theme uses navy (`#102A43`), teal (`#00A6A6`), coral (`#F76C5E`), and gold (`#F5B841`).

## Data Quality Gate

[Build script](../bi/build_powerbi.py) derives [eight local checks](../bi/snapshot/data_quality_checks.csv) from Gold snapshots: time coverage, Campaign and Experiment row counts, required campaign keys, campaign daily uniqueness, funnel and economic bounds, confirmed-booking reconciliation, and experiment arithmetic. Two more checks read the [recorded Dataform workflow and assertion outcome](../bi/snapshot/dataform_workflow_status.csv). The current stored gate says **PASS** for 10 checks, with 31 Dataform actions and 23 assertion actions completed and no problem actions.

This report page shows quality evidence. Dataform enforces the upstream block on a Gold rebuild. The page distinguishes the historical **Data Through Date**, the **Snapshot Export UTC** timestamp, and the Desktop **Import Model Status** so a static August 2026 dataset is not mistaken for a live feed.

## Decision features and evidence

| # | Feature | Evidence in the synthetic snapshot |
|---:|---|---|
| 1 | Segment action queue | `CMP003` (Thailand Skyscanner) has USD −2,808.86 contribution after spend; its mobile segment accounts for USD −2,252.85. Investigate before changing budget. |
| 2 | Economics trend | USD 37,081.33 gross margin is compared with USD 28,062.17 ad spend. Booking value alone is not a margin return. |
| 3 | Funnel diagnosis | `CMP003` has 4,925 clicks, 4,430 sessions, 86 confirmed paid bookings, and 1.75% click-to-booking conversion rate. |
| 4 | Experiment uncertainty | The report includes Treatment and Control denominators, absolute conversion-rate difference, and a two-sided normal-approximation 95% confidence interval. |
| 5 | Refresh evidence | Dataform workflow status, assertion result, snapshot export timestamp, and Desktop Import status appear on the quality page. |

The project currently covers August 2026 only. A prior period or budget target would be needed for a meaningful pacing or month-over-month view. Date filtering and campaign drillthrough are possible future report work.

## Screenshot reconciliation issue to resolve

The user-supplied Incrementality screenshot on the [front page](../README.md#report-preview) shows **600K Treatment users**, **600K Control users**, and **5K incremental conversions**. The checked-in [Gold experiment snapshot](../bi/snapshot/gold_incrementality_experiment.csv) has 15 experiment rows with **75,000 users per arm** and **656 incremental conversions**. The current [DAX definitions](../bi/APAC_Metasearch_Analytics/APAC_Metasearch_Analytics.SemanticModel/definition/tables/Experiment.tmdl) sum those Gold fields. The reason for the displayed eightfold difference has not been verified. Treat the screenshot as a layout preview and reconcile the Desktop Import model before using the Incrementality page as numerical evidence in an interview. The warehouse snapshot and Dataform result are the documented source values.

## Refresh procedure

Close Power BI Desktop before regenerating the project files. From the repository root, run the dashboard status export, Gold snapshot export, and project build, then reopen the PBIP and use **Home > Refresh**. The exact commands and cloud prerequisites are in the [runbook](operations.md#refresh-the-report). A local Import snapshot does not refresh on a schedule; there is currently no automated ingestion from the ad platforms or Power BI Service refresh.
