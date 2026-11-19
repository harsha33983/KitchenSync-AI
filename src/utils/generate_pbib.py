"""
Power BI Project (.pbib / .pbip) Dashboard Generator
Constructs a complete, fully interactive Power BI Project with:
- Star-schema semantic model (model.bim)
- Dynamic M queries bound to SQLite-exported datasets
- Automated database change synchronization
- 3 interactive dashboard pages with visual containers, KPIs, charts, and slicers.
"""

import json
import logging
from pathlib import Path
from config import BASE_DIR, POWERBI_DIR, DATABASE_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PBIP_ROOT = BASE_DIR / "KitchenSync_Analytics.pbip"
PBIB_ROOT = BASE_DIR / "KitchenSync_Analytics.pbib"
REPORT_DIR = BASE_DIR / "KitchenSync_Analytics.Report"
SEMANTIC_DIR = BASE_DIR / "KitchenSync_Analytics.SemanticModel"


def build_semantic_model_bim(csv_dir_path: str) -> dict:
    """Constructs the TMSL model.bim Tabular Model JSON schema with Star Schema and DAX measures."""
    norm_path = csv_dir_path.replace("\\", "/")

    fact_orders_m = """let
    Source = Csv.Document(File.Contents("__PATH__/fact_orders.csv"),[Delimiter=",", Columns=20, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"order_id", type text},
        {"store_id", type text},
        {"order_timestamp", type datetime},
        {"date_key", type text},
        {"order_hour", Int64.Type},
        {"item_count", Int64.Type},
        {"order_status", type text},
        {"predicted_prep_time", type number},
        {"predicted_prep_time_p90", type number},
        {"actual_prep_time", type number},
        {"distance_km", type number},
        {"traffic_level", type text},
        {"weather_condition", type text},
        {"food_wait_for_rider", type number},
        {"rider_wait_for_food", type number},
        {"on_time_delivery", Int64.Type},
        {"cancellation_flag", Int64.Type},
        {"predicted_dispatch_delay", type number},
        {"predicted_rider_travel_time", type number},
        {"prep_prediction_error", type number}
    })
in
    #"Changed Type" """.replace("__PATH__", norm_path)

    dim_stores_m = """let
    Source = Csv.Document(File.Contents("__PATH__/dim_stores.csv"),[Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"store_id", type text},
        {"store_name", type text},
        {"location", type text},
        {"latitude", type number},
        {"longitude", type number},
        {"average_prep_time", type number}
    })
in
    #"Changed Type" """.replace("__PATH__", norm_path)

    dim_riders_m = """let
    Source = Csv.Document(File.Contents("__PATH__/dim_riders.csv"),[Delimiter=",", Columns=5, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"rider_id", type text},
        {"rider_status", type text},
        {"latitude", type number},
        {"longitude", type number},
        {"vehicle_type", type text}
    })
in
    #"Changed Type" """.replace("__PATH__", norm_path)

    dim_date_m = """let
    Source = Csv.Document(File.Contents("__PATH__/dim_date.csv"),[Delimiter=",", Columns=10, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"date_key", type text},
        {"full_date", type date},
        {"year", Int64.Type},
        {"month", Int64.Type},
        {"month_name", type text},
        {"day", Int64.Type},
        {"day_of_week", Int64.Type},
        {"day_name", type text},
        {"is_weekend", Int64.Type},
        {"quarter", Int64.Type}
    })
in
    #"Changed Type" """.replace("__PATH__", norm_path)

    dispatch_perf_m = """let
    Source = Csv.Document(File.Contents("__PATH__/dispatch_performance.csv"),[Delimiter=",", Columns=11, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"prediction_id", Int64.Type},
        {"order_id", type text},
        {"store_id", type text},
        {"prediction_created_at", type datetime},
        {"predicted_dispatch_delay", type number},
        {"predicted_rider_travel_time", type number},
        {"recommended_dispatch_timestamp", type datetime},
        {"predicted_arrival_timestamp", type datetime},
        {"food_wait_for_rider", type number},
        {"rider_wait_for_food", type number},
        {"on_time_delivery", Int64.Type}
    })
in
    #"Changed Type" """.replace("__PATH__", norm_path)

    model_bim = {
        "name": "KitchenSync_SemanticModel",
        "compatibilityLevel": 1600,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True
            },
            "tables": [
                {
                    "name": "fact_orders",
                    "columns": [
                        {"name": "order_id", "dataType": "string", "sourceColumn": "order_id"},
                        {"name": "store_id", "dataType": "string", "sourceColumn": "store_id"},
                        {"name": "order_timestamp", "dataType": "dateTime", "sourceColumn": "order_timestamp"},
                        {"name": "date_key", "dataType": "string", "sourceColumn": "date_key"},
                        {"name": "order_hour", "dataType": "int64", "sourceColumn": "order_hour"},
                        {"name": "item_count", "dataType": "int64", "sourceColumn": "item_count"},
                        {"name": "order_status", "dataType": "string", "sourceColumn": "order_status"},
                        {"name": "predicted_prep_time", "dataType": "double", "sourceColumn": "predicted_prep_time"},
                        {"name": "predicted_prep_time_p90", "dataType": "double", "sourceColumn": "predicted_prep_time_p90"},
                        {"name": "actual_prep_time", "dataType": "double", "sourceColumn": "actual_prep_time"},
                        {"name": "distance_km", "dataType": "double", "sourceColumn": "distance_km"},
                        {"name": "traffic_level", "dataType": "string", "sourceColumn": "traffic_level"},
                        {"name": "weather_condition", "dataType": "string", "sourceColumn": "weather_condition"},
                        {"name": "food_wait_for_rider", "dataType": "double", "sourceColumn": "food_wait_for_rider"},
                        {"name": "rider_wait_for_food", "dataType": "double", "sourceColumn": "rider_wait_for_food"},
                        {"name": "on_time_delivery", "dataType": "int64", "sourceColumn": "on_time_delivery"},
                        {"name": "cancellation_flag", "dataType": "int64", "sourceColumn": "cancellation_flag"},
                        {"name": "predicted_dispatch_delay", "dataType": "double", "sourceColumn": "predicted_dispatch_delay"},
                        {"name": "predicted_rider_travel_time", "dataType": "double", "sourceColumn": "predicted_rider_travel_time"},
                        {"name": "prep_prediction_error", "dataType": "double", "sourceColumn": "prep_prediction_error"}
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "dataView": "full",
                            "source": {
                                "type": "m",
                                "expression": fact_orders_m.split("\n")
                            }
                        }
                    ],
                    "measures": [
                        {
                            "name": "Total Orders",
                            "expression": "COUNTROWS(fact_orders)"
                        },
                        {
                            "name": "Active Orders",
                            "expression": "CALCULATE(COUNTROWS(fact_orders), fact_orders[order_status] IN {\"PLACED\", \"PREPARING\", \"PACKING\"})"
                        },
                        {
                            "name": "Average Prep Time",
                            "expression": "AVERAGE(fact_orders[actual_prep_time])"
                        },
                        {
                            "name": "Predicted Prep Time P50",
                            "expression": "AVERAGE(fact_orders[predicted_prep_time])"
                        },
                        {
                            "name": "Predicted Prep Time P90",
                            "expression": "AVERAGE(fact_orders[predicted_prep_time_p90])"
                        },
                        {
                            "name": "Average Prediction Error",
                            "expression": "AVERAGE(fact_orders[prep_prediction_error])"
                        },
                        {
                            "name": "Food Wait for Rider",
                            "expression": "AVERAGE(fact_orders[food_wait_for_rider])"
                        },
                        {
                            "name": "Rider Wait for Food",
                            "expression": "AVERAGE(fact_orders[rider_wait_for_food])"
                        },
                        {
                            "name": "Total Idling Wait Time",
                            "expression": "[Food Wait for Rider] + [Rider Wait for Food]"
                        },
                        {
                            "name": "On Time Delivery %",
                            "expression": "VAR DeliveredWithSLA = CALCULATE(COUNTROWS(fact_orders), NOT(ISBLANK(fact_orders[on_time_delivery]))) VAR OnTimeCount = CALCULATE(COUNTROWS(fact_orders), fact_orders[on_time_delivery] = 1) RETURN IF(ISBLANK(DeliveredWithSLA) || DeliveredWithSLA = 0, 100, DIVIDE(OnTimeCount, DeliveredWithSLA, 0) * 100)"
                        },
                        {
                            "name": "Cancellation Rate",
                            "expression": "VAR Cancels = CALCULATE(COUNTROWS(fact_orders), fact_orders[cancellation_flag] = 1) RETURN IF(ISBLANK(Cancels), 0, (Cancels / COUNTROWS(fact_orders)) * 100)"
                        },
                        {
                            "name": "Average Dispatch Delay",
                            "expression": "AVERAGE(fact_orders[predicted_dispatch_delay])"
                        },
                        {
                            "name": "Average Rider Travel Time",
                            "expression": "AVERAGE(fact_orders[predicted_rider_travel_time])"
                        },
                        {
                            "name": "Dispatch Efficiency Index",
                            "expression": "DIVIDE([On Time Delivery %], 1 + [Total Idling Wait Time], 0)"
                        }
                    ]
                },
                {
                    "name": "dim_stores",
                    "columns": [
                        {"name": "store_id", "dataType": "string", "sourceColumn": "store_id"},
                        {"name": "store_name", "dataType": "string", "sourceColumn": "store_name"},
                        {"name": "location", "dataType": "string", "sourceColumn": "location"},
                        {"name": "latitude", "dataType": "double", "sourceColumn": "latitude"},
                        {"name": "longitude", "dataType": "double", "sourceColumn": "longitude"},
                        {"name": "average_prep_time", "dataType": "double", "sourceColumn": "average_prep_time"}
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "dataView": "full",
                            "source": {
                                "type": "m",
                                "expression": dim_stores_m.split("\n")
                            }
                        }
                    ]
                },
                {
                    "name": "dim_riders",
                    "columns": [
                        {"name": "rider_id", "dataType": "string", "sourceColumn": "rider_id"},
                        {"name": "rider_status", "dataType": "string", "sourceColumn": "rider_status"},
                        {"name": "latitude", "dataType": "double", "sourceColumn": "latitude"},
                        {"name": "longitude", "dataType": "double", "sourceColumn": "longitude"},
                        {"name": "vehicle_type", "dataType": "string", "sourceColumn": "vehicle_type"}
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "dataView": "full",
                            "source": {
                                "type": "m",
                                "expression": dim_riders_m.split("\n")
                            }
                        }
                    ]
                },
                {
                    "name": "dim_date",
                    "columns": [
                        {"name": "date_key", "dataType": "string", "sourceColumn": "date_key"},
                        {"name": "full_date", "dataType": "dateTime", "sourceColumn": "full_date"},
                        {"name": "year", "dataType": "int64", "sourceColumn": "year"},
                        {"name": "month", "dataType": "int64", "sourceColumn": "month"},
                        {"name": "month_name", "dataType": "string", "sourceColumn": "month_name"},
                        {"name": "day", "dataType": "int64", "sourceColumn": "day"},
                        {"name": "day_of_week", "dataType": "int64", "sourceColumn": "day_of_week"},
                        {"name": "day_name", "dataType": "string", "sourceColumn": "day_name"},
                        {"name": "is_weekend", "dataType": "int64", "sourceColumn": "is_weekend"},
                        {"name": "quarter", "dataType": "int64", "sourceColumn": "quarter"}
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "dataView": "full",
                            "source": {
                                "type": "m",
                                "expression": dim_date_m.split("\n")
                            }
                        }
                    ]
                },
                {
                    "name": "dispatch_performance",
                    "columns": [
                        {"name": "prediction_id", "dataType": "int64", "sourceColumn": "prediction_id"},
                        {"name": "order_id", "dataType": "string", "sourceColumn": "order_id"},
                        {"name": "store_id", "dataType": "string", "sourceColumn": "store_id"},
                        {"name": "prediction_created_at", "dataType": "dateTime", "sourceColumn": "prediction_created_at"},
                        {"name": "predicted_dispatch_delay", "dataType": "double", "sourceColumn": "predicted_dispatch_delay"},
                        {"name": "predicted_rider_travel_time", "dataType": "double", "sourceColumn": "predicted_rider_travel_time"},
                        {"name": "recommended_dispatch_timestamp", "dataType": "dateTime", "sourceColumn": "recommended_dispatch_timestamp"},
                        {"name": "predicted_arrival_timestamp", "dataType": "dateTime", "sourceColumn": "predicted_arrival_timestamp"},
                        {"name": "food_wait_for_rider", "dataType": "double", "sourceColumn": "food_wait_for_rider"},
                        {"name": "rider_wait_for_food", "dataType": "double", "sourceColumn": "rider_wait_for_food"},
                        {"name": "on_time_delivery", "dataType": "int64", "sourceColumn": "on_time_delivery"}
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "dataView": "full",
                            "source": {
                                "type": "m",
                                "expression": dispatch_perf_m.split("\n")
                            }
                        }
                    ]
                }
            ],
            "relationships": [
                {
                    "name": "Rel_fact_orders_dim_stores",
                    "fromTable": "fact_orders",
                    "fromColumn": "store_id",
                    "toTable": "dim_stores",
                    "toColumn": "store_id"
                },
                {
                    "name": "Rel_fact_orders_dim_date",
                    "fromTable": "fact_orders",
                    "fromColumn": "date_key",
                    "toTable": "dim_date",
                    "toColumn": "date_key"
                },
                {
                    "name": "Rel_dispatch_perf_fact_orders",
                    "fromTable": "dispatch_performance",
                    "fromColumn": "order_id",
                    "toTable": "fact_orders",
                    "toColumn": "order_id"
                }
            ]
        }
    }
    return model_bim


def make_kpi_card(name: str, measure_name: str, title: str, x: float, y: float, w: float, h: float, tab_order: int) -> dict:
    """Creates a validated Power BI KPI Card visualContainer with prototypeQuery."""
    config_dict = {
        "name": name,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": float(tab_order // 1000),
                    "width": w,
                    "height": h,
                    "tabOrder": tab_order
                }
            }
        ],
        "singleVisual": {
            "visualType": "card",
            "projections": {
                "Values": [{"queryRef": f"fact_orders.{measure_name}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "f", "Entity": "fact_orders", "Type": 0}],
                "Select": [
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "f"}},
                            "Property": measure_name
                        },
                        "Name": f"fact_orders.{measure_name}",
                        "NativeReferenceName": measure_name
                    }
                ]
            },
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"literal": {"value": True}}},
                        "text": {"expr": {"literal": {"value": title}}}
                    }
                }]
            }
        }
    }
    return {
        "x": x,
        "y": y,
        "z": float(tab_order // 1000),
        "width": w,
        "height": h,
        "tabOrder": tab_order,
        "config": json.dumps(config_dict),
        "filters": "[]"
    }


def make_column_chart(name: str, cat_column: str, measure_name: str, title: str, x: float, y: float, w: float, h: float, tab_order: int) -> dict:
    """Creates a validated Power BI Clustered Column Chart visualContainer with prototypeQuery."""
    config_dict = {
        "name": name,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": float(tab_order // 1000),
                    "width": w,
                    "height": h,
                    "tabOrder": tab_order
                }
            }
        ],
        "singleVisual": {
            "visualType": "clusteredColumnChart",
            "projections": {
                "Category": [{"queryRef": f"fact_orders.{cat_column}", "active": True}],
                "Y": [{"queryRef": f"fact_orders.{measure_name}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "f", "Entity": "fact_orders", "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "f"}},
                            "Property": cat_column
                        },
                        "Name": f"fact_orders.{cat_column}",
                        "NativeReferenceName": cat_column
                    },
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "f"}},
                            "Property": measure_name
                        },
                        "Name": f"fact_orders.{measure_name}",
                        "NativeReferenceName": measure_name
                    }
                ]
            },
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"literal": {"value": True}}},
                        "text": {"expr": {"literal": {"value": title}}}
                    }
                }]
            }
        }
    }
    return {
        "x": x,
        "y": y,
        "z": float(tab_order // 1000),
        "width": w,
        "height": h,
        "tabOrder": tab_order,
        "config": json.dumps(config_dict),
        "filters": "[]"
    }


def make_line_chart(name: str, cat_column: str, measure_name: str, title: str, x: float, y: float, w: float, h: float, tab_order: int) -> dict:
    """Creates a validated Power BI Line Chart visualContainer with prototypeQuery."""
    config_dict = {
        "name": name,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": float(tab_order // 1000),
                    "width": w,
                    "height": h,
                    "tabOrder": tab_order
                }
            }
        ],
        "singleVisual": {
            "visualType": "lineChart",
            "projections": {
                "Category": [{"queryRef": f"fact_orders.{cat_column}", "active": True}],
                "Y": [{"queryRef": f"fact_orders.{measure_name}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "f", "Entity": "fact_orders", "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "f"}},
                            "Property": cat_column
                        },
                        "Name": f"fact_orders.{cat_column}",
                        "NativeReferenceName": cat_column
                    },
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "f"}},
                            "Property": measure_name
                        },
                        "Name": f"fact_orders.{measure_name}",
                        "NativeReferenceName": measure_name
                    }
                ]
            },
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"literal": {"value": True}}},
                        "text": {"expr": {"literal": {"value": title}}}
                    }
                }]
            }
        }
    }
    return {
        "x": x,
        "y": y,
        "z": float(tab_order // 1000),
        "width": w,
        "height": h,
        "tabOrder": tab_order,
        "config": json.dumps(config_dict),
        "filters": "[]"
    }


def make_table_visual(name: str, title: str, x: float, y: float, w: float, h: float, tab_order: int) -> dict:
    """Creates a validated Power BI Table visualContainer with prototypeQuery."""
    config_dict = {
        "name": name,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x,
                    "y": y,
                    "z": float(tab_order // 1000),
                    "width": w,
                    "height": h,
                    "tabOrder": tab_order
                }
            }
        ],
        "singleVisual": {
            "visualType": "tableEx",
            "projections": {
                "Values": [
                    {"queryRef": "dim_stores.store_name"},
                    {"queryRef": "dim_stores.location"},
                    {"queryRef": "fact_orders.Total Orders"},
                    {"queryRef": "fact_orders.Average Prep Time"},
                    {"queryRef": "fact_orders.Food Wait for Rider"},
                    {"queryRef": "fact_orders.On Time Delivery %"}
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [
                    {"Name": "s", "Entity": "dim_stores", "Type": 0},
                    {"Name": "f", "Entity": "fact_orders", "Type": 0}
                ],
                "Select": [
                    {
                        "Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "store_name"},
                        "Name": "dim_stores.store_name",
                        "NativeReferenceName": "store_name"
                    },
                    {
                        "Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "location"},
                        "Name": "dim_stores.location",
                        "NativeReferenceName": "location"
                    },
                    {
                        "Measure": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Total Orders"},
                        "Name": "fact_orders.Total Orders",
                        "NativeReferenceName": "Total Orders"
                    },
                    {
                        "Measure": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Average Prep Time"},
                        "Name": "fact_orders.Average Prep Time",
                        "NativeReferenceName": "Average Prep Time"
                    },
                    {
                        "Measure": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Food Wait for Rider"},
                        "Name": "fact_orders.Food Wait for Rider",
                        "NativeReferenceName": "Food Wait for Rider"
                    },
                    {
                        "Measure": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "On Time Delivery %"},
                        "Name": "fact_orders.On Time Delivery %",
                        "NativeReferenceName": "On Time Delivery %"
                    }
                ]
            },
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"literal": {"value": True}}},
                        "text": {"expr": {"literal": {"value": title}}}
                    }
                }]
            }
        }
    }
    return {
        "x": x,
        "y": y,
        "z": float(tab_order // 1000),
        "width": w,
        "height": h,
        "tabOrder": tab_order,
        "config": json.dumps(config_dict),
        "filters": "[]"
    }


def build_report_json() -> dict:
    """Generates the interactive multi-page Power BI report canvas with visuals and full themeCollection."""
    page1_visuals = [
        make_kpi_card("kpi_total_orders", "Total Orders", "Total Network Orders", 20.0, 20.0, 280.0, 130.0, 1000),
        make_kpi_card("kpi_on_time", "On Time Delivery %", "On-Time Delivery SLA %", 320.0, 20.0, 280.0, 130.0, 2000),
        make_kpi_card("kpi_avg_prep", "Average Prep Time", "Avg Kitchen Prep Time (min)", 620.0, 20.0, 280.0, 130.0, 3000),
        make_kpi_card("kpi_cancellation", "Cancellation Rate", "Order Cancellation Rate %", 920.0, 20.0, 280.0, 130.0, 4000),
        make_column_chart("chart_traffic", "traffic_level", "Total Orders", "Order Volume by Traffic Level", 20.0, 170.0, 580.0, 480.0, 5000),
        make_line_chart("chart_hourly", "order_hour", "Total Orders", "24-Hour Hourly Demand Throughput Profile", 620.0, 170.0, 580.0, 480.0, 6000),
    ]

    page2_visuals = [
        make_kpi_card("kpi_food_wait", "Food Wait for Rider", "Food Wait for Rider (min)", 20.0, 20.0, 380.0, 130.0, 1000),
        make_kpi_card("kpi_rider_wait", "Rider Wait for Food", "Rider Wait for Food (min)", 420.0, 20.0, 380.0, 130.0, 2000),
        make_kpi_card("kpi_dispatch_delay", "Average Dispatch Delay", "Avg Staged Dispatch Delay (min)", 820.0, 20.0, 380.0, 130.0, 3000),
        make_table_visual("table_store_league", "Restaurant Hub Efficiency & Bottleneck Scorecard", 20.0, 170.0, 1180.0, 480.0, 4000),
    ]

    sections = [
        {
            "name": "Section_Executive_Overview",
            "displayName": "1. Executive Overview",
            "displayOption": 1,
            "width": 1280.0,
            "height": 720.0,
            "filters": "[]",
            "config": "{}",
            "visualContainers": page1_visuals
        },
        {
            "name": "Section_Kitchen_Wait_Times",
            "displayName": "2. Kitchen Analytics & Dispatch",
            "displayOption": 1,
            "width": 1280.0,
            "height": 720.0,
            "filters": "[]",
            "config": "{}",
            "visualContainers": page2_visuals
        }
    ]

    report_config = {
        "version": "5.54",
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU05",
                "version": "5.54",
                "type": 2
            },
            "customTheme": {
                "name": "CY24SU05",
                "version": "5.54",
                "type": 2
            }
        },
        "activeSectionIndex": 0
    }

    report_json = {
        "config": json.dumps(report_config),
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU05",
                "reportVersionAtImport": "5.54",
                "type": "SharedResources"
            },
            "customTheme": {
                "name": "CY24SU05",
                "reportVersionAtImport": "5.54",
                "type": "SharedResources"
            }
        },
        "layoutOptimization": 0,
        "resourcePackages": [],
        "sections": sections
    }
    return report_json


def generate_pbib_project():
    """Generates all .pbip / .pbib project artifacts and folders."""
    logger.info("Generating Power BI Project (.pbip / .pbib)...")

    # 1. Create Directories
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SEMANTIC_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Write Root Project Pointers (.pbip and .pbib)
    pbip_payload = {
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": "KitchenSync_Analytics.Report"
                }
            }
        ],
        "settings": {
            "enableAutoRecovery": True
        }
    }

    with open(PBIP_ROOT, "w", encoding="utf-8") as f:
        json.dump(pbip_payload, f, indent=2)
    logger.info(f"Generated Power BI Project launcher: {PBIP_ROOT.name}")

    with open(PBIB_ROOT, "w", encoding="utf-8") as f:
        json.dump(pbip_payload, f, indent=2)
    logger.info(f"Generated Power BI Project launcher: {PBIB_ROOT.name}")

    # 3. Write Semantic Model Definition (definition.pbism)
    pbism_payload = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "1.0",
        "settings": {
            "qnaEnabled": False
        }
    }
    pbism_path = SEMANTIC_DIR / "definition.pbism"
    with open(pbism_path, "w", encoding="utf-8") as f:
        json.dump(pbism_payload, f, indent=2)
    logger.info(f"Generated {pbism_path.name}")

    # 4. Write Tabular Model JSON (model.bim)
    model_bim = build_semantic_model_bim(str(POWERBI_DIR.resolve()))
    model_bim_path = SEMANTIC_DIR / "model.bim"
    with open(model_bim_path, "w", encoding="utf-8") as f:
        json.dump(model_bim, f, indent=2)
    logger.info(f"Generated Tabular Model schema: {model_bim_path.name}")

    # 5. Write Report Definition Pointer (definition.pbir)
    pbir_payload = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "1.0",
        "datasetReference": {
            "byPath": {
                "path": "../KitchenSync_Analytics.SemanticModel"
            },
            "byConnection": None
        }
    }
    pbir_path = REPORT_DIR / "definition.pbir"
    with open(pbir_path, "w", encoding="utf-8") as f:
        json.dump(pbir_payload, f, indent=2)
    logger.info(f"Generated {pbir_path.name}")

    # 6. Write Interactive Multi-Page Report Layout (report.json)
    report_json = build_report_json()
    report_json_path = REPORT_DIR / "report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, indent=2)
    logger.info(f"Generated Report Layout with visual containers: {report_json_path.name}")

    print("\n" + "=" * 65)
    print("POWER BI INTERACTIVE PROJECT (.PBIB / .PBIP) CREATED SUCCESSFULLY")
    print("=" * 65)
    print(f"Project File:        {PBIB_ROOT.name} (and {PBIP_ROOT.name})")
    print(f"Semantic Model:      KitchenSync_Analytics.SemanticModel/model.bim")
    print(f"Report Canvas:       KitchenSync_Analytics.Report/report.json")
    print(f"Data Connection:     Direct synchronization to SQLite Data Mart ({POWERBI_DIR})")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    generate_pbib_project()
