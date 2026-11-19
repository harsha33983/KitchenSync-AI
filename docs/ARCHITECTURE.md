# SYSTEM ARCHITECTURE: KITCHENSYNC AI

## 1. High-Level System Architecture

```text
                               +-----------------------------+
                               |     Incoming Food Order     |
                               +--------------+--------------+
                                              |
                                              v
                               +-----------------------------+
                               |   Streamlit Interface / POS  |
                               +--------------+--------------+
                                              |
                                              v
                               +-----------------------------+
                               |       SQLite Database       |
                               |  (data/food_delivery.db)    |
                               +-------+--------------+------+
                                       |              |
                    SQL Window Function|              | Historical
                   COUNT(*) OVER (...) |              | Records
                                       v              v
                        +--------------------+  +--------------------+
                        | Kitchen Queue Engine|  | Feature Transformer|
                        +----------+---------+  +---------+----------+
                                   |                      |
                                   +-----------+----------+
                                               |
                                               v
                                +-----------------------------+
                                |    ML Prediction Engine     |
                                |  (HistGradientBoosting)     |
                                +--------------+--------------+
                                               |
                                +--------------+--------------+
                                |                             |
                                v                             v
                 +---------------------------+  +---------------------------+
                 | Kitchen Prep Regressors   |  | Rider Transit Regressor   |
                 | Model A: P50 Median       |  | Model C: Transit Distance |
                 | Model B: P90 Conservative |  | Weather & Traffic Density |
                 +--------------+------------+  +-------------+-------------+
                                |                             |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | Dispatch Optimization Engine|
                                | Delay = max(0, Prep - Travel|
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                |    Staged Courier Dispatch   |
                                +--------------+--------------+
                                               |
                               +---------------+---------------+
                               |                               |
                               v                               v
                +-----------------------------+  +-----------------------------+
                |    SQLite Lifecycle Event   |  |  Power BI Analytics Layer  |
                |  (Wait Times & SLA Records) |  |   (Star-Schema CSV Marts)   |
                +-----------------------------+  +-----------------------------+
```

---

## 2. Component Design & Responsibilities

### 2.1 Interface Layer (`app.py`, `pages/`)
- **Dashboard 1 (`1_Live_Orders.py`):** Real-time queue depths, order submission, status state machine (`PLACED` $\rightarrow$ `PREPARING` $\rightarrow$ `PACKING` $\rightarrow$ `READY` $\rightarrow$ `DISPATCHED` $\rightarrow$ `PICKED_UP` $\rightarrow$ `DELIVERED`).
- **Dashboard 2 (`2_AI_Predictions.py`):** Model inferences, P50 vs P90 comparison, interactive parameter sensitivity simulator.
- **Dashboard 3 (`3_Rider_Dispatch.py`):** Fleet command board, countdown to dispatch, manual dispatch overrides, courier assignment.
- **Dashboard 4 (`4_Analytics.py`):** Interactive Plotly visualizations for wait distributions, bottleneck stores, and traffic impact.

### 2.2 Machine Learning Service Layer (`src/models/`)
- **Preprocessing Pipeline (`preprocessing_pipeline.pkl`):** Standardizes numerical features (item count, distance, queue depth, hour, store load) and one-hot encodes traffic density, weather conditions, and vehicle modes.
- **Model A: P50 Median Preparation Regressor (`prep_time_p50.pkl`):**
  - Algorithm: `HistGradientBoostingRegressor(loss='quantile', quantile=0.50)`
  - Objective: Expected median kitchen cooking and packing duration.
  - Evaluation: MAE 1.393 min, RMSE 1.740 min, $R^2 = 0.914$.
- **Model B: P90 Conservative Preparation Regressor (`prep_time_p90.pkl`):**
  - Algorithm: `HistGradientBoostingRegressor(loss='quantile', quantile=0.90)`
  - Objective: Conservative bound ensuring 90% confidence of food readiness before courier arrival.
  - Evaluation: Pinball loss 0.222, empirical coverage 88.59% (target 90%).
- **Model C: Rider Transit Duration Regressor (`rider_travel_model.pkl`):**
  - Algorithm: `HistGradientBoostingRegressor(loss='squared_error')`
  - Objective: Predicts point-to-point courier travel time conditioned on distance, weather, and traffic.
  - Evaluation: MAE 5.188 min, RMSE 6.616 min, $R^2 = 0.503$.

### 2.3 Dispatch Optimization Engine (`src/dispatch/dispatch_optimizer.py`)
- Calculates optimal courier hold time:
  $$\text{Optimal Dispatch Delay} = \max(0, \text{Predicted Kitchen Duration} - \text{Predicted Rider Travel Time})$$
- Evaluates operational wait penalties:
  $$\text{Food Wait for Rider} = \max(0, \text{Rider Arrival Time} - \text{Food Ready Time})$$
  $$\text{Rider Wait for Food} = \max(0, \text{Food Ready Time} - \text{Rider Arrival Time})$$

### 2.4 Persistence & SQL Engine (`src/database/`)
- Relational schema in SQLite 3 with strict foreign key integrity (`PRAGMA foreign_keys = ON`).
- **Window Function Implementation:**
  ```sql
  WITH active_orders AS (
      SELECT order_id, store_id, order_status
      FROM orders
      WHERE order_status IN ('PLACED', 'PREPARING', 'PACKING')
  )
  SELECT order_id, store_id, COUNT(*) OVER (PARTITION BY store_id) AS active_orders_per_store
  FROM active_orders;
  ```
  Runs before and after order placement to maintain real-time queue depth across multi-order batches.

### 2.5 Business Intelligence & Reporting Layer (`powerbi/`, `src/utils/export_powerbi.py`)
- Automated export from SQLite into Kimball-compliant star-schema tables:
  - `fact_orders.csv`
  - `dim_stores.csv`
  - `dim_riders.csv`
  - `dim_date.csv`
  - `dispatch_performance.csv`
- Full library of production DAX measures in `powerbi/measures.dax`.
