"""Generate a Power BI Desktop PBIP/PBIR report and TMDL model from Gold snapshots."""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "snapshot"
PROJECT = ROOT / "APAC_Metasearch_Analytics"
NAME = "APAC_Metasearch_Analytics"
REPORT = PROJECT / f"{NAME}.Report"
MODEL = PROJECT / f"{NAME}.SemanticModel"
THEME_FILE = "APACMetasearch-20260919.json"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"

PALETTE = {
    "navy": "#102A43", "teal": "#00A6A6", "coral": "#F76C5E",
    "gold": "#F5B841", "blue": "#377FB6", "pale": "#F6F8FC",
    "ink": "#243B53", "muted": "#627D98", "white": "#FFFFFF",
    "border": "#DCE6EF",
}

CAMPAIGN_COLUMNS = {
    "date": "dateTime", "market": "string", "channel": "string",
    "campaign_id": "string", "campaign_name": "string", "device_type": "string",
    "impressions": "int64", "clicks": "int64", "ad_spend": "decimal",
    "conversions": "int64", "sessions": "int64", "confirmed_bookings": "int64",
    "booking_value": "decimal", "gross_margin": "decimal", "ctr": "double",
    "cpc": "double", "cvr": "double", "cpa": "double", "roas": "double",
    "margin_roas": "double", "contribution_after_ad_spend": "decimal",
}
EXPERIMENT_COLUMNS = {
    "experiment_id": "string", "market": "string", "channel": "string",
    "treatment_users": "int64", "control_users": "int64",
    "treatment_conversions": "int64", "control_conversions": "int64",
    "treatment_revenue": "decimal", "control_revenue": "decimal",
    "treatment_conversion_rate": "double", "control_conversion_rate": "double",
    "incremental_conversions": "decimal", "relative_conversion_lift": "double",
    "incremental_revenue": "decimal",
}
QUALITY_COLUMNS = {
    "check_order": "int64", "category": "string", "check_name": "string",
    "severity": "string", "status": "string", "observed_value": "string",
    "expected_condition": "string", "failed_rows": "int64",
    "data_through_date": "dateTime", "evidence": "string",
}
FUNNEL_COLUMNS = {"stage_order": "int64", "stage": "string"}
REFRESH_COLUMNS = {
    "data_through_date": "dateTime", "snapshot_exported_utc": "dateTime",
    "dataform_workflow_state": "string", "dataform_completed_utc": "dateTime",
    "dataform_total_actions": "int64", "dataform_problem_actions": "int64",
    "dataform_assertion_actions": "int64", "dataform_problem_assertions": "int64",
    "powerbi_import_instruction": "string",
}
CAMPAIGN_MEASURES = {
    "Total Impressions": ("SUM(Campaign[impressions])", "#,0"),
    "Total Clicks": ("SUM(Campaign[clicks])", "#,0"),
    "Total Sessions": ("SUM(Campaign[sessions])", "#,0"),
    "Bookings": ("SUM(Campaign[conversions])", "#,0"),
    "Spend USD": ("SUM(Campaign[ad_spend])", "$#,0;($#,0)"),
    "Booking Value USD": ("SUM(Campaign[booking_value])", "$#,0;($#,0)"),
    "Gross Margin USD": ("SUM(Campaign[gross_margin])", "$#,0;($#,0)"),
    "Contribution USD": ("[Gross Margin USD] - [Spend USD]", "$#,0;($#,0)"),
    "CTR %": ("DIVIDE([Total Clicks], [Total Impressions])", "0.0%"),
    "Session Rate": ("DIVIDE([Total Sessions], [Total Clicks])", "0.0%"),
    "CVR %": ("DIVIDE([Bookings], [Total Clicks])", "0.0%"),
    "CPC USD": ("DIVIDE([Spend USD], [Total Clicks])", "$0.00"),
    "CPA USD": ("DIVIDE([Spend USD], [Bookings])", "$0.00"),
    "ROAS Multiple": ("DIVIDE([Booking Value USD], [Spend USD])", "0.00"),
    "Margin ROAS": ("DIVIDE([Gross Margin USD], [Spend USD])", "0.00"),
    "Booking per Session %": ("DIVIDE([Bookings], [Total Sessions])", "0.0%"),
    "Action Status": ("IF([Contribution USD] < 0, \"INVESTIGATE\", \"RETAIN / SCALE\")", "@"),
    "Import Model Status": ("IF(CALCULATE(COUNTROWS(Campaign), REMOVEFILTERS(Campaign)) = 0, \"NOT LOADED\", \"LOADED\")", "@"),
    "Thailand Peer CVR %": ("CALCULATE([CVR %], KEEPFILTERS(Campaign[market] = \"TH\"))", "0.0%"),
}
EXPERIMENT_MEASURES = {
    "Treatment Users": ("SUM(Experiment[treatment_users])", "#,0"),
    "Control Users": ("SUM(Experiment[control_users])", "#,0"),
    "Treatment CVR": ("DIVIDE(SUM(Experiment[treatment_conversions]), SUM(Experiment[treatment_users]))", "0.0%"),
    "Control CVR": ("DIVIDE(SUM(Experiment[control_conversions]), SUM(Experiment[control_users]))", "0.0%"),
    "CVR Difference pp": ("[Treatment CVR] - [Control CVR]", "0.00%"),
    "CVR Difference SE": ("SQRT(DIVIDE([Treatment CVR] * (1 - [Treatment CVR]), [Treatment Users]) + DIVIDE([Control CVR] * (1 - [Control CVR]), [Control Users]))", "0.00%"),
    "CVR Difference 95% Low": ("[CVR Difference pp] - 1.96 * [CVR Difference SE]", "0.00%"),
    "CVR Difference 95% High": ("[CVR Difference pp] + 1.96 * [CVR Difference SE]", "0.00%"),
    "Incremental Conversions": ("SUM(Experiment[incremental_conversions])", "#,0"),
    "Relative Lift": ("DIVIDE([Treatment CVR], [Control CVR]) - 1", "0.0%"),
    "Incremental Revenue USD": ("SUM(Experiment[incremental_revenue])", "$#,0;($#,0)"),
}
FUNNEL_MEASURES = {
    "Funnel Volume": ("SWITCH(SELECTEDVALUE(FunnelStage[stage]), \"Impressions\", [Total Impressions], \"Clicks\", [Total Clicks], \"Sessions\", [Total Sessions], \"Confirmed bookings\", [Bookings])", "#,0"),
    "Funnel Step Rate": ("SWITCH(SELECTEDVALUE(FunnelStage[stage]), \"Clicks\", [CTR %], \"Sessions\", [Session Rate], \"Confirmed bookings\", [Booking per Session %])", "0.0%"),
}
REFRESH_MEASURES = {
    "Dataform Workflow State": ("MAX(RefreshMetadata[dataform_workflow_state])", "@"),
    "Data Through Date": ("MAX(RefreshMetadata[data_through_date])", "mmm d, yyyy"),
    "Snapshot Export UTC": ("MAX(RefreshMetadata[snapshot_exported_utc])", "yyyy-mm-dd hh:mm:ss"),
}
QUALITY_MEASURES = {
    "Checks Evaluated": ("COUNTROWS(DataQuality)", "#,0"),
    "Checks Passed": ("CALCULATE(COUNTROWS(DataQuality), DataQuality[status] = \"PASS\")", "#,0"),
    "Checks Failed": ("CALCULATE(COUNTROWS(DataQuality), DataQuality[status] = \"FAIL\")", "#,0"),
    "Checks Unknown": ("CALCULATE(COUNTROWS(DataQuality), DataQuality[status] = \"UNKNOWN\")", "#,0"),
    "Affected Rows": ("SUM(DataQuality[failed_rows])", "#,0"),
    "Overall Checks Evaluated": ("CALCULATE(COUNTROWS(DataQuality), REMOVEFILTERS(DataQuality))", "#,0"),
    "Overall Checks Passed": ("CALCULATE([Checks Passed], REMOVEFILTERS(DataQuality))", "#,0"),
    "Overall Checks Failed": ("CALCULATE([Checks Failed], REMOVEFILTERS(DataQuality))", "#,0"),
    "Overall Checks Unknown": ("CALCULATE([Checks Unknown], REMOVEFILTERS(DataQuality))", "#,0"),
    "Gate Status": ("IF([Overall Checks Evaluated] = 0, \"NOT LOADED\", IF([Overall Checks Failed] > 0, \"FAIL\", IF([Overall Checks Unknown] > 0, \"UNKNOWN\", \"PASS\")))", "@"),
    "Latest Data Date": ("MAX(DataQuality[data_through_date])", "mmm d, yyyy"),
}


def uid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"apac-metasearch/{label}"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": f"'{value}'"}}}


def boolean(value: bool) -> dict:
    return {"expr": {"Literal": {"Value": str(value).lower()}}}


def color(value: str) -> dict:
    return {"solid": {"color": literal(value)}}


def field(table: str, property_name: str, kind: str) -> dict:
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": property_name}}


def projection(table: str, property_name: str, kind: str) -> dict:
    item = {"field": field(table, property_name, kind),
            "queryRef": f"{table}.{property_name}", "nativeQueryRef": property_name}
    if kind == "Column":
        item["active"] = True
    return item


def container_title(value: str) -> dict:
    return {"title": [{"properties": {"show": literal("true"), "text": literal(value)}}],
            "background": [{"properties": {"show": literal("true"), "color": color(PALETTE["white"])}}],
            "border": [{"properties": {"show": literal("true"), "color": color(PALETTE["border"])}}]}


def visual(name: str, visual_type: str, x: int, y: int, w: int, h: int,
           query_state: dict | None = None, title: str | None = None,
           objects: dict | None = None) -> dict:
    body: dict = {"visualType": visual_type}
    if query_state is not None:
        body["query"] = {"queryState": query_state}
    if objects:
        body["objects"] = objects
    if title:
        body["visualContainerObjects"] = container_title(title)
    return {
        "$schema": f"{SCHEMA}/item/report/definition/visualContainer/2.11.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 100 + len(name), "height": h,
                     "width": w, "tabOrder": 100 + len(name)},
        "visual": body,
    }


def textbox(name: str, value: str, x: int, y: int, w: int, h: int,
            font_size: int, background: str, foreground: str,
            bold: bool = False) -> dict:
    style = {"fontFamily": "Segoe UI", "fontSize": f"{font_size}pt", "color": foreground}
    if bold:
        style["fontWeight"] = "bold"
    result = visual(name, "textbox", x, y, w, h, objects={
        "general": [{"properties": {"paragraphs": [{"textRuns": [
            {"value": value, "textStyle": style}
        ]}]}}]
    })
    result["visual"]["visualContainerObjects"] = {
        "background": [{"properties": {"color": color(background)}}]
    }
    return result


def card(name: str, table: str, measure: str, x: int, y: int, w: int) -> dict:
    result = visual(name, "cardVisual", x, y, w, 108, {
        "Data": {"projections": [projection(table, measure, "Measure")]}
    }, objects={
        "label": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "11D"}}}}}],
        "value": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "24D"}}}}}],
    })
    result["visual"]["visualContainerObjects"] = container_title("")
    return result


def slicer(name: str, table: str, column: str, x: int, width: int) -> dict:
    return visual(name, "slicer", x, 115, width, 60,
                  {"Values": {"projections": [projection(table, column, "Column")]}},
                  objects={
                      "data": [{"properties": {"mode": literal("Dropdown")}}],
                      "selection": [{"properties": {
                          "singleSelect": boolean(False),
                          "strictSingleSelect": boolean(False),
                          "selectAllCheckboxEnabled": boolean(True),
                      }}],
                  })


def chart(name: str, chart_type: str, table: str, category: str,
          measures: list[str], title: str, x: int, y: int, w: int, h: int) -> dict:
    return visual(name, chart_type, x, y, w, h, {
        "Category": {"projections": [projection(table, category, "Column")]},
        "Y": {"projections": [projection(table, m, "Measure") for m in measures]},
    }, title=title)


def table_visual(name: str, table: str, columns: list[tuple[str, str]], title: str,
                 x: int, y: int, width: int, height: int,
                 sort_measure: str | None = None, ascending: bool = False) -> dict:
    result = visual(name, "tableEx", x, y, width, height, {
        "Values": {"projections": [projection(table, col, kind) for col, kind in columns]}
    }, title=title)
    if sort_measure:
        result["visual"]["query"]["sortDefinition"] = {
            "sort": [{"field": field(table, sort_measure, "Measure"),
                      "direction": "Ascending" if ascending else "Descending"}],
            "isDefaultSort": True,
        }
    return result


def build_funnel_stage_snapshot() -> Path:
    funnel_path = SNAPSHOT / "funnel_stages.csv"
    rows = [
        {"stage_order": 1, "stage": "Impressions"},
        {"stage_order": 2, "stage": "Clicks"},
        {"stage_order": 3, "stage": "Sessions"},
        {"stage_order": 4, "stage": "Confirmed bookings"},
    ]
    with funnel_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FUNNEL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return funnel_path


def ensure_refresh_metadata() -> Path:
    """Keep a transparent fallback when a clone has no recorded snapshot export yet."""
    metadata_path = SNAPSHOT / "refresh_metadata.csv"
    if metadata_path.exists():
        return metadata_path
    with (SNAPSHOT / "gold_campaign_daily.csv").open(newline="", encoding="utf-8") as file:
        data_through_date = max(row["date"] for row in csv.DictReader(file))
    row = {
        "data_through_date": data_through_date,
        "snapshot_exported_utc": "",
        "dataform_workflow_state": "UNKNOWN",
        "dataform_completed_utc": "",
        "dataform_total_actions": "",
        "dataform_problem_actions": "",
        "dataform_assertion_actions": "",
        "dataform_problem_assertions": "",
        "powerbi_import_instruction": "Open the PBIP and select Home > Refresh to load this snapshot.",
    }
    with metadata_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REFRESH_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    return metadata_path


def build_quality_snapshot() -> Path:
    """Create a repeatable quality-gate snapshot from the two Gold mart extracts."""
    campaign_path = SNAPSHOT / "gold_campaign_daily.csv"
    experiment_path = SNAPSHOT / "gold_incrementality_experiment.csv"
    with campaign_path.open(newline="", encoding="utf-8") as file:
        campaign = list(csv.DictReader(file))
    with experiment_path.open(newline="", encoding="utf-8") as file:
        experiment = list(csv.DictReader(file))
    workflow_path = SNAPSHOT / "dataform_workflow_status.csv"
    if workflow_path.exists():
        with workflow_path.open(newline="", encoding="utf-8") as file:
            workflow = next(csv.DictReader(file), {})
    else:
        workflow = {}

    campaign_grain = {
        (row["date"], row["market"], row["channel"], row["campaign_id"], row["device_type"])
        for row in campaign
    }
    null_key_rows = sum(
        any(not row[column].strip() for column in ("date", "market", "channel", "campaign_id", "device_type"))
        for row in campaign
    )
    invalid_funnel_rows = sum(
        float(row["clicks"]) > float(row["impressions"])
        or float(row["conversions"]) > float(row["clicks"])
        or float(row["sessions"]) > float(row["clicks"])
        or float(row["ad_spend"]) < 0
        or float(row["booking_value"]) < 0
        or float(row["gross_margin"]) < 0
        or float(row["gross_margin"]) > float(row["booking_value"])
        for row in campaign
    )
    conversion_total = sum(int(row["conversions"]) for row in campaign)
    confirmed_booking_total = sum(int(row["confirmed_bookings"]) for row in campaign)
    incrementality_mismatches = sum(
        round(float(row["treatment_conversions"]) - float(row["control_conversions"]), 6)
        != round(float(row["incremental_conversions"]), 6)
        for row in experiment
    )
    campaign_dates = {row["date"] for row in campaign}
    expected_dates = {(date(2026, 8, 1) + timedelta(days=offset)).isoformat() for offset in range(31)}
    data_through_date = max(campaign_dates)

    def check(order: int, category: str, name: str, severity: str,
              observed: str, expected: str, failed_rows: int, evidence: str,
              status: str | None = None) -> dict[str, str | int]:
        return {
            "check_order": order, "category": category, "check_name": name,
            "severity": severity, "status": status or ("PASS" if failed_rows == 0 else "FAIL"),
            "observed_value": observed, "expected_condition": expected,
            "failed_rows": failed_rows, "data_through_date": data_through_date,
            "evidence": evidence,
        }

    checks = [
        check(1, "Coverage", "Campaign period coverage", "Critical",
              f"{min(campaign_dates)} to {data_through_date}; {len(campaign_dates)} dates",
              "2026-08-01 to 2026-08-31; 31 dates",
              len(campaign_dates.symmetric_difference(expected_dates)), "Distinct campaign dates"),
        check(2, "Completeness", "Campaign row volume", "Critical", f"{len(campaign):,} rows",
              "930 rows = 3 markets × 5 channels × 2 devices × 31 days",
              abs(len(campaign) - 930), "COUNTROWS(Campaign)"),
        check(3, "Completeness", "Experiment row volume", "Critical", f"{len(experiment):,} rows",
              "15 rows = 3 markets × 5 channels", abs(len(experiment) - 15), "COUNTROWS(Experiment)"),
        check(4, "Completeness", "Required campaign keys", "Critical", f"{null_key_rows:,} null-key rows",
              "0 nulls across date, market, channel, campaign_id, device_type", null_key_rows,
              "Null-key row count"),
        check(5, "Validity", "Campaign daily grain uniqueness", "Critical", f"{len(campaign_grain):,} distinct grains",
              "One row per date, market, channel, campaign_id, device_type", len(campaign) - len(campaign_grain),
              "Distinct campaign grain versus row count"),
        check(6, "Validity", "Funnel and economic bounds", "Critical", f"{invalid_funnel_rows:,} invalid rows",
              "0 rows where clicks > impressions, conversions/sessions > clicks, or economics are invalid",
              invalid_funnel_rows, "Row-level bounds check"),
        check(7, "Reconciliation", "Confirmed bookings reconcile", "Critical",
              f"{conversion_total:,} conversions = {confirmed_booking_total:,} confirmed bookings",
              "Platform conversions equal confirmed bookings", abs(conversion_total - confirmed_booking_total),
              "SUM(conversions) versus SUM(confirmed_bookings)"),
        check(8, "Reconciliation", "Experiment lift arithmetic", "Warning",
              f"{incrementality_mismatches:,} mismatched experiment rows",
              "incremental_conversions = treatment_conversions − control_conversions",
              incrementality_mismatches, "Experiment row-level arithmetic"),
        check(9, "Pipeline", "Dataform workflow invocation", "Critical",
              f"{workflow.get('invocation_state', 'UNAVAILABLE')}; {workflow.get('total_actions', 'n/a')} actions",
              "SUCCEEDED with every action completed", int(workflow.get("problem_actions", "0") or 0),
              workflow.get("invocation_id", "Run python dataform/cloud_api.py dashboard-status"),
              workflow.get("workflow_gate_status", "UNKNOWN")),
        check(10, "Pipeline", "Dataform assertion actions", "Critical",
              f"{workflow.get('assertion_actions', 'n/a')} assertions; {workflow.get('problem_assertion_actions', 'n/a')} problems",
              "All assertion actions SUCCEEDED", int(workflow.get("problem_assertion_actions", "0") or 0),
              "apac_meta_assertions action summary",
              "PASS" if workflow.get("workflow_gate_status") == "PASS" else workflow.get("workflow_gate_status", "UNKNOWN")),
    ]
    quality_path = SNAPSHOT / "data_quality_checks.csv"
    with quality_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=QUALITY_COLUMNS)
        writer.writeheader()
        writer.writerows(checks)
    return quality_path


def tmdl_table(name: str, columns: dict[str, str], measures: dict[str, tuple[str, str]],
               csv_path: Path) -> str:
    collisions = set(columns).intersection(measures)
    collisions |= {measure for measure in measures if measure.casefold() in {column.casefold() for column in columns}}
    if collisions:
        raise RuntimeError(f"Power BI column/measure name collision in {name}: {sorted(collisions)}")
    with csv_path.open(newline="", encoding="utf-8") as f:
        headers = next(csv.reader(f))
    if list(columns) != headers:
        raise RuntimeError(f"Unexpected CSV schema in {csv_path}")
    lines = [f"table {name}", f"\tlineageTag: {uid(name)}", ""]
    for measure_name, (expression, fmt) in measures.items():
        lines += [f"\tmeasure '{measure_name}' = {expression}",
                  f"\t\tformatString: {fmt}",
                  "\t\tdisplayFolder: KPI Measures",
                  f"\t\tlineageTag: {uid(name + '/measure/' + measure_name)}", ""]
    for column_name, data_type in columns.items():
        lines += [f"\tcolumn {column_name}", f"\t\tdataType: {data_type}",
                  f"\t\tlineageTag: {uid(name + '/column/' + column_name)}",
                  "\t\tsummarizeBy: none", f"\t\tsourceColumn: {column_name}"]
        if column_name in {"ctr", "cpc", "cvr", "cpa", "roas", "margin_roas",
                           "treatment_conversion_rate", "control_conversion_rate",
                           "relative_conversion_lift"}:
            lines.append("\t\tisHidden")
        lines.append("")
    type_map = {"string": "type text", "dateTime": "type datetime", "int64": "Int64.Type",
                "decimal": "type number", "double": "type number"}
    conversions = ", ".join(f'{{"{column}", {type_map[kind]}}}' for column, kind in columns.items())
    path = str(csv_path.resolve())
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =",
              "\t\t\t\tlet",
              f'\t\t\t\t  Source = Csv.Document(File.Contents("{path}"), [Delimiter=",", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
              "\t\t\t\t  Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
              f'\t\t\t\t  Types = Table.TransformColumnTypes(Headers, {{{conversions}}}, "en-US")',
              "\t\t\t\tin", "\t\t\t\t  Types", ""]
    return "\n".join(lines)


def build_model() -> None:
    write_json(MODEL / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {},
    })
    write_json(MODEL / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "APAC Metasearch Semantic Model"},
        "config": {"version": "2.0", "logicalId": uid("semantic-model")},
    })
    definition = MODEL / "definition"
    definition.mkdir(parents=True, exist_ok=True)
    (definition / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n", encoding="utf-8")
    (definition / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n\tdataAccessOptions\n\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        "ref table Campaign\nref table Experiment\nref table DataQuality\nref table FunnelStage\n"
        "ref table RefreshMetadata\n", encoding="utf-8")
    tables = definition / "tables"
    tables.mkdir(exist_ok=True)
    (tables / "Campaign.tmdl").write_text(tmdl_table(
        "Campaign", CAMPAIGN_COLUMNS, CAMPAIGN_MEASURES,
        SNAPSHOT / "gold_campaign_daily.csv"), encoding="utf-8")
    (tables / "Experiment.tmdl").write_text(tmdl_table(
        "Experiment", EXPERIMENT_COLUMNS, EXPERIMENT_MEASURES,
        SNAPSHOT / "gold_incrementality_experiment.csv"), encoding="utf-8")
    (tables / "DataQuality.tmdl").write_text(tmdl_table(
        "DataQuality", QUALITY_COLUMNS, QUALITY_MEASURES,
        SNAPSHOT / "data_quality_checks.csv"), encoding="utf-8")
    (tables / "FunnelStage.tmdl").write_text(tmdl_table(
        "FunnelStage", FUNNEL_COLUMNS, FUNNEL_MEASURES,
        SNAPSHOT / "funnel_stages.csv"), encoding="utf-8")
    (tables / "RefreshMetadata.tmdl").write_text(tmdl_table(
        "RefreshMetadata", REFRESH_COLUMNS, REFRESH_MEASURES,
        SNAPSHOT / "refresh_metadata.csv"), encoding="utf-8")


def page(page_name: str, display: str, visuals: list[dict]) -> None:
    location = REPORT / "definition" / "pages" / page_name
    visuals_location = location / "visuals"
    # PBIR treats every child directory here as a report visual. Remove visual
    # definitions from a prior generation so renamed/replaced visuals cannot
    # remain on the page and overlap the current layout in Power BI Desktop.
    if visuals_location.exists():
        for child in visuals_location.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    write_json(location / "page.json", {
        "$schema": f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json",
        "name": page_name, "displayName": display, "displayOption": "FitToPage",
        "height": 720, "width": 1280,
    })
    for item in visuals:
        write_json(visuals_location / item["name"] / "visual.json", item)


def build_report() -> None:
    write_json(PROJECT / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(REPORT / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "APAC Metasearch Performance Analytics"},
        "config": {"version": "2.0", "logicalId": uid("report")},
    })
    write_json(REPORT / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    definition = REPORT / "definition"
    write_json(definition / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    theme = {
        "name": "APAC Metasearch", "dataColors": [PALETTE[k] for k in
            ("teal", "blue", "coral", "gold", "navy", "muted")],
        "background": PALETTE["pale"], "foreground": PALETTE["ink"],
        "tableAccent": PALETTE["teal"],
        "good": PALETTE["teal"], "neutral": PALETTE["gold"],
        "bad": PALETTE["coral"],
    }
    write_json(REPORT / "StaticResources" / "RegisteredResources" / THEME_FILE, theme)
    write_json(ROOT / "theme.json", theme)
    base_theme = REPORT / "StaticResources" / "SharedResources" / "BaseThemes" / "CY26SU07.json"
    base_theme.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "base_theme.json", base_theme)
    version = {"visual": "2.11.0", "report": "3.3.0", "page": "2.1.0"}
    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY26SU07", "reportVersionAtImport": version,
                          "type": "SharedResources"},
            "customTheme": {"name": THEME_FILE, "reportVersionAtImport": version,
                            "type": "RegisteredResources"},
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY26SU07", "path": "BaseThemes/CY26SU07.json",
                        "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": THEME_FILE, "path": THEME_FILE,
                        "type": "CustomTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True,
                     "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True},
    })

    pages = ["overview", "diagnostics", "incrementality", "quality"]
    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": pages, "activePageName": pages[0],
    })

    overview = [
        textbox("header", "APAC METASEARCH  /  PERFORMANCE PULSE", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "August 2026  •  Synthetic data  •  USD equivalents  •  Click-date attribution",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("market", "Campaign", "market", 20, 180),
        slicer("channel", "Campaign", "channel", 210, 250),
        slicer("device", "Campaign", "device_type", 470, 180),
        card("spend", "Campaign", "Spend USD", 20, 190, 295),
        card("bookings", "Campaign", "Bookings", 335, 190, 295),
        card("margin_roas", "Campaign", "Margin ROAS", 650, 190, 295),
        card("contribution", "Campaign", "Contribution USD", 965, 190, 295),
        chart("market_margin_roas", "clusteredBarChart", "Campaign", "market",
              ["Margin ROAS"], "Margin return on ad spend by market", 20, 315, 600, 210),
        chart("daily_margin_spend", "lineChart", "Campaign", "date",
              ["Gross Margin USD", "Spend USD"], "Daily gross margin and ad spend (USD)",
              640, 315, 620, 210),
        table_visual("action_queue", "Campaign", [
            ("market", "Column"), ("channel", "Column"), ("device_type", "Column"),
            ("Spend USD", "Measure"), ("Bookings", "Measure"),
            ("Gross Margin USD", "Measure"), ("Margin ROAS", "Measure"),
            ("Contribution USD", "Measure"), ("Action Status", "Measure")],
            "Action queue • investigate negative contribution before changing budget", 20, 540, 1240, 145,
            sort_measure="Contribution USD", ascending=True),
    ]
    page("overview", "01  Executive Pulse", overview)

    diagnostics = [
        textbox("header", "CAMPAIGN DIAGNOSTICS  /  FIND THE LEAK", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "Follow impression → click → session → confirmed booking. Funnel values and rates recalculate from totals after every filter.",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("market", "Campaign", "market", 20, 180),
        slicer("channel", "Campaign", "channel", 210, 250),
        slicer("device", "Campaign", "device_type", 470, 180),
        card("impressions", "Campaign", "Total Impressions", 20, 190, 295),
        card("clicks", "Campaign", "Total Clicks", 335, 190, 295),
        card("sessions", "Campaign", "Total Sessions", 650, 190, 295),
        card("bookings", "Campaign", "Bookings", 965, 190, 295),
        chart("funnel_volumes", "clusteredBarChart", "FunnelStage", "stage",
              ["Funnel Volume"], "Funnel volumes • selected performance segment", 20, 315, 410, 200),
        chart("thailand_peer_cvr", "clusteredBarChart", "Campaign", "campaign_id",
              ["Thailand Peer CVR %"], "Thailand peer CVR • CMP003 versus other Thai campaigns", 450, 315, 810, 200),
        table_visual("funnel_step_detail", "FunnelStage", [
            ("stage", "Column"), ("Funnel Volume", "Measure"), ("Funnel Step Rate", "Measure")],
            "Funnel detail • step rate uses the preceding stage", 20, 535, 390, 150),
        table_visual("campaign_table", "Campaign", [
            ("campaign_id", "Column"), ("market", "Column"), ("channel", "Column"),
            ("device_type", "Column"), ("Total Clicks", "Measure"), ("Bookings", "Measure"),
            ("CVR %", "Measure"), ("Margin ROAS", "Measure"),
            ("Contribution USD", "Measure"), ("Action Status", "Measure")],
            "Campaign and device queue • inspect CMP003 before moving budget", 430, 535, 830, 150,
            sort_measure="Contribution USD", ascending=True),
    ]
    page("diagnostics", "02  Funnel & Campaign", diagnostics)

    experiment = [
        textbox("header", "INCREMENTALITY  /  DID ADS CREATE DEMAND?", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "Randomized treatment versus control summary  •  Separate synthetic population from campaign attribution",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("market", "Experiment", "market", 20, 180),
        slicer("channel", "Experiment", "channel", 210, 250),
        card("treatment_users", "Experiment", "Treatment Users", 20, 190, 295),
        card("control_users", "Experiment", "Control Users", 335, 190, 295),
        card("cvr_difference", "Experiment", "CVR Difference pp", 650, 190, 295),
        card("incremental_conversions", "Experiment", "Incremental Conversions", 965, 190, 295),
        chart("market_cvr", "clusteredColumnChart", "Experiment", "market",
              ["Treatment CVR", "Control CVR"], "Observed conversion rate by experiment arm and market",
              20, 315, 600, 190),
        chart("market_cvr_difference", "clusteredBarChart", "Experiment", "market",
              ["CVR Difference pp"], "Observed treatment minus control CVR (percentage points)",
              640, 315, 620, 190),
        table_visual("experiment_table", "Experiment", [
            ("experiment_id", "Column"), ("market", "Column"),
            ("channel", "Column"), ("Treatment Users", "Measure"), ("Control Users", "Measure"),
            ("Treatment CVR", "Measure"), ("Control CVR", "Measure"),
            ("CVR Difference pp", "Measure"), ("CVR Difference 95% Low", "Measure"),
            ("CVR Difference 95% High", "Measure"), ("Relative Lift", "Measure"),
            ("Incremental Conversions", "Measure"), ("Incremental Revenue USD", "Measure")],
            "Experiment detail • 95% interval applies to the treatment-control CVR difference", 20, 520, 1240, 140),
        textbox("caveat", "Intervals use a normal approximation for independent Bernoulli arms and do not adjust for multiple comparisons. Experiment revenue is gross booking value from a separate population, not campaign margin or incremental ROAS.",
                20, 670, 1240, 33, 10, PALETTE["pale"], PALETTE["muted"]),
    ]
    page("incrementality", "03  Incrementality", experiment)

    quality = [
        textbox("header", "DATA QUALITY GATE  /  CAN WE TRUST THIS PULSE?", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "Gold snapshot checks plus the latest recorded Dataform workflow and assertion outcomes",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("category", "DataQuality", "category", 20, 220),
        slicer("severity", "DataQuality", "severity", 250, 180),
        card("gate_status", "DataQuality", "Gate Status", 20, 190, 235),
        card("workflow_state", "RefreshMetadata", "Dataform Workflow State", 270, 190, 235),
        card("import_model_status", "Campaign", "Import Model Status", 520, 190, 235),
        card("data_through", "RefreshMetadata", "Data Through Date", 770, 190, 235),
        card("snapshot_export", "RefreshMetadata", "Snapshot Export UTC", 1020, 190, 240),
        chart("checks_by_category", "clusteredColumnChart", "DataQuality", "category",
              ["Checks Passed", "Checks Failed"], "Pass / fail checks by quality category", 20, 315, 600, 190),
        chart("checks_by_severity", "clusteredBarChart", "DataQuality", "severity",
              ["Checks Evaluated", "Checks Failed"], "Checks by severity", 640, 315, 620, 190),
        table_visual("quality_detail", "DataQuality", [
            ("category", "Column"), ("check_name", "Column"), ("severity", "Column"),
            ("observed_value", "Column"), ("expected_condition", "Column"),
            ("failed_rows", "Column"), ("status", "Column"), ("evidence", "Column")],
            "Quality gate detail • inspect failures, unknown results, and workflow evidence", 20, 520, 1240, 140),
        textbox("gate_rule", "Decision rule: investigate Critical FAIL before recommending a budget change. Data Through Date is the historical snapshot boundary; Snapshot Export UTC records the file export. Import Model Status changes only after Home > Refresh in Power BI Desktop.",
                20, 670, 1240, 33, 10, PALETTE["pale"], PALETTE["muted"]),
    ]
    page("quality", "04  Data Quality Gate", quality)


def main() -> None:
    for name in ("gold_campaign_daily", "gold_incrementality_experiment"):
        if not (SNAPSHOT / f"{name}.csv").exists():
            raise RuntimeError(f"Missing snapshot for {name}; run export_gold.py first")
    build_funnel_stage_snapshot()
    ensure_refresh_metadata()
    build_quality_snapshot()
    build_model()
    build_report()
    print(PROJECT / f"{NAME}.pbip")


if __name__ == "__main__":
    main()
