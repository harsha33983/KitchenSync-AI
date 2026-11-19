# DATASET DOCUMENTATION

## 1. Overview & Data Sources

This project evaluates and integrates real publicly available food delivery logistics datasets to build an intelligent dispatch and kitchen preparation time estimation system.

| Dataset Dimension | Primary Logistics Dataset | Secondary Benchmark Dataset |
|---|---|---|
| **Dataset Name** | Zomato / Swiggy Food Delivery Operations Dataset | Food Delivery Times Benchmark |
| **Source URL** | [Hugging Face aneesarom/Food-Delivery](https://huggingface.co/datasets/aneesarom/Food-Delivery) (Kaggle Mirror) | [GitHub bayuptrdn/Food_Delivery_Time_Prediction](https://github.com/bayuptrdn/Food_Delivery_Time_Prediction) |
| **License** | Open Database License (ODbL) / CC-BY 4.0 | MIT License |
| **Download Method** | Automated HTTPS Parquet/CSV via `src/data/download_dataset.py` | Direct HTTPS Raw CSV download |
| **Raw Records** | 45,584 records (36,467 train + 9,117 test) | 1,000 records |
| **Raw Columns** | 20 features | 9 features |
| **Storage Path** | `data/raw/zomato_delivery_raw.csv` | `data/external/food_delivery_times_benchmark.csv` |

---

## 2. Primary Dataset Schema & Column Dictionary

| Column Name | Data Type | Description | Operational Significance |
|---|---|---|---|
| `ID` | String (Hex) | Unique order identification code (e.g., `0x6bbb`) | Tracking identifier |
| `Delivery_person_ID` | String | Courier ID embedding restaurant code (e.g. `INDORES02DEL01`) | Parsed into `store_id` (`INDORES02`) and `rider_id` |
| `Delivery_person_Age` | Float | Courier age | Rider demographic |
| `Delivery_person_Ratings` | Float | Historical courier rating (1.0 to 5.0) | Courier performance indicator |
| `Restaurant_latitude` | Float | Restaurant geographic latitude | Origin coordinate |
| `Restaurant_longitude` | Float | Restaurant geographic longitude | Origin coordinate |
| `Delivery_location_latitude` | Float | Customer delivery destination latitude | Destination coordinate |
| `Delivery_location_longitude` | Float | Customer delivery destination longitude | Destination coordinate |
| `Order_Date` | String | Date order was placed (DD-MM-YYYY) | Temporal feature |
| `Time_Orderd` | String | Timestamp when customer placed order (HH:MM) | Order placement timestamp |
| `Time_Order_picked` | String | Timestamp when courier picked up completed food (HH:MM) | Preparation + pickup timestamp |
| `Weather_conditions` | String | Atmospheric weather (Sunny, Stormy, Sandstorms, Cloudy, Fog, Windy) | Operational context |
| `Road_traffic_density` | String | Traffic level (Low, Medium, High, Jam) | Transit impediment indicator |
| `Vehicle_condition` | Integer | Mechanical condition of courier vehicle (0, 1, 2) | Speed & reliability factor |
| `Type_of_order` | String | Order meal type (Snack, Meal, Drinks, Buffet) | Kitchen workload & complexity proxy |
| `Type_of_vehicle` | String | Transport vehicle (motorcycle, scooter, electric_scooter, bicycle) | Rider transit mode |
| `multiple_deliveries` | Float | Count of concurrent orders assigned to rider (0, 1, 2, 3) | Rider capacity & delay factor |
| `Festival` | String | Festival period indicator (Yes, No) | Kitchen surge demand flag |
| `City` | String | Urban typology (Metropolitian, Urban, Semi-Urban) | Traffic & infrastructure tier |
| `Time_taken (min)` | Integer | Courier transit duration from store to customer | Travel time target variable |

---

## 3. Target Variables & Operational Derivations

### Target 1: Kitchen Food Preparation Time (`actual_prep_time_min`)
- **Observed Origin:** Calculated directly as the delta between `Time_Order_picked` and `Time_Orderd`.
- **Unit:** Continuous minutes.
- **Physical Interpretation:** Represents the operational time from order placement to the moment the kitchen completed the order and handed it to the courier.
- **P50 / P90 Prediction Target:** Trained via `HistGradientBoostingRegressor(loss='quantile')`.

### Target 2: Rider Travel / Transit Duration (`rider_travel_time_min`)
- **Observed Origin:** Available directly from `Time_taken (min)`.
- **Unit:** Continuous minutes.
- **Physical Interpretation:** Courier travel duration from restaurant pickup to doorstep drop-off, varying with distance, weather, traffic density, and vehicle type.

---

## 4. Data Quality Issues & Preprocessing Strategy

### Identified Anomalies:
1. **Timestamp Formatting Inconsistencies:** Some timestamps in the raw dataset appear as fractions of day (Excel serial format, e.g., `0.958333333`) or lack zero-padding (`9:20` vs `09:20`).
   - *Fix:* Implemented robust time parser handling both 24-hour HH:MM strings and floating day fractions.
2. **Overnight Midnight Wraps:** Orders placed before midnight (e.g., `23:55`) and picked up after midnight (`00:10` or `24:10`) generate negative deltas if naive subtraction is used.
   - *Fix:* Added modulo 24-hour wrap correction (`+ 24 * 60` minutes).
3. **Extreme Coordinate Outliers:** Certain records contain zero or inverted coordinates (e.g., latitude 0.0, longitude 0.0).
   - *Fix:* Coordinates outside valid subcontinental bounds are treated as missing and imputed using store/city centroid values.
4. **Missing Categoricals & Whitespace Artifacts:** Categories contain leading spaces (e.g. `' conditions Sunny'`, `'Jam '`).
   - *Fix:* Applied `.strip()` and standardized labels into canonical categories.
5. **Kitchen Queue Depth & Workload:** Raw records represent individual transactions.
   - *Fix:* Computed live active store workload and concurrent orders using SQL window functions (`COUNT(*) OVER (PARTITION BY store_id)`), and simulated chronological order stream to simulate real kitchen backlogs.

---

## 5. Leakage Prevention Protocol

To ensure industry-grade ML integrity:
- **No Future Timestamps:** Features only include data available *at or before order placement timestamp*.
- **No Delivery Duration in Prep Model:** `Time_taken (min)` is strictly withheld when predicting food preparation time.
- **Chronological Split:** Test sets are partitioned chronologically by `Order_Date` and order timestamp to mirror real-world inference.
- **Target Segregation:** Food preparation time and rider travel time models are trained as independent functional units.

---

## 6. Dataset Limitations & Ethical Transparency

1. **Kitchen Step Granularity:** The dataset records `Time_Order_picked` rather than separate "Cooking Done" vs "Packing Done" events. In the operational dispatch simulator, packaging duration is modeled with an empirical operational buffer (3 minutes).
2. **Order Item Counts:** Raw data indicates meal type (`Snack`, `Meal`, `Drinks`, `Buffet`) rather than raw SKU counts. We synthesize realistic item count distributions conditioned on order type (e.g., Snack = 1-3 items, Meal = 2-5 items, Buffet = 5-12 items) to provide operational realism.
3. **No Fabricated Data:** All baseline models are trained on the genuine 45,584 records.
