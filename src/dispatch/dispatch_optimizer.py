"""
Rider Dispatch Optimization Engine
Calculates optimal dispatch delays, recommended dispatch timestamps, expected arrival times,
and human-readable operational explanations.
Supports both P50 (median) and P90 (conservative) dispatch strategies.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config import DEFAULT_SAFETY_BUFFER_MIN, PACKING_TIME_MIN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DispatchOptimizer:
    """Core operational dispatch optimization engine."""

    def __init__(self, safety_buffer_min: float = 0.0):
        self.safety_buffer_min = safety_buffer_min

    @staticmethod
    def calculate_dispatch_delay(
        prep_time_min: float,
        travel_time_min: float,
        safety_buffer_min: float = 0.0,
    ) -> float:
        """
        Calculates raw optimal dispatch delay:
        optimal_dispatch_delay = max(0, prep_time - travel_time - safety_buffer)
        """
        raw_delay = prep_time_min - travel_time_min - safety_buffer_min
        return max(0.0, round(raw_delay, 1))

    @staticmethod
    def calculate_wait_times(
        food_ready_time: datetime,
        rider_arrival_time: datetime,
    ) -> Dict[str, float]:
        """
        Calculates food waiting for rider and rider waiting for food.
        food_wait_for_rider = max(0, rider_arrival_time - food_ready_time)
        rider_wait_for_food = max(0, food_ready_time - rider_arrival_time)
        """
        delta_sec = (rider_arrival_time - food_ready_time).total_seconds()
        delta_min = delta_sec / 60.0

        food_wait = max(0.0, round(delta_min, 1)) if delta_min > 0 else 0.0
        rider_wait = max(0.0, round(-delta_min, 1)) if delta_min < 0 else 0.0

        return {
            "food_wait_for_rider_min": food_wait,
            "rider_wait_for_food_min": rider_wait,
        }

    def generate_explanation(
        self,
        prep_time: float,
        travel_time: float,
        dispatch_delay: float,
        rider_available: bool = True,
        is_p90: bool = False,
    ) -> str:
        """Generates clear, context-aware operational explanation for dispatch personnel."""
        strategy = "Conservative P90" if is_p90 else "Standard P50"

        if not rider_available:
            return (
                f"[{strategy}] Warning: No immediate rider available in store vicinity. "
                f"High risk of food wait; prioritize rider reassignment immediately."
            )

        if dispatch_delay == 0.0:
            if travel_time >= prep_time:
                return (
                    f"[{strategy}] Dispatch rider IMMEDIATELY. Estimated travel duration ({travel_time:.1f}m) "
                    f"exceeds or matches food prep ({prep_time:.1f}m). Early dispatch ensures rider arrives "
                    f"right as the kitchen packages the order."
                )
            else:
                return (
                    f"[{strategy}] Dispatch rider IMMEDIATELY. Kitchen prep is short ({prep_time:.1f}m) "
                    f"relative to transit ({travel_time:.1f}m)."
                )
        else:
            return (
                f"[{strategy}] HOLD rider dispatch for {dispatch_delay:.1f} minutes. "
                f"Kitchen prep ({prep_time:.1f}m) is significantly longer than rider travel ({travel_time:.1f}m). "
                f"Staging dispatch prevents rider from idling at the restaurant for {dispatch_delay:.1f}m."
            )

    def optimize_dispatch(
        self,
        predicted_prep_time_p50: float,
        predicted_prep_time_p90: float,
        predicted_rider_travel_time: float,
        current_time: Optional[datetime] = None,
        rider_available: bool = True,
        kitchen_queue_depth: int = 1,
        store_load: float = 1.0,
        apply_buffer: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes full dispatch optimization analysis.
        Returns dispatch delays, timestamps, wait projections, and operational explanations.
        """
        if current_time is None:
            current_time = datetime.utcnow()

        buffer = self.safety_buffer_min if apply_buffer else 0.0

        # 1. Standard (P50) Dispatch
        delay_p50 = self.calculate_dispatch_delay(
            prep_time_min=predicted_prep_time_p50,
            travel_time_min=predicted_rider_travel_time,
            safety_buffer_min=buffer,
        )
        dispatch_ts_p50 = current_time + timedelta(minutes=delay_p50)
        arrival_ts_p50 = dispatch_ts_p50 + timedelta(minutes=predicted_rider_travel_time)
        food_ready_ts_p50 = current_time + timedelta(minutes=predicted_prep_time_p50)
        waits_p50 = self.calculate_wait_times(food_ready_ts_p50, arrival_ts_p50)
        expl_p50 = self.generate_explanation(
            predicted_prep_time_p50,
            predicted_rider_travel_time,
            delay_p50,
            rider_available,
            is_p90=False,
        )

        # 2. Conservative (P90) Dispatch
        delay_p90 = self.calculate_dispatch_delay(
            prep_time_min=predicted_prep_time_p90,
            travel_time_min=predicted_rider_travel_time,
            safety_buffer_min=buffer,
        )
        dispatch_ts_p90 = current_time + timedelta(minutes=delay_p90)
        arrival_ts_p90 = dispatch_ts_p90 + timedelta(minutes=predicted_rider_travel_time)
        food_ready_ts_p90 = current_time + timedelta(minutes=predicted_prep_time_p90)
        waits_p90 = self.calculate_wait_times(food_ready_ts_p90, arrival_ts_p90)
        expl_p90 = self.generate_explanation(
            predicted_prep_time_p90,
            predicted_rider_travel_time,
            delay_p90,
            rider_available,
            is_p90=True,
        )

        return {
            "current_time": current_time,
            "predicted_prep_time_p50": predicted_prep_time_p50,
            "predicted_prep_time_p90": predicted_prep_time_p90,
            "predicted_rider_travel_time": predicted_rider_travel_time,
            "rider_available": rider_available,
            "kitchen_queue_depth": kitchen_queue_depth,
            "store_load": store_load,
            "p50_plan": {
                "dispatch_delay_min": delay_p50,
                "recommended_dispatch_timestamp": dispatch_ts_p50,
                "predicted_arrival_timestamp": arrival_ts_p50,
                "food_ready_timestamp": food_ready_ts_p50,
                "projected_food_wait_min": waits_p50["food_wait_for_rider_min"],
                "projected_rider_wait_min": waits_p50["rider_wait_for_food_min"],
                "explanation": expl_p50,
            },
            "p90_plan": {
                "dispatch_delay_min": delay_p90,
                "recommended_dispatch_timestamp": dispatch_ts_p90,
                "predicted_arrival_timestamp": arrival_ts_p90,
                "food_ready_timestamp": food_ready_ts_p90,
                "projected_food_wait_min": waits_p90["food_wait_for_rider_min"],
                "projected_rider_wait_min": waits_p90["rider_wait_for_food_min"],
                "explanation": expl_p90,
            },
        }


# Convenience Global Optimizer Instance
default_optimizer = DispatchOptimizer()


if __name__ == "__main__":
    # Test Scenario A: Prep = 25m, Travel = 15m -> Delay = 10m
    print("Testing Scenario A (Prep 25m, Travel 15m):")
    res_a = default_optimizer.calculate_dispatch_delay(25.0, 15.0)
    print(f"  Result: {res_a} min (Expected: 10.0 min)")
    assert res_a == 10.0, f"Scenario A failed: got {res_a}"

    # Test Scenario B: Prep = 10m, Travel = 15m -> Delay = 0m
    print("Testing Scenario B (Prep 10m, Travel 15m):")
    res_b = default_optimizer.calculate_dispatch_delay(10.0, 15.0)
    print(f"  Result: {res_b} min (Expected: 0.0 min)")
    assert res_b == 0.0, f"Scenario B failed: got {res_b}"

    # Test Scenario C: Prep = 30m, Travel = 10m -> Delay = 20m
    print("Testing Scenario C (Prep 30m, Travel 10m):")
    res_c = default_optimizer.calculate_dispatch_delay(30.0, 10.0)
    print(f"  Result: {res_c} min (Expected: 20.0 min)")
    assert res_c == 20.0, f"Scenario C failed: got {res_c}"

    print("\nAll 3 Mandatory Dispatch Test Scenarios PASSED successfully!")
