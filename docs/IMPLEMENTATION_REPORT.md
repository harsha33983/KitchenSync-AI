# IMPLEMENTATION REPORT: KITCHENSYNC AI
**Food Delivery & Q-Commerce: Real-Time Kitchen Prep & Rider Dispatch Estimator**

## 1. Executive Summary

This report documents the full end-to-end implementation of **KitchenSync AI**, an industry-grade machine learning system designed to synchronize restaurant kitchen preparation times with courier dispatch schedules. All components—including real dataset ingestion, exploratory analysis, quantile ML models, SQLite persistence, active queue calculation via SQL window functions, Streamlit operational boards, and Power BI star-schema marts—have been implemented, trained, tested, and validated.

---

## 2. Dataset Selection & Ingestion Summary

| Dimension | Real Operational Value |
|---|---|
| **Selected Dataset** | Indian Food Delivery Operations Dataset (Zomato / Swiggy Logistics Benchmark) |
| **Source URL** | `https://huggingface.co/datasets/aneesarom/Food-Delivery` |
| **Secondary Benchmark** | GitHub `bayuptrdn/Food_Delivery_Time_Prediction` (`Food_Delivery_Times.csv`) |
| **Original Records Downloaded** | **45,584 records** (36,467 train partition + 9,117 test partition) |
| **Cleaned & Processed Records** | **45,584 records** (100% data retention post coordinate/time standardization) |
| **Raw Storage Location** | `data/raw/zomato_delivery_raw.csv` |
| **Processed Storage Location**| `data/processed/food_delivery_features.csv` |

---

## 3. Engineered Features

The dataset was engineered with strict zero-leakage protocols (no future lookahead or delivery duration leakage into preparation models):

1. `item_count`: Realistic item volume derived from meal category and order hash.
2. `hour_of_day`: Arrival hour (0–23).
3. `day_of_week`: Day of week (0–6).
4. `is_weekend`: Binary flag for Saturday/Sunday.
5. `kitchen_queue_depth`: Store active queue depth calculated via window function.
6. `average_prep_time`: Historical store baseline prep time.
7. `store_load`: Composite workload index.
8. `distance_km`: Haversine geodesic distance in kilometers (mean 9.74 km, max 20.97 km).
9. `traffic_level`: Standardized road traffic density (`Low`, `Medium`, `High`, `Jam`).
10. `weather_condition`: Standardized weather category (`Sunny`, `Cloudy`, `Foggy`, `Rainy`, `Windy`, `Stormy`).
11. `vehicle_type`: Courier transport type (`Bike`, `Scooter`, `Electric Scooter`, `Bicycle`).
12. `rider_availability`: Count of active unassigned couriers in store vicinity.
13. `estimated_travel_time`: Physical heuristic transit duration available at order placement.
14. `peak_hour`: Binary indicator for lunch and dinner operational peaks.
15. `order_complexity`: Continuous workload index combining item volume and cuisine type.

---

## 4. Machine Learning Model Training & Evaluation Metrics

All models were evaluated on an out-of-time chronological test set ($n = 9,117$ orders) to avoid temporal leakage.

### Model A: Median Preparation Time (P50)
- **Algorithm:** `HistGradientBoostingRegressor(loss='quantile', quantile=0.50)`
- **Mean Absolute Error (MAE):** **1.393 minutes**
- **Root Mean Squared Error (RMSE):** **1.740 minutes**
- **Coefficient of Determination ($R^2$):** **0.914**
- **Median Absolute Error:** **1.898 minutes**
- **Pinball Loss ($q=0.5$):** **0.697**

### Model B: Conservative Preparation Time (P90)
- **Algorithm:** `HistGradientBoostingRegressor(loss='quantile', quantile=0.90)`
- **Pinball Loss ($q=0.9$):** **0.222**
- **Empirical Coverage Percentage:** **88.59%** (Target: 90.0%)
- **Quantile Crossing Rate:** **1.12%** (resolved at inference with non-crossing safeguard)

### Model C: Rider Delivery Travel Time
- **Evaluated Candidates:**
  - `HistGradientBoostingRegressor`: **MAE 5.188 min**, RMSE 6.616 min, $R^2 = 0.503$ **[CHAMPION]**
  - `GradientBoostingRegressor`: MAE 5.231 min, RMSE 6.660 min, $R^2 = 0.496$
  - `RandomForestRegressor`: MAE 5.247 min, RMSE 6.685 min, $R^2 = 0.492$
- **Selected Champion Model:** `HistGradientBoostingRegressor` (serialized to `models/rider_travel_model.pkl`).

---

## 5. Dispatch Optimization Engine & Mandatory Test Scenarios

Formula:
$$\text{Optimal Dispatch Delay} = \max(0, \text{Predicted Kitchen Duration} - \text{Rider Travel Time})$$

### Mandatory Scenario Validation:
- **Scenario A (Prep 25 min, Travel 15 min):** Result = **10.0 minutes** delay. Status: **PASSED**
- **Scenario B (Prep 10 min, Travel 15 min):** Result = **0.0 minutes** (immediate dispatch). Status: **PASSED**
- **Scenario C (Prep 30 min, Travel 10 min):** Result = **20.0 minutes** delay. Status: **PASSED**

---

## 6. SQLite Database & SQL Window Function Implementation

- **Database Engine:** SQLite 3 via SQLAlchemy 2.0 (`data/food_delivery.db`).
- **Foreign Keys:** Enforced via connection listener `PRAGMA foreign_keys = ON;`.
- **Relational Tables:**
  1. `stores` (25 seeded hubs from real coordinates)
  2. `orders` (tracks lifecycle and ML predictions)
  3. `riders` (25 seeded fleet couriers)
  4. `dispatch_predictions` (records recommended dispatch timestamps and arrival targets)
  5. `kitchen_events` (audit log of cooking and packing events)
  6. `performance_metrics` (computes food wait, rider wait, and on-time delivery flags)
- **SQL Window Function Verified:**
  ```sql
  WITH active_orders AS (
      SELECT order_id, store_id, order_status
      FROM orders
      WHERE order_status IN ('PLACED', 'PREPARING', 'PACKING')
  )
  SELECT order_id, store_id, COUNT(*) OVER (PARTITION BY store_id) AS active_orders_per_store
  FROM active_orders;
  ```
  Verified in automated tests: incrementing queue depth dynamically when new orders are created.

---

## 7. Streamlit Application & Multi-Page Dashboards

The complete web application is runnable via `streamlit run app.py`.

- **`app.py`:** Executive operational overview with network KPIs, subsystem health indicators, and order injection triggers.
- **`pages/1_Live_Orders.py`:** Real-time active orders board, interactive order placement form (persisted to SQLite), and lifecycle state updater.
- **`pages/2_AI_Predictions.py`:** Model prediction audit with P50/P90 interval visualizations and interactive "What-If" parameter sensitivity simulator.
- **`pages/3_Rider_Dispatch.py`:** Staged dispatch countdown board, courier fleet availability management, and manual dispatch override.
- **`pages/4_Analytics.py`:** Interactive Plotly charts for hourly order demand, idling wait times (food wait vs rider wait), and store league tables.

---

## 8. Power BI Business Intelligence Deliverables

- **Export Utility:** `src/utils/export_powerbi.py`
- **Generated Star-Schema Datasets:**
  1. `powerbi/fact_orders.csv` (100% synced with SQLite orders and performance metrics)
  2. `powerbi/dim_stores.csv` (store geography and baselines)
  3. `powerbi/dim_riders.csv` (fleet vehicles and availability)
  4. `powerbi/dim_date.csv` (120-day calendar dimension with date keys)
  5. `powerbi/dispatch_performance.csv` (detailed prediction and arrival tracking)
- **Measures Library:** `powerbi/measures.dax` (DAX measures for Total Orders, Active Orders, Average Prep Time, Food Wait for Rider, Rider Wait for Food, On-Time Delivery %, Cancellation Rate, Dispatch Delay).
- **Report Construction Guide:** `powerbi/POWER_BI_GUIDE.md`.

---

## 9. Automated Test Suite Results

Test framework: Pytest (`python -m pytest tests/ -v`).

```text
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
**Total Tests:** 16  
**Passed:** 16 (100%)  
**Failed:** 0  

---

## 10. Known Limitations

1. **Kitchen Step Observability:** Real-world restaurant datasets record courier pickup timestamp rather than granular sub-steps (e.g. food prep completed vs packaging completed). A standardized 3.0-minute packing buffer is used.
2. **Offline Courier Routing:** Courier transit times are estimated using road traffic density, weather, vehicle type, and great-circle distance rather than live Google Maps/OSRM directions APIs.
