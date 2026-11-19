"""
Unit and Integration Tests for Rider Dispatch Optimization Engine
Includes mandatory test scenarios A, B, and C, and wait calculations.
"""

import pytest
from datetime import datetime, timedelta

from src.dispatch.dispatch_optimizer import DispatchOptimizer, default_optimizer


def test_mandatory_scenario_a():
    """
    Mandatory Scenario A:
    - Food preparation: 25 minutes.
    - Rider travel: 15 minutes.
    - Expected dispatch delay: 10 minutes.
    """
    delay = default_optimizer.calculate_dispatch_delay(prep_time_min=25.0, travel_time_min=15.0)
    assert delay == 10.0, f"Scenario A failed: expected 10.0 min, got {delay}"


def test_mandatory_scenario_b():
    """
    Mandatory Scenario B:
    - Food preparation: 10 minutes.
    - Rider travel: 15 minutes.
    - Expected dispatch delay: 0 minutes (immediate dispatch).
    """
    delay = default_optimizer.calculate_dispatch_delay(prep_time_min=10.0, travel_time_min=15.0)
    assert delay == 0.0, f"Scenario B failed: expected 0.0 min, got {delay}"


def test_mandatory_scenario_c():
    """
    Mandatory Scenario C:
    - Food preparation: 30 minutes.
    - Rider travel: 10 minutes.
    - Expected dispatch delay: 20 minutes.
    """
    delay = default_optimizer.calculate_dispatch_delay(prep_time_min=30.0, travel_time_min=10.0)
    assert delay == 20.0, f"Scenario C failed: expected 20.0 min, got {delay}"


def test_wait_times_calculation():
    """Verify calculation of food wait and rider wait times."""
    now = datetime(2026, 11, 18, 12, 0, 0)
    
    # Case 1: Rider arrives 5 minutes AFTER food is ready -> Food waits 5 min, Rider waits 0 min
    food_ready_1 = now
    rider_arrival_1 = now + timedelta(minutes=5)
    waits_1 = default_optimizer.calculate_wait_times(food_ready_1, rider_arrival_1)
    assert waits_1["food_wait_for_rider_min"] == 5.0
    assert waits_1["rider_wait_for_food_min"] == 0.0

    # Case 2: Rider arrives 7 minutes BEFORE food is ready -> Food waits 0 min, Rider waits 7 min
    food_ready_2 = now
    rider_arrival_2 = now - timedelta(minutes=7)
    waits_2 = default_optimizer.calculate_wait_times(food_ready_2, rider_arrival_2)
    assert waits_2["food_wait_for_rider_min"] == 0.0
    assert waits_2["rider_wait_for_food_min"] == 7.0

    # Case 3: Perfect synchronization -> Both wait 0 min
    waits_3 = default_optimizer.calculate_wait_times(now, now)
    assert waits_3["food_wait_for_rider_min"] == 0.0
    assert waits_3["rider_wait_for_food_min"] == 0.0


def test_full_dispatch_optimization_flow():
    """Verify complete dispatch optimization output structure."""
    opt_res = default_optimizer.optimize_dispatch(
        predicted_prep_time_p50=22.0,
        predicted_prep_time_p90=26.0,
        predicted_rider_travel_time=14.0,
        current_time=datetime(2026, 11, 18, 18, 0, 0),
        rider_available=True,
    )

    assert "p50_plan" in opt_res
    assert "p90_plan" in opt_res
    # Delay P50: 22 - 14 = 8 min
    assert opt_res["p50_plan"]["dispatch_delay_min"] == 8.0
    # Delay P90: 26 - 14 = 12 min
    assert opt_res["p90_plan"]["dispatch_delay_min"] == 12.0
    assert "HOLD rider dispatch" in opt_res["p50_plan"]["explanation"]
