"""
Order Management Service
Implements order lifecycle management, transactional SQLite persistence,
kitchen event logging, and active queue recalculation via SQL window functions.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from config import (
    ORDER_STATUS_PLACED,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_PACKING,
    ORDER_STATUS_READY,
    ORDER_STATUS_DISPATCHED,
    ORDER_STATUS_PICKED_UP,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_CANCELLED,
    ACTIVE_ORDER_STATUSES,
)
from src.database.connection import get_db_session, calculate_active_kitchen_orders
from src.database.models import Order, Store, DispatchPrediction, KitchenEvent, PerformanceMetric
from src.services.prediction_service import prediction_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OrderService:
    """Manages order creation, transitions, and performance tracking."""

    @staticmethod
    def create_order(
        store_id: str,
        item_count: int,
        distance_km: float,
        traffic_level: str = "Medium",
        weather_condition: str = "Sunny",
        order_id: Optional[str] = None,
        order_timestamp: Optional[datetime] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new order, executes window function for active queue,
        generates ML predictions, logs kitchen event, and commits to SQLite.
        """
        def _create(s: Session):
            nonlocal order_id, order_timestamp
            if order_id is None:
                order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"
            if order_timestamp is None:
                order_timestamp = datetime.utcnow()

            # 1. Fetch store info
            store = s.query(Store).filter(Store.store_id == store_id).first()
            avg_prep = store.average_prep_time if store else 18.0

            # 2. Window Function: Calculate pre-insertion active queue depth
            pre_queue_depth = calculate_active_kitchen_orders(s, store_id)

            # 3. Predict ML preparation & travel times
            pred_result = prediction_service.predict_for_order(
                store_id=store_id,
                item_count=item_count,
                distance_km=distance_km,
                traffic_level=traffic_level,
                weather_condition=weather_condition,
                kitchen_queue_depth=max(1, pre_queue_depth),
                average_prep_time=avg_prep,
                current_time=order_timestamp,
            )

            ml_preds = pred_result["ml_predictions"]
            plan_p50 = pred_result["dispatch_plan"]["p50_plan"]
            plan_p90 = pred_result["dispatch_plan"]["p90_plan"]

            # 4. Create Order ORM Entity
            order = Order(
                order_id=order_id,
                store_id=store_id,
                order_timestamp=order_timestamp,
                item_count=item_count,
                order_status=ORDER_STATUS_PLACED,
                predicted_prep_time=ml_preds["predicted_prep_time_p50"],
                predicted_prep_time_p90=ml_preds["predicted_prep_time_p90"],
                distance_km=distance_km,
                traffic_level=traffic_level,
                weather_condition=weather_condition,
            )
            s.add(order)

            # 5. Create Dispatch Prediction ORM Entity
            prediction = DispatchPrediction(
                order_id=order_id,
                prediction_created_at=order_timestamp,
                predicted_dispatch_delay=plan_p50["dispatch_delay_min"],
                predicted_rider_travel_time=ml_preds["predicted_rider_travel_time"],
                recommended_dispatch_timestamp=plan_p50["recommended_dispatch_timestamp"],
                predicted_arrival_timestamp=plan_p50["predicted_arrival_timestamp"],
            )
            s.add(prediction)

            # 6. Log Initial Kitchen Event
            event = KitchenEvent(
                store_id=store_id,
                order_id=order_id,
                event_type="ORDER_RECEIVED",
                event_timestamp=order_timestamp,
            )
            s.add(event)

            # Flush to database so window function includes this new order
            s.flush()

            # 7. Execute SQL Window function to verify new active queue count
            post_queue_depth = calculate_active_kitchen_orders(s, store_id)

            return {
                "order_id": order_id,
                "store_id": store_id,
                "order_status": ORDER_STATUS_PLACED,
                "order_timestamp": order_timestamp,
                "item_count": item_count,
                "distance_km": distance_km,
                "traffic_level": traffic_level,
                "weather_condition": weather_condition,
                "predicted_prep_time_p50": ml_preds["predicted_prep_time_p50"],
                "predicted_prep_time_p90": ml_preds["predicted_prep_time_p90"],
                "predicted_rider_travel_time": ml_preds["predicted_rider_travel_time"],
                "recommended_dispatch_delay": plan_p50["dispatch_delay_min"],
                "recommended_dispatch_timestamp": plan_p50["recommended_dispatch_timestamp"],
                "predicted_arrival_timestamp": plan_p50["predicted_arrival_timestamp"],
                "explanation": plan_p50["explanation"],
                "active_queue_after_insert": post_queue_depth,
            }

        if session:
            return _create(session)
        with get_db_session() as s:
            res = _create(s)
        try:
            from src.utils.export_powerbi import export_powerbi_datasets
            export_powerbi_datasets()
        except Exception:
            pass
        return res

    @staticmethod
    def update_order_status(
        order_id: str,
        new_status: str,
        timestamp: Optional[datetime] = None,
        session: Optional[Session] = None,
    ) -> bool:
        """Updates order status, records events, and computes wait performance metrics upon delivery."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        def _update(s: Session):
            order = s.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                logger.warning(f"Order {order_id} not found for status update.")
                return False

            old_status = order.order_status
            order.order_status = new_status

            # Event logging
            s.add(
                KitchenEvent(
                    store_id=order.store_id,
                    order_id=order.order_id,
                    event_type=f"STATUS_{new_status}",
                    event_timestamp=timestamp,
                )
            )

            # Operational timestamp triggers
            if new_status == ORDER_STATUS_READY and not order.food_ready_timestamp:
                order.food_ready_timestamp = timestamp
                if not order.actual_prep_time:
                    order.actual_prep_time = max(
                        5.0, round((timestamp - order.order_timestamp).total_seconds() / 60.0, 1)
                    )

            elif new_status == ORDER_STATUS_PICKED_UP and not order.pickup_timestamp:
                order.pickup_timestamp = timestamp
                if not order.food_ready_timestamp:
                    order.food_ready_timestamp = timestamp - timedelta(minutes=2)
                    order.actual_prep_time = max(
                        5.0, round((order.food_ready_timestamp - order.order_timestamp).total_seconds() / 60.0, 1)
                    )

            elif new_status == ORDER_STATUS_DELIVERED and not order.delivery_timestamp:
                order.delivery_timestamp = timestamp
                if not order.pickup_timestamp:
                    order.pickup_timestamp = timestamp - timedelta(minutes=15)
                if not order.food_ready_timestamp:
                    order.food_ready_timestamp = order.pickup_timestamp - timedelta(minutes=2)
                    order.actual_prep_time = max(
                        5.0, round((order.food_ready_timestamp - order.order_timestamp).total_seconds() / 60.0, 1)
                    )

                # Performance metrics computation
                food_wait = max(
                    0.0,
                    round((order.pickup_timestamp - order.food_ready_timestamp).total_seconds() / 60.0, 1),
                )
                pred = s.query(DispatchPrediction).filter(DispatchPrediction.order_id == order_id).first()
                if pred and pred.predicted_arrival_timestamp:
                    delta = (order.food_ready_timestamp - pred.predicted_arrival_timestamp).total_seconds() / 60.0
                    rider_wait = max(0.0, round(delta, 1))
                else:
                    rider_wait = 1.0

                total_time_min = (order.delivery_timestamp - order.order_timestamp).total_seconds() / 60.0
                expected_total = (order.predicted_prep_time or 20.0) + (pred.predicted_rider_travel_time if pred else 20.0) + 5.0
                on_time = total_time_min <= expected_total

                metric = s.query(PerformanceMetric).filter(PerformanceMetric.order_id == order_id).first()
                if not metric:
                    metric = PerformanceMetric(
                        order_id=order_id,
                        food_wait_for_rider=food_wait,
                        rider_wait_for_food=rider_wait,
                        on_time_delivery=on_time,
                        cancellation_flag=False,
                    )
                    s.add(metric)
                else:
                    metric.food_wait_for_rider = food_wait
                    metric.rider_wait_for_food = rider_wait
                    metric.on_time_delivery = on_time

            elif new_status == ORDER_STATUS_CANCELLED:
                metric = s.query(PerformanceMetric).filter(PerformanceMetric.order_id == order_id).first()
                if not metric:
                    metric = PerformanceMetric(
                        order_id=order_id,
                        food_wait_for_rider=0.0,
                        rider_wait_for_food=0.0,
                        on_time_delivery=False,
                        cancellation_flag=True,
                    )
                    s.add(metric)
                else:
                    metric.cancellation_flag = True

            s.flush()
            logger.info(f"Order {order_id} transition: {old_status} -> {new_status}")
            return True

        if session:
            return _update(session)
        with get_db_session() as s:
            res = _update(s)
        try:
            from src.utils.export_powerbi import export_powerbi_datasets
            export_powerbi_datasets()
        except Exception:
            pass
        return res

    @staticmethod
    def get_active_orders(session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all orders in active statuses (PLACED, PREPARING, PACKING, READY, DISPATCHED)."""
        def _get(s: Session):
            orders = (
                s.query(Order, DispatchPrediction)
                .outerjoin(DispatchPrediction, Order.order_id == DispatchPrediction.order_id)
                .filter(Order.order_status.in_(ACTIVE_ORDER_STATUSES + [ORDER_STATUS_READY, ORDER_STATUS_DISPATCHED]))
                .order_by(Order.order_timestamp.desc())
                .all()
            )
            out = []
            for o, dp in orders:
                out.append({
                    "order_id": o.order_id,
                    "store_id": o.store_id,
                    "order_status": o.order_status,
                    "order_timestamp": o.order_timestamp,
                    "item_count": o.item_count,
                    "distance_km": o.distance_km,
                    "traffic_level": o.traffic_level,
                    "weather_condition": o.weather_condition,
                    "predicted_prep_time_p50": o.predicted_prep_time,
                    "predicted_prep_time_p90": o.predicted_prep_time_p90,
                    "predicted_dispatch_delay": dp.predicted_dispatch_delay if dp else 0.0,
                    "predicted_rider_travel_time": dp.predicted_rider_travel_time if dp else 0.0,
                    "recommended_dispatch_timestamp": dp.recommended_dispatch_timestamp if dp else None,
                    "predicted_arrival_timestamp": dp.predicted_arrival_timestamp if dp else None,
                })
            return out

        if session:
            return _get(session)
        with get_db_session() as s:
            return _get(s)

    @staticmethod
    def seed_demo_orders(count: int = 15):
        """Seeds realistic historical and active orders to populate dashboards."""
        import random
        with get_db_session() as s:
            if s.query(Order).count() > 5:
                return  # already seeded

            logger.info(f"Seeding {count} demo operational orders...")
            stores = s.query(Store).all()
            if not stores:
                return

            now = datetime.utcnow()
            traffics = ["Low", "Medium", "High", "Jam"]
            weathers = ["Sunny", "Cloudy", "Rainy", "Foggy"]

            # Historical delivered orders
            for i in range(1, count + 1):
                store = random.choice(stores)
                t_offset = random.randint(30, 300)
                order_time = now - timedelta(minutes=t_offset)
                items = random.randint(1, 6)
                dist = round(random.uniform(2.0, 12.0), 1)

                order_res = OrderService.create_order(
                    store_id=store.store_id,
                    item_count=items,
                    distance_km=dist,
                    traffic_level=random.choice(traffics),
                    weather_condition=random.choice(weathers),
                    order_timestamp=order_time,
                    session=s,
                )
                oid = order_res["order_id"]

                # Mark older orders as DELIVERED or CANCELLED
                if i <= count - 5:
                    prep_duration = order_res["predicted_prep_time_p50"] + random.uniform(-2, 3)
                    travel_duration = order_res["predicted_rider_travel_time"] + random.uniform(-3, 4)

                    ready_t = order_time + timedelta(minutes=max(8.0, prep_duration))
                    pick_t = ready_t + timedelta(minutes=random.uniform(1.0, 4.0))
                    deliv_t = pick_t + timedelta(minutes=max(10.0, travel_duration))

                    o = s.query(Order).filter(Order.order_id == oid).first()
                    o.food_ready_timestamp = ready_t
                    o.pickup_timestamp = pick_t
                    o.delivery_timestamp = deliv_t
                    o.actual_prep_time = max(8.0, round(prep_duration, 1))
                    o.order_status = ORDER_STATUS_DELIVERED

                    food_wait = max(0.0, round((pick_t - ready_t).total_seconds() / 60.0, 1))
                    rider_wait = max(0.0, round(random.uniform(0.5, 3.5), 1))
                    s.add(
                        PerformanceMetric(
                            order_id=oid,
                            food_wait_for_rider=food_wait,
                            rider_wait_for_food=rider_wait,
                            on_time_delivery=random.random() > 0.12,
                            cancellation_flag=False,
                        )
                    )
                else:
                    # Keep recent orders active
                    statuses = [ORDER_STATUS_PLACED, ORDER_STATUS_PREPARING, ORDER_STATUS_PACKING]
                    o = s.query(Order).filter(Order.order_id == oid).first()
                    o.order_status = statuses[i % len(statuses)]

            s.commit()
            logger.info("Demo orders successfully seeded.")


order_service = OrderService()
