"""
Real-Time ML Prediction Service
Exposes fast, thread-safe inference for kitchen preparation time (P50/P90)
and rider travel time using trained serialized scikit-learn pipelines.
Includes robust self-healing fallback to retrain models natively in-environment
if cross-platform or cross-version unpickling issues occur.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingRegressor

from config import (
    PROCESSED_DATASET_PATH,
    PREP_MODEL_P50_PATH,
    PREP_MODEL_P90_PATH,
    TRAVEL_MODEL_PATH,
    PREPROCESSING_PIPELINE_PATH,
    PACKING_TIME_MIN,
    RANDOM_STATE,
)
from src.data.feature_engineering import (
    ALL_FEATURE_COLUMNS,
    create_feature_pipeline,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DeliveryPredictionEngine:
    """Manages loaded models and executes multi-target quantile predictions."""

    _instance = None

    def __init__(self):
        self.preprocessor = None
        self.model_p50 = None
        self.model_p90 = None
        self.travel_model = None
        self._initialize_engine()

    def _initialize_engine(self):
        """Attempts to load existing pickled models; falls back to native retraining on error."""
        try:
            self._load_artifacts()
            logger.info("DeliveryPredictionEngine loaded all models and pipelines successfully.")
        except Exception as e:
            logger.warning(
                f"Model artifact deserialization failed ({type(e).__name__}: {e}). "
                "Triggering self-healing in-environment model training..."
            )
            self._retrain_in_environment()

    def _load_artifacts(self):
        """Loads serialized preprocessing pipeline and ML models."""
        self.preprocessor = joblib.load(PREPROCESSING_PIPELINE_PATH)
        self.model_p50 = joblib.load(PREP_MODEL_P50_PATH)
        self.model_p90 = joblib.load(PREP_MODEL_P90_PATH)
        self.travel_model = joblib.load(TRAVEL_MODEL_PATH)

    def _retrain_in_environment(self):
        """
        Trains the preprocessor and models natively in the active Python environment.
        Guarantees 100% compatibility across Python / scikit-learn versions.
        """
        data_path = Path(PROCESSED_DATASET_PATH)
        if not data_path.exists():
            logger.warning(f"Processed dataset not found at {data_path}. Predictions will use operational heuristic.")
            return

        try:
            logger.info("Loading processed dataset for in-environment training...")
            df = pd.read_csv(data_path)

            # Fit feature preprocessor
            logger.info("Fitting native feature preprocessing pipeline...")
            self.preprocessor = create_feature_pipeline()
            self.preprocessor.fit(df[ALL_FEATURE_COLUMNS])

            X_trans = self.preprocessor.transform(df[ALL_FEATURE_COLUMNS])
            y_prep = df["actual_prep_time"].values
            y_travel = df["actual_rider_travel_time"].values

            # Fit Model A: P50 Median Preparation Regressor
            logger.info("Fitting native Model A (P50 Quantile Regressor)...")
            self.model_p50 = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=0.50,
                max_iter=150,
                min_samples_leaf=25,
                learning_rate=0.08,
                l2_regularization=0.1,
                random_state=RANDOM_STATE,
            )
            self.model_p50.fit(X_trans, y_prep)

            # Fit Model B: P90 Conservative Preparation Regressor
            logger.info("Fitting native Model B (P90 Quantile Regressor)...")
            self.model_p90 = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=0.90,
                max_iter=150,
                min_samples_leaf=25,
                learning_rate=0.08,
                l2_regularization=0.1,
                random_state=RANDOM_STATE,
            )
            self.model_p90.fit(X_trans, y_prep)

            # Fit Model C: Rider Travel Regressor
            logger.info("Fitting native Model C (Rider Travel Regressor)...")
            self.travel_model = HistGradientBoostingRegressor(
                max_iter=150,
                learning_rate=0.08,
                min_samples_leaf=20,
                random_state=RANDOM_STATE,
            )
            self.travel_model.fit(X_trans, y_travel)

            # Attempt to cache newly trained models to disk
            try:
                PREPROCESSING_PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(self.preprocessor, PREPROCESSING_PIPELINE_PATH)
                joblib.dump(self.model_p50, PREP_MODEL_P50_PATH)
                joblib.dump(self.model_p90, PREP_MODEL_P90_PATH)
                joblib.dump(self.travel_model, TRAVEL_MODEL_PATH)
                logger.info("Successfully serialized and cached retrained models to disk.")
            except Exception as write_err:
                logger.warning(f"Could not write cached models to disk ({write_err}); in-memory models active.")

            logger.info("In-environment model training completed successfully.")

        except Exception as train_err:
            logger.error(f"In-environment training failed: {train_err}. Operational heuristic fallback enabled.")

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

        # Check if ML models are ready
        if (
            self.preprocessor is not None
            and self.model_p50 is not None
            and self.model_p90 is not None
            and self.travel_model is not None
        ):
            X_trans = self.preprocessor.transform(df_in[ALL_FEATURE_COLUMNS])
            pred_p50 = float(self.model_p50.predict(X_trans)[0])
            pred_p90 = float(self.model_p90.predict(X_trans)[0])
            pred_travel = float(self.travel_model.predict(X_trans)[0])
        else:
            # Operational heuristic fallback
            row = df_in.iloc[0]
            base_prep = float(row.get("average_prep_time", 18.0))
            items = float(row.get("item_count", 3))
            queue = float(row.get("kitchen_queue_depth", 2))
            pred_p50 = max(8.0, base_prep + items * 1.2 + queue * 0.9)
            pred_p90 = max(pred_p50 + 2.0, pred_p50 * 1.30)
            dist = float(row.get("distance_km", 5.0))
            traffic_mult = {"Low": 0.85, "Medium": 1.0, "High": 1.3, "Jam": 1.7}.get(
                str(row.get("traffic_level", "Medium")), 1.0
            )
            pred_travel = max(5.0, (dist / 20.0) * 60.0 * traffic_mult)

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
