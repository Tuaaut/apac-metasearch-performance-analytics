"""Generate a Power BI Desktop PBIP/PBIR report and TMDL model from Gold snapshots."""

from __future__ import annotations

import csv
import json
import shutil
import uuid
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
CAMPAIGN_MEASURES = {
    "Impressions": ("SUM(Campaign[impressions])", "#,0"),
    "Clicks": ("SUM(Campaign[clicks])", "#,0"),
    "Sessions": ("SUM(Campaign[sessions])", "#,0"),
    "Bookings": ("SUM(Campaign[conversions])", "#,0"),
    "Spend USD": ("SUM(Campaign[ad_spend])", "$#,0;($#,0)"),
    "Booking Value USD": ("SUM(Campaign[booking_value])", "$#,0;($#,0)"),
    "Gross Margin USD": ("SUM(Campaign[gross_margin])", "$#,0;($#,0)"),
    "Contribution USD": ("[Gross Margin USD] - [Spend USD]", "$#,0;($#,0)"),
    "CTR": ("DIVIDE([Clicks], [Impressions])", "0.0%"),
    "Session Rate": ("DIVIDE([Sessions], [Clicks])", "0.0%"),
    "CVR": ("DIVIDE([Bookings], [Clicks])", "0.0%"),
    "CPC USD": ("DIVIDE([Spend USD], [Clicks])", "$0.00"),
    "CPA USD": ("DIVIDE([Spend USD], [Bookings])", "$0.00"),
    "ROAS": ("DIVIDE([Booking Value USD], [Spend USD])", "0.00"),
    "Margin ROAS": ("DIVIDE([Gross Margin USD], [Spend USD])", "0.00"),
}
EXPERIMENT_MEASURES = {
    "Treatment CVR": ("DIVIDE(SUM(Experiment[treatment_conversions]), SUM(Experiment[treatment_users]))", "0.0%"),
    "Control CVR": ("DIVIDE(SUM(Experiment[control_conversions]), SUM(Experiment[control_users]))", "0.0%"),
    "Incremental Conversions": ("SUM(Experiment[incremental_conversions])", "#,0"),
    "Relative Lift": ("DIVIDE([Treatment CVR], [Control CVR]) - 1", "0.0%"),
    "Incremental Revenue USD": ("SUM(Experiment[incremental_revenue])", "$#,0;($#,0)"),
}


def uid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"apac-metasearch/{label}"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": f"'{value}'"}}}


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
                  objects={"data": [{"properties": {"mode": literal("Dropdown")}}]})


def chart(name: str, chart_type: str, table: str, category: str,
          measures: list[str], title: str, x: int, y: int, w: int, h: int) -> dict:
    return visual(name, chart_type, x, y, w, h, {
        "Category": {"projections": [projection(table, category, "Column")]},
        "Y": {"projections": [projection(table, m, "Measure") for m in measures]},
    }, title=title)


def table_visual(name: str, table: str, columns: list[tuple[str, str]],
                 title: str, y: int, height: int) -> dict:
    return visual(name, "tableEx", 20, y, 1240, height, {
        "Values": {"projections": [projection(table, col, kind) for col, kind in columns]}
    }, title=title)


def tmdl_table(name: str, columns: dict[str, str], measures: dict[str, tuple[str, str]],
               csv_path: Path) -> str:
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
    type_map = {"string": "type text", "dateTime": "type date", "int64": "Int64.Type",
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
        "ref table Campaign\nref table Experiment\n", encoding="utf-8")
    tables = definition / "tables"
    tables.mkdir(exist_ok=True)
    (tables / "Campaign.tmdl").write_text(tmdl_table(
        "Campaign", CAMPAIGN_COLUMNS, CAMPAIGN_MEASURES,
        SNAPSHOT / "gold_campaign_daily.csv"), encoding="utf-8")
    (tables / "Experiment.tmdl").write_text(tmdl_table(
        "Experiment", EXPERIMENT_COLUMNS, EXPERIMENT_MEASURES,
        SNAPSHOT / "gold_incrementality_experiment.csv"), encoding="utf-8")


def page(page_name: str, display: str, visuals: list[dict]) -> None:
    location = REPORT / "definition" / "pages" / page_name
    write_json(location / "page.json", {
        "$schema": f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json",
        "name": page_name, "displayName": display, "displayOption": "FitToPage",
        "height": 720, "width": 1280,
    })
    for item in visuals:
        write_json(location / "visuals" / item["name"] / "visual.json", item)


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

    pages = ["overview", "diagnostics", "incrementality"]
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
              ["Margin ROAS"], "Margin return on ad spend by market", 20, 315, 600, 255),
        chart("daily_value_spend", "lineChart", "Campaign", "date",
              ["Spend USD", "Booking Value USD"], "Daily ad spend and booking value (USD)",
              640, 315, 620, 255),
        textbox("takeaway", "Decision lens: margin ROAS > 1 means commission margin exceeds ad spend before overhead. Use filters to compare market efficiency; booking value ROAS alone can overstate contribution.",
                20, 585, 1240, 108, 14, PALETTE["white"], PALETTE["ink"]),
    ]
    page("overview", "01  Executive Pulse", overview)

    diagnostics = [
        textbox("header", "CAMPAIGN DIAGNOSTICS  /  FIND THE LEAK", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "Follow impression → click → session → confirmed booking. Ratios recalculate from totals after every filter.",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("market", "Campaign", "market", 20, 180),
        slicer("channel", "Campaign", "channel", 210, 250),
        slicer("device", "Campaign", "device_type", 470, 180),
        card("ctr", "Campaign", "CTR", 20, 190, 295),
        card("session_rate", "Campaign", "Session Rate", 335, 190, 295),
        card("cvr", "Campaign", "CVR", 650, 190, 295),
        card("cpa", "Campaign", "CPA USD", 965, 190, 295),
        chart("campaign_ctr", "clusteredBarChart", "Campaign", "campaign_id",
              ["CTR"], "Click appeal: CTR by campaign", 20, 315, 600, 220),
        chart("campaign_cvr", "clusteredBarChart", "Campaign", "campaign_id",
              ["CVR"], "Post-click quality: CVR by campaign", 640, 315, 620, 220),
        table_visual("campaign_table", "Campaign", [
            ("campaign_id", "Column"), ("market", "Column"),
            ("device_type", "Column"), ("Clicks", "Measure"),
            ("Bookings", "Measure"), ("Spend USD", "Measure"),
            ("CVR", "Measure"), ("CPA USD", "Measure"),
            ("Margin ROAS", "Measure")],
            "Campaign detail • investigate CMP003: high CTR, weak CVR", 545, 148),
    ]
    page("diagnostics", "02  Funnel & Campaign", diagnostics)

    experiment = [
        textbox("header", "INCREMENTALITY  /  DID ADS CREATE DEMAND?", 0, 0, 1280, 70,
                26, PALETTE["navy"], PALETTE["white"], True),
        textbox("subtitle", "Randomized treatment vs control summary  •  Separate synthetic population from campaign attribution",
                0, 70, 1280, 37, 12, PALETTE["pale"], PALETTE["muted"]),
        slicer("market", "Experiment", "market", 20, 180),
        slicer("channel", "Experiment", "channel", 210, 250),
        card("incremental_conversions", "Experiment", "Incremental Conversions", 20, 190, 400),
        card("relative_lift", "Experiment", "Relative Lift", 440, 190, 400),
        card("incremental_revenue", "Experiment", "Incremental Revenue USD", 860, 190, 400),
        chart("market_cvr", "clusteredColumnChart", "Experiment", "market",
              ["Treatment CVR", "Control CVR"], "Conversion rate by experiment arm and market",
              20, 315, 600, 225),
        chart("channel_incremental", "clusteredBarChart", "Experiment", "channel",
              ["Incremental Conversions"], "Incremental conversions by channel",
              640, 315, 620, 225),
        table_visual("experiment_table", "Experiment", [
            ("experiment_id", "Column"), ("market", "Column"),
            ("channel", "Column"), ("Treatment CVR", "Measure"),
            ("Control CVR", "Measure"), ("Incremental Conversions", "Measure"),
            ("Relative Lift", "Measure")],
            "Experiment detail • lift requires uncertainty analysis before budget decisions", 550, 113),
        textbox("caveat", "Experiment revenue is gross booking value from separate eligible users. Do not add it to the observational campaign totals or treat observed ROAS as causal lift.",
                20, 670, 1240, 33, 10, PALETTE["pale"], PALETTE["muted"]),
    ]
    page("incrementality", "03  Incrementality", experiment)


def main() -> None:
    for name in ("gold_campaign_daily", "gold_incrementality_experiment"):
        if not (SNAPSHOT / f"{name}.csv").exists():
            raise RuntimeError(f"Missing snapshot for {name}; run export_gold.py first")
    build_model()
    build_report()
    print(PROJECT / f"{NAME}.pbip")


if __name__ == "__main__":
    main()
