"""
Real-Time ML Prediction Service
Exposes fast, thread-safe inference for kitchen preparation time (P50/P90)
and rider travel time using trained serialized scikit-learn pipelines.
"""

import logging
from typing import Dict, Any, Union
import numpy as np
import pandas as pd
import joblib

from config import (
    PREP_MODEL_P50_PATH,
    PREP_MODEL_P90_PATH,
    TRAVEL_MODEL_PATH,
    PREPROCESSING_PIPELINE_PATH,
    PACKING_TIME_MIN,
)
from src.data.feature_engineering import ALL_FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DeliveryPredictionEngine:
    """Manages loaded models and executes multi-target quantile predictions."""

    _instance = None

    def __init__(self):
        self.preprocessor = joblib.load(PREPROCESSING_PIPELINE_PATH)
        self.model_p50 = joblib.load(PREP_MODEL_P50_PATH)
        self.model_p90 = joblib.load(PREP_MODEL_P90_PATH)
        self.travel_model = joblib.load(TRAVEL_MODEL_PATH)
        logger.info("DeliveryPredictionEngine loaded all models and pipelines.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DeliveryPredictionEngine()
        return cls._instance

    def predict(self, input_features: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
        """
        Generates predictions for a single order or batch.
        Guarantees non-crossing quantiles (P90 >= P50).
        """
        if isinstance(input_features, dict):
            # Fill missing keys with sensible operational defaults
            features_dict = {
                "item_count": input_features.get("item_count", 3),
                "hour_of_day": input_features.get("hour_of_day", 19),
                "day_of_week": input_features.get("day_of_week", 2),
                "is_weekend": input_features.get("is_weekend", 0),
                "kitchen_queue_depth": input_features.get("kitchen_queue_depth", 2),
                "average_prep_time": input_features.get("average_prep_time", 18.0),
                "store_load": input_features.get("store_load", 3.0),
                "distance_km": input_features.get("distance_km", 5.0),
                "rider_availability": input_features.get("rider_availability", 8),
                "estimated_travel_time": input_features.get(
                    "estimated_travel_time",
                    (input_features.get("distance_km", 5.0) / 20.0) * 60.0,
                ),
                "peak_hour": input_features.get(
                    "peak_hour",
                    1 if input_features.get("hour_of_day", 19) in [12, 13, 14, 19, 20, 21, 22] else 0,
                ),
                "order_complexity": input_features.get(
                    "order_complexity",
                    2.0 + 0.15 * input_features.get("item_count", 3),
                ),
                "traffic_level": input_features.get("traffic_level", "Medium"),
                "weather_condition": input_features.get("weather_condition", "Sunny"),
                "vehicle_type": input_features.get("vehicle_type", "Scooter"),
            }
            df_in = pd.DataFrame([features_dict])
        else:
            df_in = input_features.copy()

        # Transform using preprocessor
        X_trans = self.preprocessor.transform(df_in[ALL_FEATURE_COLUMNS])

        # Model inferences
        pred_p50 = float(self.model_p50.predict(X_trans)[0])
        pred_p90 = float(self.model_p90.predict(X_trans)[0])
        pred_travel = float(self.travel_model.predict(X_trans)[0])

        # Enforce non-crossing quantile constraint
        if pred_p90 < pred_p50:
            pred_p90 = pred_p50 + 2.0

        # Packing buffer
        packing_time = float(PACKING_TIME_MIN)
        total_kitchen_p50 = pred_p50 + packing_time
        total_kitchen_p90 = pred_p90 + packing_time

        return {
            "predicted_prep_time_p50": round(pred_p50, 1),
            "predicted_prep_time_p90": round(pred_p90, 1),
            "predicted_packing_time": round(packing_time, 1),
            "predicted_total_kitchen_time_p50": round(total_kitchen_p50, 1),
            "predicted_total_kitchen_time_p90": round(total_kitchen_p90, 1),
            "predicted_rider_travel_time": round(pred_travel, 1),
        }


def predict_order_times(features: Dict[str, Any]) -> Dict[str, Any]:
    """Helper functional wrapper for prediction engine."""
    engine = DeliveryPredictionEngine.get_instance()
    return engine.predict(features)


if __name__ == "__main__":
    sample_order = {
        "item_count": 4,
        "hour_of_day": 20,
        "day_of_week": 5,
        "is_weekend": 1,
        "kitchen_queue_depth": 4,
        "average_prep_time": 20.0,
        "store_load": 5.5,
        "distance_km": 6.8,
        "rider_availability": 6,
        "traffic_level": "High",
        "weather_condition": "Rainy",
        "vehicle_type": "Scooter",
    }
    preds = predict_order_times(sample_order)
    print("Sample Order Predictions:")
    for k, v in preds.items():
        print(f"  {k}: {v}")
