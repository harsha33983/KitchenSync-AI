"""
Unit and Integration Tests for SQLite Database and SQL Window Functions
"""

import pytest
import sqlite3
import pandas as pd
from datetime import datetime
from sqlalchemy import text

from config import DATABASE_FILE, POWERBI_DIR
from src.database.connection import init_database, get_db_session, calculate_active_kitchen_orders, engine
from src.database.models import Store, Order, Rider, PerformanceMetric, DispatchPrediction
from src.services.order_service import order_service
from src.utils.export_powerbi import export_powerbi_datasets


def test_sqlite_db_and_foreign_keys():
    """Verify that SQLite database is created and foreign keys are enforced."""
    init_database()
    assert DATABASE_FILE.exists(), f"Database file not found at {DATABASE_FILE}"

    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA foreign_keys;")).fetchone()
        assert res[0] == 1, "SQLite PRAGMA foreign_keys is not ON"


def test_order_creation_and_window_function():
    """
    Verify order creation, persistence, and that the SQLite WINDOW FUNCTION
    correctly includes the newly inserted order in the store's active queue.
    """
    with get_db_session() as s:
        # Pick first available store
        store = s.query(Store).first()
        assert store is not None, "No stores available in database"
        store_id = store.store_id

        # Pre-insertion active queue depth
        initial_queue = calculate_active_kitchen_orders(s, store_id)

        # Create new order
        res = order_service.create_order(
            store_id=store_id,
            item_count=3,
            distance_km=4.5,
            traffic_level="Low",
            weather_condition="Sunny",
            session=s,
        )
        new_order_id = res["order_id"]

        # Post-insertion active queue depth
        new_queue = calculate_active_kitchen_orders(s, store_id)
        assert new_queue == initial_queue + 1, f"Window function failed to increment active queue: before={initial_queue}, after={new_queue}"

        # Verify order in DB
        db_order = s.query(Order).filter(Order.order_id == new_order_id).first()
        assert db_order is not None
        assert db_order.order_status == "PLACED"


def test_order_lifecycle_metrics():
    """Verify lifecycle status transition and performance metrics generation upon delivery."""
    with get_db_session() as s:
        store = s.query(Store).first()
        res = order_service.create_order(
            store_id=store.store_id,
            item_count=2,
            distance_km=3.0,
            session=s,
        )
        oid = res["order_id"]

        # Transition to DELIVERED
        success = order_service.update_order_status(oid, "DELIVERED", session=s)
        assert success is True

        # Check performance metrics created
        metric = s.query(PerformanceMetric).filter(PerformanceMetric.order_id == oid).first()
        assert metric is not None
        assert metric.food_wait_for_rider >= 0.0
        assert metric.rider_wait_for_food >= 0.0


def test_powerbi_exports():
    """Verify that Power BI export generates all 5 CSV files with valid records."""
    export_powerbi_datasets()

    expected_files = [
        "fact_orders.csv",
        "dim_stores.csv",
        "dim_riders.csv",
        "dim_date.csv",
        "dispatch_performance.csv",
        "measures.dax",
        "POWER_BI_GUIDE.md",
    ]

    for fname in expected_files:
        fpath = POWERBI_DIR / fname
        assert fpath.exists(), f"Power BI deliverable {fname} not found in {POWERBI_DIR}"
        if fname.endswith(".csv"):
            df = pd.read_csv(fpath)
            assert len(df) > 0, f"Exported {fname} is empty"
