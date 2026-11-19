"""
Unit and Integration Tests for Data Preprocessing and Feature Engineering
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from config import RAW_DATA_DIR, PROCESSED_DATASET_PATH, PREPROCESSING_PIPELINE_PATH
from src.data.preprocessing import parse_time_to_minutes, haversine_distance_km, clean_and_standardize_raw_data
from src.data.feature_engineering import engineer_features, ALL_FEATURE_COLUMNS, NUMERICAL_FEATURES


def test_raw_dataset_exists():
    """Verify that the raw downloaded dataset exists and has valid records."""
    raw_path = RAW_DATA_DIR / "zomato_delivery_raw.csv"
    assert raw_path.exists(), f"Raw dataset not found at {raw_path}"
    df = pd.read_csv(raw_path, nrows=50)
    assert len(df) == 50
    assert "Delivery_person_ID" in df.columns
    assert "Time_Orderd" in df.columns


def test_time_parsing():
    """Verify time parsing for standard 24h formats and Excel day fractions."""
    # Standard string format
    assert parse_time_to_minutes("11:30") == 690.0
    assert parse_time_to_minutes("00:15") == 15.0
    assert parse_time_to_minutes("23:45") == 1425.0
    # Day fractions
    frac_val = 0.5  # 12:00 PM = 720 min
    assert parse_time_to_minutes(frac_val) == 720.0
    # Null or invalid handling
    assert np.isnan(parse_time_to_minutes(None))
    assert np.isnan(parse_time_to_minutes("invalid_time"))


def test_haversine_distance():
    """Verify geodesic distance calculation on known benchmark coordinates."""
    # Distance between Jaipur (26.9124, 75.7873) and nearby point (~10 km away)
    lat1, lon1 = 26.9124, 75.7873
    lat2, lon2 = 26.9800, 75.8500
    dist = haversine_distance_km(lat1, lon1, lat2, lon2)
    assert 5.0 < dist < 15.0, f"Expected approx 9-11 km, got {dist}"


def test_feature_engineering_pipeline():
    """Verify feature engineering produces all required columns with zero missing values."""
    assert PROCESSED_DATASET_PATH.exists(), f"Processed dataset not found at {PROCESSED_DATASET_PATH}"
    df = pd.read_csv(PROCESSED_DATASET_PATH, nrows=100)

    # Check all required features exist
    for col in ALL_FEATURE_COLUMNS:
        assert col in df.columns, f"Missing engineered column: {col}"

    # Verify no nulls in feature subset
    assert df[ALL_FEATURE_COLUMNS].isna().sum().sum() == 0, "Null values found in engineered features"

    # Verify targets exist and are in valid ranges
    assert "actual_prep_time" in df.columns
    assert df["actual_prep_time"].min() >= 5.0
    assert df["actual_prep_time"].max() <= 60.0
