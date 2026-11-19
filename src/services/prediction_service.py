"""
Prediction Service
Coordinates feature preparation, model inference, and operational explanations
for incoming orders and re-evaluations.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from src.models.predict import DeliveryPredictionEngine
from src.dispatch.dispatch_optimizer import default_optimizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PredictionService:
    """Provides high-level ML predictions and dispatch guidance."""

    def __init__(self):
        self.engine = DeliveryPredictionEngine.get_instance()
        self.optimizer = default_optimizer

    def predict_for_order(
        self,
        store_id: str,
        item_count: int,
        distance_km: float,
        traffic_level: str,
        weather_condition: str,
        kitchen_queue_depth: int = 1,
        average_prep_time: float = 18.0,
        vehicle_type: str = "Scooter",
        current_time: datetime = None,
        rider_available: bool = True,
    ) -> Dict[str, Any]:
        """Runs full ML pipeline and dispatch optimization for an order."""
        if current_time is None:
            current_time = datetime.utcnow()

        hour_of_day = current_time.hour
        day_of_week = current_time.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        peak_hour = 1 if hour_of_day in [12, 13, 14, 19, 20, 21, 22] else 0

        store_load = round((kitchen_queue_depth * 1.2) + (peak_hour * 1.5) + (is_weekend * 0.8), 2)
        order_complexity = round(2.0 + 0.15 * item_count, 2)
        estimated_travel_time = round((distance_km / 20.0) * 60.0, 1)

        input_features = {
            "item_count": item_count,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "kitchen_queue_depth": kitchen_queue_depth,
            "average_prep_time": average_prep_time,
            "store_load": store_load,
            "distance_km": distance_km,
            "rider_availability": 8 if rider_available else 1,
            "estimated_travel_time": estimated_travel_time,
            "peak_hour": peak_hour,
            "order_complexity": order_complexity,
            "traffic_level": traffic_level,
            "weather_condition": weather_condition,
            "vehicle_type": vehicle_type,
        }

        # 1. Run ML Model Predictions
        ml_preds = self.engine.predict(input_features)

        # 2. Run Dispatch Optimization
        dispatch_plan = self.optimizer.optimize_dispatch(
            predicted_prep_time_p50=ml_preds["predicted_prep_time_p50"],
            predicted_prep_time_p90=ml_preds["predicted_prep_time_p90"],
            predicted_rider_travel_time=ml_preds["predicted_rider_travel_time"],
            current_time=current_time,
            rider_available=rider_available,
            kitchen_queue_depth=kitchen_queue_depth,
            store_load=store_load,
        )

        return {
            "ml_predictions": ml_preds,
            "dispatch_plan": dispatch_plan,
            "features_used": input_features,
        }


# Singleton instance
prediction_service = PredictionService()
