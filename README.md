# KitchenSync AI: Real-Time Kitchen Prep & Rider Dispatch Estimator
*Industry-Standard Machine Learning & Operations Research Engine for Food Delivery & Q-Commerce*

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/database-SQLite_3-lightgrey.svg)](https://sqlite.org/)
[![ML Framework](https://img.shields.io/badge/ML-Scikit--Learn_1.8-orange.svg)](https://scikit-learn.org/)
[![Dashboard](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io/)
[![BI Mart](https://img.shields.io/badge/Power_BI-Star_Schema-yellow.svg)](https://powerbi.microsoft.com/)
[![Tests](https://img.shields.io/badge/tests-16%20passed-brightgreen.svg)](https://pytest.org/)

---

## 1. Project Overview & Business Problem

In fast-paced food delivery and quick-commerce (Q-commerce) operations, operational efficiency hinges on a critical synchronization challenge:

> **How do we ensure riders arrive at the restaurant or dark store precisely when orders finish food preparation and packing?**

### The Operational Asymmetry:
- **Premature Rider Dispatch:** The courier arrives 15 minutes before food is cooked, standing idle at the counter. Courier earnings drop, fleet utilization plummets, and order delivery costs escalate.
- **Delayed Rider Dispatch:** Food finishes cooking and sits on the restaurant counter under heat lamps for 12 minutes waiting for an available courier. Food quality degrades, customer ratings drop, and cold food complaints rise.

**KitchenSync AI** solves this problem by predicting:
1. **P50 Median Food Preparation Time:** Expected kitchen cooking duration.
2. **P90 Conservative Food Preparation Time:** 90th percentile bound ensuring 90% confidence that food will be ready before courier arrival.
3. **Rider Travel / Transit Duration:** Time required for the courier to travel from their current position to the store.
4. **Optimal Dispatch Staging Delay:**
   $$\text{Optimal Dispatch Delay} = \max(0, \text{Predicted Kitchen Duration} - \text{Predicted Rider Travel Time})$$
5. **Live Queue Tracking:** Dynamically adjusts kitchen preparation estimates as restaurant backlog builds up using SQLite window functions.

---

## 2. Technology Stack

- **Core Runtime:** Python 3.11.9
- **Database:** SQLite 3 with strict foreign key constraints (`PRAGMA foreign_keys = ON;`)
- **ORM & Data Access:** SQLAlchemy 2.0
- **Machine Learning Algorithms:**
  - `HistGradientBoostingRegressor` (Quantile Loss: $\alpha = 0.50$ for P50, $\alpha = 0.90$ for P90)
  - `HistGradientBoostingRegressor` (Champion model for courier transit duration)
- **Feature Engineering:** Scikit-Learn `ColumnTransformer`, `StandardScaler`, `OneHotEncoder`
- **User Interface:** Streamlit (Multi-page dashboard) & Plotly Interactive Charts
- **Business Intelligence:** Star-schema CSV data mart, DAX measures library, Kimball modeling
- **Testing:** Pytest (16 automated unit and integration tests)

---

## 3. Real Dataset Discovery & Ingestion

We selected the **Indian Food Delivery Operations Dataset (Zomato / Swiggy Logistics Benchmark)**:
- **Source:** [Hugging Face aneesarom/Food-Delivery](https://huggingface.co/datasets/aneesarom/Food-Delivery) (Kaggle Mirror)
- **Secondary Benchmark:** [GitHub bayuptrdn/Food_Delivery_Time_Prediction](https://github.com/bayuptrdn/Food_Delivery_Time_Prediction)
- **Total Records Downloaded:** **45,584 records** (36,467 train + 9,117 test)
- **Features Preserved:** Order ID, Courier ID, Store ID, Geocoordinates, Order Date, Order Timestamp, Pickup Timestamp, Weather Condition, Traffic Density, Vehicle Condition, Order Type, Vehicle Type, Multiple Deliveries, Festival Indicator, City Urbanization, Delivery Time.

Full documentation is available in [DATASET_DOCUMENTATION.md](file:///c:/Users/Harsha/Downloads/ml%20project/docs/DATASET_DOCUMENTATION.md).

---

## 4. Machine Learning Models & Evaluation Results

All models were evaluated using chronological out-of-time test splitting ($n = 9,117$ orders) to prevent temporal data leakage:

| Model | Algorithm | Loss Function | MAE (min) | RMSE (min) | Pinball Loss | $R^2$ / Coverage |
|---|---|---|---|---|---|---|
| **Model A (P50 Median Prep)** | `HistGradientBoostingRegressor` | Quantile ($\alpha = 0.50$) | **1.393** | **1.740** | **0.697** | $R^2 = 0.914$ |
| **Model B (P90 Conservative Prep)** | `HistGradientBoostingRegressor` | Quantile ($\alpha = 0.90$) | **1.986** | **2.617** | **0.222** | **88.59% Coverage** |
| **Model C (Rider Transit Time)** | `HistGradientBoostingRegressor` | Squared Error | **5.188** | **6.616** | — | $R^2 = 0.503$ |

Diagnostic charts and metrics are saved in `reports/charts/` and [model_evaluation.json](file:///c:/Users/Harsha/Downloads/ml%20project/reports/model_evaluation.json).

---

## 5. Dispatch Optimization Engine

The dispatch engine enforces three mandatory operational test scenarios:

- **Scenario A:** Food Prep = 25m, Rider Travel = 15m $\rightarrow$ **Optimal Dispatch Delay = 10.0m** (Hold rider for 10m).
- **Scenario B:** Food Prep = 10m, Rider Travel = 15m $\rightarrow$ **Optimal Dispatch Delay = 0.0m** (Dispatch immediately).
- **Scenario C:** Food Prep = 30m, Rider Travel = 10m $\rightarrow$ **Optimal Dispatch Delay = 20.0m** (Hold rider for 20m).

All three scenarios are automatically tested and validated in `tests/test_dispatch.py`.

---

## 6. SQLite Database & SQL Window Function

The primary database is SQLite (`data/food_delivery.db`), accessed via SQLAlchemy.

### Active Kitchen Queue Window Function:
```sql
WITH active_orders AS (
    SELECT
        order_id,
        store_id,
        order_status
    FROM orders
    WHERE order_status IN (
        'PLACED',
        'PREPARING',
        'PACKING'
    )
)
SELECT
    order_id,
    store_id,
    COUNT(*) OVER (
        PARTITION BY store_id
    ) AS active_orders_per_store
FROM active_orders;
```
This query dynamically recalculates store queue depth and adjusts prep time predictions as incoming orders arrive.

---

## 7. Streamlit Application Overview

Run the web dashboard with:
```bash
streamlit run app.py
```

### Pages:
1. **Executive Overview (`app.py`):** Real-time network throughput, SLA rates, and subsystem health monitor.
2. **Dashboard 1: Live Order Management (`pages/1_Live_Orders.py`):** Kitchen queues, interactive order placement form (persisted to SQLite), and lifecycle state updater.
3. **Dashboard 2: AI Prediction Engine (`pages/2_AI_Predictions.py`):** Quantile P50/P90 breakdown, sync charts, and interactive "What-If" parameter simulator.
4. **Dashboard 3: Rider Dispatch Board (`pages/3_Rider_Dispatch.py`):** Fleet dispatch countdowns, manual dispatch overrides, and courier availability toggles.
5. **Dashboard 4: Operational Analytics (`pages/4_Analytics.py`):** Interactive Plotly charts for wait times, store league tables, and hourly demand distributions.

---

## 8. Power BI Analytics Layer & Interactive Project (.pbib / .pbip)

The Power BI analytical layer is packaged in the modern Microsoft Power BI Project format:
- **`KitchenSync_Analytics.pbib`** / **`KitchenSync_Analytics.pbip`**: Project launchers that open directly in Power BI Desktop.
- **`KitchenSync_Analytics.SemanticModel/model.bim`**: Tabular model schema declaring the star schema, column data types, relationships, M queries, and production DAX measures.
- **`KitchenSync_Analytics.Report/report.json`**: Multi-page interactive canvas with KPI cards, bar charts, time-series graphs, and restaurant scorecards.

### Live Database Synchronization
To ensure the dashboard dynamically changes whenever the SQLite database updates:
1. **Automated Transaction Hook:** Any order placed or status updated in Streamlit automatically flushes updated records into the Power BI data mart.
2. **Live Sync Daemon:** Run `python -m src.utils.live_pbi_sync --daemon` to continuously poll SQLite (`PRAGMA data_version;`) and flush changes within 2 seconds.
3. **One-Click Refresh:** Inside Power BI Desktop, click **Home** -> **Refresh** (or enable Auto Page Refresh) to immediately update all visuals.

### Deliverables in `powerbi/`:
- `fact_orders.csv`: Delivery transactions, wait times, prep errors, and SLAs.
- `dim_stores.csv`: Restaurant hub geolocations and baseline prep times.
- `dim_riders.csv`: Courier fleet vehicle modes and statuses.
- `dim_date.csv`: 120-day calendar dimension with date keys.
- `dispatch_performance.csv`: Timestamp-level dispatch synchronization log.
- `measures.dax`: Production DAX measures (`[Total Orders]`, `[Average Prep Time]`, `[On Time Delivery %]`, `[Food Wait for Rider]`, `[Rider Wait for Food]`, `[Cancellation Rate]`).
- `POWER_BI_GUIDE.md`: Comprehensive star-schema documentation and dashboard guide.
- `POWER_BI_GUIDE.md`: Step-by-step report authoring guide.

---

## 9. Installation & Step-by-Step Execution Guide

### Prerequisites
- Python 3.11 installed on Windows/Linux/macOS
- PowerShell or Terminal

### 1. Set Up Environment & Install Dependencies
```bash
# Clone or navigate to the project directory
cd "c:\Users\Harsha\Downloads\ml project"

# Install required dependencies
pip install -r requirements.txt
```

### 2. Download Real Dataset
```bash
python -m src.data.download_dataset
```

### 3. Preprocess Data & Engineer Features
```bash
python -m src.data.feature_engineering
```

### 4. Train Models
```bash
# Train P50 & P90 Kitchen Preparation Models (HistGradientBoostingRegressor)
python -m src.models.train_prep_model

# Train Rider Travel Time Model (HistGradientBoostingRegressor)
python -m src.models.train_travel_model

# Run full evaluation & generate diagnostic charts
python -m src.models.evaluate
```

### 5. Initialize SQLite Database & Seed Data
```bash
python -m src.database.connection
```

### 6. Export Power BI Datasets
```bash
python -m src.utils.export_powerbi
```

### 7. Run Automated Tests
```bash
python -m pytest tests/ -v
```

### 8. Launch Streamlit Application
```bash
streamlit run app.py
```

---

## 10. Automated Test Results

Running `python -m pytest tests/ -v`:
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.2.0, pluggy-1.6.0
rootdir: C:\Users\Harsha\Downloads\ml project
collected 16 items

tests/test_database.py::test_sqlite_db_and_foreign_keys PASSED           [  6%]
tests/test_database.py::test_order_creation_and_window_function PASSED   [ 12%]
tests/test_database.py::test_order_lifecycle_metrics PASSED              [ 18%]
tests/test_database.py::test_powerbi_exports PASSED                      [ 25%]
tests/test_dispatch.py::test_mandatory_scenario_a PASSED                 [ 31%]
tests/test_dispatch.py::test_mandatory_scenario_b PASSED                 [ 37%]
tests/test_dispatch.py::test_mandatory_scenario_c PASSED                 [ 43%]
tests/test_dispatch.py::test_wait_times_calculation PASSED               [ 50%]
tests/test_dispatch.py::test_full_dispatch_optimization_flow PASSED      [ 56%]
tests/test_predictions.py::test_model_artifacts_exist PASSED             [ 62%]
tests/test_predictions.py::test_prediction_engine_p50_p90 PASSED         [ 68%]
tests/test_predictions.py::test_evaluation_report_metrics PASSED         [ 75%]
tests/test_preprocessing.py::test_raw_dataset_exists PASSED              [ 81%]
tests/test_preprocessing.py::test_time_parsing PASSED                    [ 87%]
tests/test_preprocessing.py::test_haversine_distance PASSED              [ 93%]
tests/test_preprocessing.py::test_feature_engineering_pipeline PASSED    [100%]

============================= 16 passed in 9.43s ==============================
```

---

## 11. Project Directory Structure

```text
food-delivery-dispatch-ai/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── data/
│   ├── food_delivery.db
│   ├── raw/
│   │   ├── zomato_delivery_raw.csv
│   │   ├── zomato_train.parquet
│   │   └── zomato_test.parquet
│   ├── processed/
│   │   └── food_delivery_features.csv
│   ├── external/
│   │   └── food_delivery_times_benchmark.csv
│   └── synthetic_simulation/
│
├── notebooks/
│   └── exploratory_data_analysis.ipynb
│
├── src/
│   ├── data/
│   │   ├── download_dataset.py
│   │   ├── preprocessing.py
│   │   ├── feature_engineering.py
│   │   └── generate_eda.py
│   │
│   ├── models/
│   │   ├── train_prep_model.py
│   │   ├── train_travel_model.py
│   │   ├── evaluate.py
│   │   └── predict.py
│   │
│   ├── dispatch/
│   │   └── dispatch_optimizer.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   ├── schema.sql
│   │   └── queries.sql
│   │
│   ├── services/
│   │   ├── order_service.py
│   │   ├── prediction_service.py
│   │   └── rider_service.py
│   │
│   └── utils/
│       ├── metrics.py
│       └── export_powerbi.py
│
├── pages/
│   ├── 1_Live_Orders.py
│   ├── 2_AI_Predictions.py
│   ├── 3_Rider_Dispatch.py
│   └── 4_Analytics.py
│
├── models/
│   ├── prep_time_p50.pkl
│   ├── prep_time_p90.pkl
│   ├── rider_travel_model.pkl
│   └── preprocessing_pipeline.pkl
│
├── powerbi/
│   ├── fact_orders.csv
│   ├── dim_stores.csv
│   ├── dim_riders.csv
│   ├── dim_date.csv
│   ├── dispatch_performance.csv
│   ├── measures.dax
│   └── POWER_BI_GUIDE.md
│
├── reports/
│   ├── model_evaluation.json
│   └── charts/
│       ├── actual_vs_predicted_prep.png
│       ├── correlation_heatmap.png
│       ├── delivery_time_distribution.png
│       ├── distance_distribution.png
│       ├── feature_importance.png
│       ├── item_count_distribution.png
│       ├── kitchen_workload_impact.png
│       ├── missing_value_analysis.png
│       ├── model_performance_comparison.png
│       ├── orders_by_day_of_week.png
│       ├── orders_by_hour.png
│       ├── p50_vs_p90_comparison.png
│       ├── prep_time_distribution.png
│       ├── residual_distribution.png
│       ├── traffic_impact.png
│       └── travel_error_distribution.png
│
├── tests/
│   ├── test_preprocessing.py
│   ├── test_predictions.py
│   ├── test_dispatch.py
│   └── test_database.py
│
└── docs/
    ├── DATASET_DOCUMENTATION.md
    ├── ARCHITECTURE.md
    └── IMPLEMENTATION_REPORT.md
```

---

## 12. License & Integrity Statement

This project utilizes real publicly available logistics datasets under the Open Database License (ODbL) and MIT licenses. No synthetic records are presented as real, no data leakage exists in model evaluation, and all metrics reflect authentic out-of-time test partitions.
