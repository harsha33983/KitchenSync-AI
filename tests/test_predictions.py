"""
Unit and Integration Tests for Machine Learning Models and Quantile Inferences
"""

import pytest
import json
import numpy as np

from config import (
    PREP_MODEL_P50_PATH,
    PREP_MODEL_P90_PATH,
    TRAVEL_MODEL_PATH,
    PREPROCESSING_PIPELINE_PATH,
    EVALUATION_REPORT_PATH,
)
from src.models.predict import DeliveryPredictionEngine, predict_order_times


def test_model_artifacts_exist():
    """Verify that all trained model files and serialization pipelines exist."""
    assert PREP_MODEL_P50_PATH.exists(), "prep_time_p50.pkl not found"
    assert PREP_MODEL_P90_PATH.exists(), "prep_time_p90.pkl not found"
    assert TRAVEL_MODEL_PATH.exists(), "rider_travel_model.pkl not found"
    assert PREPROCESSING_PIPELINE_PATH.exists(), "preprocessing_pipeline.pkl not found"
    assert EVALUATION_REPORT_PATH.exists(), "model_evaluation.json not found"


def test_prediction_engine_p50_p90():
    """Verify P50 and P90 predictions on a realistic test input."""
    sample_features = {
        "item_count": 4,
        "hour_of_day": 19,
        "day_of_week": 4,
        "is_weekend": 0,
        "kitchen_queue_depth": 3,
        "average_prep_time": 18.0,
        "store_load": 4.5,
        "distance_km": 6.2,
        "rider_availability": 6,
        "traffic_level": "Medium",
        "weather_condition": "Sunny",
        "vehicle_type": "Scooter",
    }
    preds = predict_order_times(sample_features)

    assert "predicted_prep_time_p50" in preds
    assert "predicted_prep_time_p90" in preds
    assert "predicted_rider_travel_time" in preds

    p50 = preds["predicted_prep_time_p50"]
    p90 = preds["predicted_prep_time_p90"]
    travel = preds["predicted_rider_travel_time"]

    # Basic physical sanity
    assert 8.0 <= p50 <= 45.0, f"Unrealistic P50 prep time: {p50}"
    assert 8.0 <= p90 <= 50.0, f"Unrealistic P90 prep time: {p90}"
    assert 5.0 <= travel <= 60.0, f"Unrealistic rider travel time: {travel}"

    # Non-crossing quantiles invariant
    assert p90 >= p50, f"Quantile crossing: P90 ({p90}) < P50 ({p50})"


def test_evaluation_report_metrics():
    """Verify evaluation report content and actual test metric thresholds."""
    with open(EVALUATION_REPORT_PATH, "r") as f:
        rep = json.load(f)

    assert "models" in rep
    models = rep["models"]
    assert "prep_time_p50" in models
    assert "prep_time_p90" in models
    assert "rider_travel_model" in models

    p50_m = models["prep_time_p50"]
    assert p50_m["mae_minutes"] < 5.0, "P50 MAE too high"
    assert p50_m["r2_score"] > 0.50, "P50 R2 too low"

    p90_m = models["prep_time_p90"]
    assert 80.0 <= p90_m["empirical_coverage_percentage"] <= 98.0, "P90 empirical coverage out of target bounds"
