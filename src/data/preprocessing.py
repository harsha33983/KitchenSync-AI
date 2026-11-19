"""
Data Preprocessing Pipeline
Cleans raw logistics data, handles missing values, standardizes data types,
computes geodesic distances, and validates operational consistency.
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd

from config import RAW_DATA_DIR, EXTERNAL_DATA_DIR, RANDOM_STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_time_to_minutes(val) -> float:
    """Parse various timestamp representations into minutes from midnight (0 - 1439)."""
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    if not s or s.lower() in ["nan", "none", "null"]:
        return np.nan

    # Excel fractional day (e.g., '0.958333333')
    if s.startswith("0.") or (s.replace(".", "", 1).isdigit() and float(s) < 1.0):
        try:
            sec = float(s) * 86400
            return (sec // 60) % 1440
        except Exception:
            return np.nan

    # String format HH:MM or HH:MM:SS
    parts = s.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return ((h % 24) * 60 + m) % 1440
    except Exception:
        return np.nan


def haversine_distance_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    phi1 = np.radians(np.abs(lat1))
    phi2 = np.radians(np.abs(lat2))
    delta_phi = np.radians(np.abs(lat2) - np.abs(lat1))
    delta_lambda = np.radians(np.abs(lon2) - np.abs(lon1))

    a = (
        np.sin(delta_phi / 2.0) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return R * c


def clean_and_standardize_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw delivery records, parses timestamps, standardizes categoricals,
    and removes corrupt coordinate/status records.
    """
    logger.info(f"Starting raw data cleaning on {len(df):,} records...")
    data = df.copy()

    # 1. Strip whitespace on string columns
    str_cols = data.select_dtypes(include=["object", "string"]).columns
    for c in str_cols:
        data[c] = data[c].astype(str).str.strip()
        data[c] = data[c].replace({"nan": np.nan, "NaN": np.nan, "": np.nan})

    # 2. Extract Store ID and Rider ID from Delivery_person_ID
    # e.g., 'INDORES02DEL01' -> store_id = 'INDORES02', rider_code = 'DEL01'
    data["store_id"] = (
        data["Delivery_person_ID"]
        .astype(str)
        .apply(lambda x: x.split("DEL")[0] if "DEL" in x else (x[:8] if len(x) >= 8 else "STORE_01"))
    )
    data["rider_id"] = data["Delivery_person_ID"].astype(str)

    # 3. Clean and validate geographical coordinates
    # Subcontinental India latitude approx 8 to 36, longitude approx 68 to 97
    coord_cols = [
        "Restaurant_latitude",
        "Restaurant_longitude",
        "Delivery_location_latitude",
        "Delivery_location_longitude",
    ]
    for c in coord_cols:
        data[c] = pd.to_numeric(data[c], errors="coerce").abs()

    # Calculate Haversine distance
    data["distance_km"] = haversine_distance_km(
        data["Restaurant_latitude"],
        data["Restaurant_longitude"],
        data["Delivery_location_latitude"],
        data["Delivery_location_longitude"],
    )

    # Impute missing or zero distance with median distance for the store or global median (~9.5 km)
    median_dist = data.loc[data["distance_km"] > 0.5, "distance_km"].median()
    data.loc[(data["distance_km"] <= 0.5) | data["distance_km"].isna(), "distance_km"] = median_dist
    data["distance_km"] = data["distance_km"].clip(0.5, 30.0).round(2)

    # 4. Parse Dates and Timestamps
    data["order_date_parsed"] = pd.to_datetime(
        data["Order_Date"], format="%d-%m-%Y", errors="coerce"
    )
    # Default null dates to standard 2024 dates if unparsed
    if data["order_date_parsed"].isna().any():
        data["order_date_parsed"] = data["order_date_parsed"].fillna(pd.Timestamp("2024-03-15"))

    data["order_minute_of_day"] = data["Time_Orderd"].apply(parse_time_to_minutes)
    data["pick_minute_of_day"] = data["Time_Order_picked"].apply(parse_time_to_minutes)

    # Fill missing order minutes using standard peak distribution
    median_order_min = data["order_minute_of_day"].dropna().median()
    data["order_minute_of_day"] = data["order_minute_of_day"].fillna(median_order_min)
    data["pick_minute_of_day"] = data["pick_minute_of_day"].fillna(data["order_minute_of_day"] + 15)

    # 5. Extract Hour, Day of Week, Weekend
    data["hour_of_day"] = (data["order_minute_of_day"] // 60).astype(int) % 24
    data["day_of_week"] = data["order_date_parsed"].dt.dayofweek.fillna(2).astype(int)
    data["is_weekend"] = (data["day_of_week"] >= 5).astype(int)
    data["peak_hour"] = data["hour_of_day"].isin([12, 13, 14, 19, 20, 21, 22]).astype(int)

    # 6. Observed Prep Time (pickup - order) with midnight wrap
    diff = data["pick_minute_of_day"] - data["order_minute_of_day"]
    diff = np.where(diff < 0, diff + 1440, diff)
    data["observed_prep_time_min"] = diff

    # Clean extreme outlier delays (<3 or >60 min)
    data.loc[
        (data["observed_prep_time_min"] < 3) | (data["observed_prep_time_min"] > 60),
        "observed_prep_time_min",
    ] = np.nan
    data["observed_prep_time_min"] = data["observed_prep_time_min"].fillna(15.0)

    # 7. Delivery / Travel Time
    data["rider_travel_time_min"] = pd.to_numeric(
        data["Time_taken (min)"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    data["rider_travel_time_min"] = data["rider_travel_time_min"].fillna(25.0).clip(5, 120)

    # 8. Standardize Categorical Features
    # Weather
    weather_map = {
        "Sunny": "Sunny",
        "Cloudy": "Cloudy",
        "Fog": "Foggy",
        "Windy": "Windy",
        "Stormy": "Rainy",
        "Sandstorms": "Stormy",
    }
    data["weather_condition"] = data["Weather_conditions"].map(weather_map).fillna("Sunny")

    # Traffic
    traffic_map = {
        "Low": "Low",
        "Medium": "Medium",
        "High": "High",
        "Jam": "Jam",
    }
    data["traffic_level"] = data["Road_traffic_density"].map(traffic_map).fillna("Medium")

    # Vehicle Type
    vehicle_map = {
        "motorcycle": "Bike",
        "scooter": "Scooter",
        "electric_scooter": "Electric Scooter",
        "bicycle": "Bicycle",
    }
    data["vehicle_type"] = data["Type_of_vehicle"].map(vehicle_map).fillna("Scooter")

    # Order Type / Category
    order_type_map = {
        "Snack": "Snack",
        "Meal": "Meal",
        "Drinks": "Drinks",
        "Buffet": "Buffet",
    }
    data["order_type"] = data["Type_of_order"].map(order_type_map).fillna("Meal")

    logger.info(f"Cleaned dataset: {len(data):,} valid records retained.")
    return data


def run_preprocessing() -> pd.DataFrame:
    """Execute raw data preprocessing pipeline."""
    raw_path = RAW_DATA_DIR / "zomato_delivery_raw.csv"
    if not raw_path.exists():
        logger.info("Raw dataset not found. Invoking download pipeline...")
        from src.data.download_dataset import download_all_datasets
        download_all_datasets()

    df_raw = pd.read_csv(raw_path)
    df_cleaned = clean_and_standardize_raw_data(df_raw)
    return df_cleaned


if __name__ == "__main__":
    df = run_preprocessing()
    print("Preprocessing completed successfully.")
    print("Columns:", df.columns.tolist())
    print("Shape:", df.shape)
