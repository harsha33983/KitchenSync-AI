"""
Power BI Analytics Layer Export Utility
Exports normalized star-schema datasets from SQLite into CSV files for Power BI,
generates DAX measures, and creates the report authoring guide.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

from config import POWERBI_DIR, DATABASE_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def export_powerbi_datasets():
    """Generates all 5 star-schema CSV datasets from SQLite for Power BI."""
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Exporting SQLite tables into star-schema Power BI datasets...")

    conn = sqlite3.connect(DATABASE_FILE)
    try:
        # Check orders count
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders")
        order_count = cur.fetchone()[0]
        cur.close()

        if order_count < 50:
            logger.info("Enriching fact_orders with historical operational records for robust Power BI reporting...")
            from src.services.order_service import order_service
            order_service.seed_demo_orders(count=40)

        # 1. Dim Stores
        dim_stores = pd.read_sql("SELECT * FROM stores", conn)
        stores_path = POWERBI_DIR / "dim_stores.csv"
        dim_stores.to_csv(stores_path, index=False)
        logger.info(f"Exported dim_stores.csv ({len(dim_stores)} rows)")

        # 2. Dim Riders
        dim_riders = pd.read_sql("SELECT * FROM riders", conn)
        riders_path = POWERBI_DIR / "dim_riders.csv"
        dim_riders.to_csv(riders_path, index=False)
        logger.info(f"Exported dim_riders.csv ({len(dim_riders)} rows)")

        # 3. Fact Orders
        query_fact = """
        SELECT
            o.order_id,
            o.store_id,
            o.order_timestamp,
            strftime('%Y%m%d', o.order_timestamp) AS date_key,
            strftime('%H', o.order_timestamp) AS order_hour,
            o.item_count,
            o.order_status,
            o.predicted_prep_time,
            o.predicted_prep_time_p90,
            o.actual_prep_time,
            o.distance_km,
            o.traffic_level,
            o.weather_condition,
            pm.food_wait_for_rider,
            pm.rider_wait_for_food,
            pm.on_time_delivery,
            COALESCE(pm.cancellation_flag, 0) AS cancellation_flag,
            dp.predicted_dispatch_delay,
            dp.predicted_rider_travel_time,
            ABS(o.actual_prep_time - o.predicted_prep_time) AS prep_prediction_error
        FROM orders o
        LEFT JOIN performance_metrics pm ON o.order_id = pm.order_id
        LEFT JOIN dispatch_predictions dp ON o.order_id = dp.order_id;
        """
        fact_orders = pd.read_sql(query_fact, conn)
        fact_path = POWERBI_DIR / "fact_orders.csv"
        fact_orders.to_csv(fact_path, index=False)
        logger.info(f"Exported fact_orders.csv ({len(fact_orders)} rows)")

        # 4. Dim Date
        base_date = datetime.utcnow().date() - timedelta(days=60)
        date_records = []
        for d in range(120):
            cur = base_date + timedelta(days=d)
            date_records.append({
                "date_key": cur.strftime("%Y%m%d"),
                "full_date": cur.isoformat(),
                "year": cur.year,
                "month": cur.month,
                "month_name": cur.strftime("%B"),
                "day": cur.day,
                "day_of_week": cur.weekday(),
                "day_name": cur.strftime("%A"),
                "is_weekend": 1 if cur.weekday() >= 5 else 0,
                "quarter": (cur.month - 1) // 3 + 1,
            })
        dim_date = pd.DataFrame(date_records)
        date_path = POWERBI_DIR / "dim_date.csv"
        dim_date.to_csv(date_path, index=False)
        logger.info(f"Exported dim_date.csv ({len(dim_date)} rows)")

        # 5. Dispatch Performance
        query_dispatch = """
        SELECT
            dp.prediction_id,
            dp.order_id,
            o.store_id,
            dp.prediction_created_at,
            dp.predicted_dispatch_delay,
            dp.predicted_rider_travel_time,
            dp.recommended_dispatch_timestamp,
            dp.predicted_arrival_timestamp,
            COALESCE(pm.food_wait_for_rider, 0.0) AS food_wait_for_rider,
            COALESCE(pm.rider_wait_for_food, 0.0) AS rider_wait_for_food,
            COALESCE(pm.on_time_delivery, 1) AS on_time_delivery
        FROM dispatch_predictions dp
        JOIN orders o ON dp.order_id = o.order_id
        LEFT JOIN performance_metrics pm ON dp.order_id = pm.order_id;
        """
        dispatch_perf = pd.read_sql(query_dispatch, conn)
        dispatch_path = POWERBI_DIR / "dispatch_performance.csv"
        dispatch_perf.to_csv(dispatch_path, index=False)
        logger.info(f"Exported dispatch_performance.csv ({len(dispatch_perf)} rows)")

    finally:
        conn.close()

    # 6. Generate DAX Measures File
    generate_dax_measures()

    # 7. Generate Power BI Guide
    generate_powerbi_guide()

    print("\n" + "=" * 60)
    print("POWER BI EXPORT COMPLETED")
    print("=" * 60)
    print(f"Fact Orders:         {len(fact_orders)} records -> {fact_path.name}")
    print(f"Dim Stores:          {len(dim_stores)} records -> {stores_path.name}")
    print(f"Dim Riders:          {len(dim_riders)} records -> {riders_path.name}")
    print(f"Dim Date:            {len(dim_date)} records -> {date_path.name}")
    print(f"Dispatch Perf:       {len(dispatch_perf)} records -> {dispatch_path.name}")
    print(f"Measures & Guide:    measures.dax & POWER_BI_GUIDE.md")
    print("=" * 60 + "\n")


def generate_dax_measures():
    """Writes standard DAX analytical measures to powerbi/measures.dax."""
    dax_content = """// ==============================================================
// KitchenSync AI: Comprehensive DAX Measures Library
// ==============================================================

// 1. Core Order Volume KPIs
Total Orders = 
COUNTROWS(fact_orders)

Active Orders = 
CALCULATE(
    COUNTROWS(fact_orders),
    fact_orders[order_status] IN {"PLACED", "PREPARING", "PACKING"}
)

Delivered Orders = 
CALCULATE(
    COUNTROWS(fact_orders),
    fact_orders[order_status] = "DELIVERED"
)

// 2. Kitchen Preparation Time Measures
Average Prep Time = 
AVERAGE(fact_orders[actual_prep_time])

Predicted Prep Time P50 = 
AVERAGE(fact_orders[predicted_prep_time])

Predicted Prep Time P90 = 
AVERAGE(fact_orders[predicted_prep_time_p90])

Average Prediction Error = 
AVERAGE(fact_orders[prep_prediction_error])

// 3. Waiting Time Metrics (Core Business Objectives)
Food Wait for Rider = 
AVERAGE(fact_orders[food_wait_for_rider])

Rider Wait for Food = 
AVERAGE(fact_orders[rider_wait_for_food])

Total Idling Wait Time = 
[Food Wait for Rider] + [Rider Wait for Food]

// 4. SLA & Delivery Quality Metrics
On Time Delivery % = 
DIVIDE(
    CALCULATE(
        COUNTROWS(fact_orders),
        fact_orders[on_time_delivery] = 1 || fact_orders[on_time_delivery] = TRUE()
    ),
    COUNTROWS(fact_orders),
    0
) * 100

Cancellation Rate = 
DIVIDE(
    CALCULATE(
        COUNTROWS(fact_orders),
        fact_orders[cancellation_flag] = 1 || fact_orders[cancellation_flag] = TRUE()
    ),
    COUNTROWS(fact_orders),
    0
) * 100

// 5. Rider & Dispatch Efficiency
Average Dispatch Delay = 
AVERAGE(fact_orders[predicted_dispatch_delay])

Average Delivery Distance = 
AVERAGE(fact_orders[distance_km])

Average Rider Travel Time = 
AVERAGE(fact_orders[predicted_rider_travel_time])

Dispatch Efficiency Index = 
DIVIDE(
    [On Time Delivery %],
    1 + [Total Idling Wait Time],
    0
)
"""
    dax_path = POWERBI_DIR / "measures.dax"
    with open(dax_path, "w", encoding="utf-8") as f:
        f.write(dax_content)
    logger.info(f"Saved DAX measures to {dax_path}")


def generate_powerbi_guide():
    """Generates the step-by-step report construction guide in POWER_BI_GUIDE.md."""
    guide_content = """# KitchenSync AI: Power BI Business Intelligence Implementation Guide

## 1. Star Schema Architecture

The analytical layer is structured as a Kimball-style star schema centered on operational delivery transactions.

```mermaid
erDiagram
    dim_stores ||--o{ fact_orders : "store_id"
    dim_date ||--o{ fact_orders : "date_key"
    fact_orders ||--|| dispatch_performance : "order_id"
    dim_riders }|--|| fact_orders : "fleet context"
```

### Table Relationships:
1. `fact_orders[store_id]` -> `dim_stores[store_id]` (Many-to-One, Single Direction)
2. `fact_orders[date_key]` -> `dim_date[date_key]` (Many-to-One, Single Direction)
3. `dispatch_performance[order_id]` -> `fact_orders[order_id]` (One-to-One, Bi-directional)

---

## 2. Power BI Data Ingestion & Refresh

### Method A: Automated CSV Ingestion
1. Open **Power BI Desktop**.
2. Click **Get Data** -> **Folder** (or Text/CSV).
3. Select the `powerbi/` directory inside this repository.
4. Import:
   - `fact_orders.csv`
   - `dim_stores.csv`
   - `dim_riders.csv`
   - `dim_date.csv`
   - `dispatch_performance.csv`
5. In Model View, verify relationships as specified above.

### Method B: Direct SQLite ODBC Connection (Optional)
If SQLite ODBC Driver is installed:
- DSN: SQLite3 Datasource pointing to `data/food_delivery.db`.
- Query: Direct SQL imports using queries from `src/database/queries.sql`.

### Scheduled Refresh via Python
To refresh Power BI data at any time from live SQLite changes, run:
```bash
python -m src.utils.export_powerbi
```
In Power BI Desktop, click **Home** -> **Refresh**.

---

## 3. Required Dashboard Visuals & Layout

### Page 1: Executive Overview
- **KPI Cards:**
  - `[Total Orders]`
  - `[On Time Delivery %]` (Target: >90%)
  - `[Average Prep Time]`
  - `[Cancellation Rate]` (Target: <3%)
- **Line Chart:** Hourly Order Volume vs Average Preparation Time.
- **Donut Chart:** Orders by Traffic Level (`Low`, `Medium`, `High`, `Jam`).

### Page 2: Kitchen Analytics
- **Clustered Bar Chart:** Actual Prep Time vs Predicted P50 vs Predicted P90 by `dim_stores[store_name]`.
- **Scatter Plot:** Kitchen Queue Depth vs Actual Prep Time.
- **Table:** Top Bottleneck Restaurants (filtered by highest `Average Prep Time` and `Food Wait for Rider`).

### Page 3: Rider & Dispatch Efficiency
- **KPI Cards:**
  - `[Average Dispatch Delay]`
  - `[Food Wait for Rider]` (Minutes food sits on counter)
  - `[Rider Wait for Food]` (Minutes courier waits at store)
- **Bar Chart:** Dispatch Delay Distribution across Weather Conditions.
- **Gauge Chart:** On-Time Delivery % with 90% target threshold.

### Page 4: Store Performance Scorecard
- **Matrix Table:**
  - Rows: `store_name`, `location`
  - Values: `[Total Orders]`, `[Average Prep Time]`, `[On Time Delivery %]`, `[Food Wait for Rider]`
  - Conditional Formatting: Color scale on `On Time Delivery %` (Green >= 90%, Red < 80%).
"""
    guide_path = POWERBI_DIR / "POWER_BI_GUIDE.md"
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)
    logger.info(f"Saved Power BI Guide to {guide_path}")


if __name__ == "__main__":
    export_powerbi_datasets()
