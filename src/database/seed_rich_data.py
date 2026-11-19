"""
Seed Rich Operational Data
Enriches the database with 500+ realistic multi-day delivery orders,
diverse restaurant branding, distinct traffic/weather conditions,
and accurate ML quantile predictions and dispatch performance metrics.
"""

import sys
import random
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
from sqlalchemy.orm import Session

from config import (
    DATABASE_FILE,
    ORDER_STATUS_PLACED,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_PACKING,
    ORDER_STATUS_DISPATCHED,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_CANCELLED,
)
from src.database.connection import get_db_session, init_database
from src.database.models import Store, Order, Rider, DispatchPrediction, PerformanceMetric, KitchenEvent
from src.models.predict import DeliveryPredictionEngine
from src.dispatch.dispatch_optimizer import default_optimizer
from src.utils.export_powerbi import export_powerbi_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

STORE_BRAND_CATALOG = {
    "AGRRES01": ("Central Gourmet Hub", "Downtown Metro", 16.5),
    "AGRRES010": ("Burger Craft & Brews", "Tech Boulevard", 14.0),
    "AGRRES02": ("Northside Artisan Pizzeria", "North Commercial Park", 19.5),
    "AGRRES03": ("Royal Dum Biryani & Grills", "South City Mall", 22.0),
    "AGRRES04": ("QuickBite Fast Food Co.", "Eastside IT Corridor", 12.5),
    "AGRRES05": ("GreenBowl Salad & Superfoods", "Financial District", 13.5),
    "AGRRES06": ("Dragon Wok Asian Street Kitchen", "Midtown Junction", 17.0),
    "AGRRES07": ("SweetCraving Patisserie & Bakes", "Heritage Quarter", 11.0),
    "AGRRES08": ("Coastal Wave Seafood & Curries", "Harbor Promenade", 23.5),
    "AGRRES09": ("Taco Fiesta Mexican Grill", "Westside Avenue", 15.0),
    "AGRRES11": ("Chai & Samosa Junction", "Metro Interchange", 10.5),
    "AGRRES12": ("Pasta Fresca Italian Trattoria", "University Square", 18.0),
    "AGRRES13": ("Tandoori Nights Barbecue Hub", "North Gate Bypass", 21.5),
    "AGRRES14": ("Siam Orchid Thai Bistro", "Lakeside Enclave", 19.0),
    "AGRRES15": ("Golden Spoon Multi-Cuisine Diner", "Suburban Plaza", 16.0),
    "AGRRES16": ("The Daily Roll Sushi Bar", "City Centre Atrium", 20.0),
    "AGRRES17": ("Falafel & Shawarma Oasis", "Trade Center Ring", 13.0),
    "AGRRES18": ("Smoky BBQ Pit House", "Industrial Estate Road", 24.0),
    "AGRRES19": ("Waffle & Crepe Factory", "Fashion Street Walkway", 12.0),
    "AGRRES20": ("Bao & Dim Sum Express", "Skyline Cyber City", 15.5),
    "ALHRES01": ("Grand Darbar Mughlai Feast", "Old Fort Road", 23.0),
    "ALHRES010": ("Kathi Roll Express", "Railway Station Road", 11.5),
    "ALHRES02": ("Southern Spices Chettinad Kitchen", "Civil Lines Main", 18.5),
    "ALHRES03": ("Urban Waffle & Shake Cafe", "Cantonment Plaza", 13.0),
    "ALHRES04": ("Momo Master Himalayan Kitchen", "Mall Mile Crossing", 14.5),
}

TRAFFIC_LEVELS = ["Low", "Medium", "High", "Jam"]
TRAFFIC_WEIGHTS = [0.35, 0.30, 0.20, 0.15]

WEATHER_CONDITIONS = ["Sunny", "Cloudy", "Rainy", "Foggy", "Windy", "Stormy"]
WEATHER_WEIGHTS = [0.40, 0.25, 0.15, 0.08, 0.07, 0.05]

VEHICLE_TYPES = ["Scooter", "Motorcycle", "Electric Bike", "Bicycle"]
VEHICLE_WEIGHTS = [0.55, 0.25, 0.15, 0.05]


def seed_rich_operational_data(total_orders: int = 500):
    """Generates 500+ realistic historical and active delivery orders."""
    init_database()
    random.seed(42)
    engine = DeliveryPredictionEngine.get_instance()
    optimizer = default_optimizer

    logger.info(f"Starting database enrichment with {total_orders} rich operational orders...")

    with get_db_session() as s:
        # 1. Update stores with realistic restaurant branding
        existing_stores = s.query(Store).all()
        for store in existing_stores:
            if store.store_id in STORE_BRAND_CATALOG:
                name, loc, prep = STORE_BRAND_CATALOG[store.store_id]
                store.store_name = f"{name} ({store.store_id})"
                store.location = loc
                store.average_prep_time = prep
        s.commit()
        logger.info(f"Updated metadata for {len(existing_stores)} dark stores.")

        # 2. Reset order-related tables for clean star-schema consistency
        s.query(PerformanceMetric).delete()
        s.query(DispatchPrediction).delete()
        s.query(KitchenEvent).delete()
        s.query(Order).delete()
        s.commit()
        logger.info("Cleared previous order records for high-fidelity regeneration.")

        stores = s.query(Store).all()
        store_map = {st.store_id: st for st in stores}
        store_ids = list(store_map.keys())

        # Define order distribution:
        # ~460 Delivered, ~12 Cancelled, ~28 Active
        num_cancelled = 12
        num_active = 28
        num_delivered = total_orders - num_cancelled - num_active

        order_specs = []
        for _ in range(num_delivered):
            order_specs.append(ORDER_STATUS_DELIVERED)
        for _ in range(num_cancelled):
            order_specs.append(ORDER_STATUS_CANCELLED)
        
        active_pool = [ORDER_STATUS_PLACED] * 12 + [ORDER_STATUS_PREPARING] * 8 + [ORDER_STATUS_PACKING] * 4 + [ORDER_STATUS_DISPATCHED] * 4
        order_specs.extend(active_pool[:num_active])
        random.shuffle(order_specs)

        now = datetime.utcnow()
        logger.info(f"Generating {len(order_specs)} orders across 30 days...")

        for i, target_status in enumerate(order_specs, start=1):
            order_id = f"ORD_{10000 + i}"
            st_id = random.choice(store_ids)
            st_obj = store_map[st_id]

            # Date/time generation
            if target_status in [ORDER_STATUS_DELIVERED, ORDER_STATUS_CANCELLED]:
                # Across the last 30 days
                day_offset = random.randint(1, 30)
                # Realistic hourly demand: peak lunch (12-14) or dinner (19-22) 65% of the time
                if random.random() < 0.65:
                    hour = random.choice([12, 13, 14, 19, 20, 21, 22])
                else:
                    hour = random.choice([9, 10, 11, 15, 16, 17, 18, 23])
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                order_time = (now - timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=second)
            else:
                # Active orders placed within the last 5 to 45 minutes
                mins_ago = random.randint(5, 45)
                order_time = now - timedelta(minutes=mins_ago)

            items = random.choices([1, 2, 3, 4, 5, 6, 7, 8], weights=[0.15, 0.25, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02])[0]
            dist = round(random.uniform(1.2, 14.5), 1)
            traffic = random.choices(TRAFFIC_LEVELS, weights=TRAFFIC_WEIGHTS)[0]
            weather = random.choices(WEATHER_CONDITIONS, weights=WEATHER_WEIGHTS)[0]
            queue_depth = random.randint(1, 6)

            # ML feature dictionary
            features = {
                "item_count": items,
                "hour_of_day": order_time.hour,
                "day_of_week": order_time.weekday(),
                "is_weekend": 1 if order_time.weekday() >= 5 else 0,
                "kitchen_queue_depth": queue_depth,
                "average_prep_time": st_obj.average_prep_time,
                "store_load": round((queue_depth * 1.2) + (1.5 if order_time.hour in [12, 13, 14, 19, 20, 21, 22] else 0.0), 2),
                "distance_km": dist,
                "rider_availability": 8,
                "estimated_travel_time": round((dist / 20.0) * 60.0, 1),
                "peak_hour": 1 if order_time.hour in [12, 13, 14, 19, 20, 21, 22] else 0,
                "order_complexity": round(2.0 + 0.15 * items, 2),
                "traffic_level": traffic,
                "weather_condition": weather,
                "vehicle_type": "Scooter",
            }

            preds = engine.predict(features)
            p50 = preds["predicted_prep_time_p50"]
            p90 = preds["predicted_prep_time_p90"]
            travel = preds["predicted_rider_travel_time"]

            # Dispatch Optimization Plan
            disp_plan = optimizer.optimize_dispatch(
                predicted_prep_time_p50=p50,
                predicted_prep_time_p90=p90,
                predicted_rider_travel_time=travel,
                current_time=order_time,
                rider_available=True,
                kitchen_queue_depth=queue_depth,
            )
            p50_plan = disp_plan["p50_plan"]
            dispatch_delay = p50_plan["dispatch_delay_min"]
            recommended_dispatch_time = p50_plan["recommended_dispatch_timestamp"]
            predicted_arrival_time = p50_plan["predicted_arrival_timestamp"]

            # Instantiate Order Entity
            order_ent = Order(
                order_id=order_id,
                store_id=st_id,
                order_timestamp=order_time,
                item_count=items,
                order_status=target_status,
                predicted_prep_time=p50,
                predicted_prep_time_p90=p90,
                distance_km=dist,
                traffic_level=traffic,
                weather_condition=weather,
            )

            # Performance and Timestamps based on final status
            if target_status == ORDER_STATUS_DELIVERED:
                # Realistic actual prep time with normal deviation around P50
                jitter = random.gauss(0.0, 1.2)
                actual_prep = round(max(8.0, min(45.0, p50 + jitter)), 1)
                order_ent.actual_prep_time = actual_prep

                food_ready = order_time + timedelta(minutes=actual_prep)
                order_ent.food_ready_timestamp = food_ready

                # Staged dispatch arrival
                transit_jitter = random.gauss(0.0, 1.5)
                actual_transit = round(max(5.0, travel + transit_jitter), 1)

                actual_arrival = recommended_dispatch_time + timedelta(minutes=actual_transit)
                pickup_time = max(food_ready, actual_arrival) + timedelta(minutes=random.uniform(0.5, 2.0))
                order_ent.pickup_timestamp = pickup_time

                customer_transit = actual_transit * random.uniform(0.9, 1.1)
                delivery_time = pickup_time + timedelta(minutes=customer_transit)
                order_ent.delivery_timestamp = delivery_time

                # Metrics calculation
                food_wait = round(max(0.0, (pickup_time - food_ready).total_seconds() / 60.0), 1)
                rider_wait = round(max(0.0, (food_ready - actual_arrival).total_seconds() / 60.0), 1)
                total_duration = (delivery_time - order_time).total_seconds() / 60.0
                sla_target = p90 + travel + 5.0
                is_on_time = bool(total_duration <= sla_target)

                metric_ent = PerformanceMetric(
                    order_id=order_id,
                    food_wait_for_rider=food_wait,
                    rider_wait_for_food=rider_wait,
                    on_time_delivery=is_on_time,
                    cancellation_flag=False,
                )
                s.add(metric_ent)

            elif target_status == ORDER_STATUS_CANCELLED:
                order_ent.actual_prep_time = None
                metric_ent = PerformanceMetric(
                    order_id=order_id,
                    food_wait_for_rider=0.0,
                    rider_wait_for_food=0.0,
                    on_time_delivery=False,
                    cancellation_flag=True,
                )
                s.add(metric_ent)

            else:
                # In-flight active orders
                if target_status in [ORDER_STATUS_PREPARING, ORDER_STATUS_PACKING, ORDER_STATUS_DISPATCHED]:
                    order_ent.actual_prep_time = round(p50 * random.uniform(0.7, 0.95), 1)
                if target_status in [ORDER_STATUS_PACKING, ORDER_STATUS_DISPATCHED]:
                    order_ent.food_ready_timestamp = order_time + timedelta(minutes=order_ent.actual_prep_time)

            s.add(order_ent)

            # Dispatch Prediction Record
            disp_ent = DispatchPrediction(
                order_id=order_id,
                prediction_created_at=order_time,
                predicted_dispatch_delay=dispatch_delay,
                predicted_rider_travel_time=travel,
                recommended_dispatch_timestamp=recommended_dispatch_time,
                predicted_arrival_timestamp=predicted_arrival_time,
            )
            s.add(disp_ent)

        s.commit()
        logger.info(f"Database successfully populated with {total_orders} rich operational orders.")

    # Refresh Power BI Data Mart
    logger.info("Synchronizing rich data to Power BI CSV data mart...")
    export_powerbi_datasets()
    logger.info("Enrichment and export completed successfully.")


if __name__ == "__main__":
    seed_rich_operational_data(500)
