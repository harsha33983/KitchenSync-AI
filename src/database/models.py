"""
SQLAlchemy ORM Models for KitchenSync AI Database
Maps all relational entities: Stores, Orders, Riders, Dispatch Predictions,
Kitchen Events, and Performance Metrics with strict constraints.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Store(Base):
    __tablename__ = "stores"

    store_id = Column(String, primary_key=True)
    store_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    average_prep_time = Column(Float, nullable=False, default=18.0)

    # Relationships
    orders = relationship("Order", back_populates="store", cascade="all, delete-orphan")
    kitchen_events = relationship("KitchenEvent", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store {self.store_id}: {self.store_name}>"


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    order_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    item_count = Column(Integer, nullable=False, default=1)
    order_status = Column(
        String,
        CheckConstraint(
            "order_status IN ('PLACED', 'PREPARING', 'PACKING', 'READY', 'DISPATCHED', 'PICKED_UP', 'DELIVERED', 'CANCELLED')"
        ),
        nullable=False,
        default="PLACED",
    )
    predicted_prep_time = Column(Float, nullable=True)
    predicted_prep_time_p90 = Column(Float, nullable=True)
    actual_prep_time = Column(Float, nullable=True)
    food_ready_timestamp = Column(DateTime, nullable=True)
    pickup_timestamp = Column(DateTime, nullable=True)
    delivery_timestamp = Column(DateTime, nullable=True)
    distance_km = Column(Float, nullable=False, default=5.0)
    traffic_level = Column(String, nullable=False, default="Medium")
    weather_condition = Column(String, nullable=False, default="Sunny")

    # Relationships
    store = relationship("Store", back_populates="orders")
    dispatch_prediction = relationship(
        "DispatchPrediction", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    performance_metric = relationship(
        "PerformanceMetric", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    kitchen_events = relationship("KitchenEvent", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_orders_store_status", "store_id", "order_status"),
        Index("idx_orders_timestamp", "order_timestamp"),
    )

    def __repr__(self):
        return f"<Order {self.order_id} ({self.order_status})>"


class Rider(Base):
    __tablename__ = "riders"

    rider_id = Column(String, primary_key=True)
    rider_status = Column(
        String,
        CheckConstraint("rider_status IN ('AVAILABLE', 'ASSIGNED', 'BUSY', 'OFFLINE')"),
        nullable=False,
        default="AVAILABLE",
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    vehicle_type = Column(String, nullable=False, default="Scooter")

    def __repr__(self):
        return f"<Rider {self.rider_id} [{self.rider_status}]>"


class DispatchPrediction(Base):
    __tablename__ = "dispatch_predictions"

    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    prediction_created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    predicted_dispatch_delay = Column(Float, nullable=False)
    predicted_rider_travel_time = Column(Float, nullable=False)
    recommended_dispatch_timestamp = Column(DateTime, nullable=False)
    predicted_arrival_timestamp = Column(DateTime, nullable=False)

    order = relationship("Order", back_populates="dispatch_prediction")

    __table_args__ = (Index("idx_dispatch_order", "order_id"),)

    def __repr__(self):
        return f"<DispatchPrediction for {self.order_id}: delay={self.predicted_dispatch_delay}m>"


class KitchenEvent(Base):
    __tablename__ = "kitchen_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)  # 'ORDER_RECEIVED', 'COOKING_STARTED', 'PACKED', etc.
    event_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    store = relationship("Store", back_populates="kitchen_events")
    order = relationship("Order", back_populates="kitchen_events")

    __table_args__ = (Index("idx_kitchen_events_store_time", "store_id", "event_timestamp"),)

    def __repr__(self):
        return f"<KitchenEvent {self.event_type} on {self.order_id}>"


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False, unique=True)
    food_wait_for_rider = Column(Float, nullable=False, default=0.0)
    rider_wait_for_food = Column(Float, nullable=False, default=0.0)
    on_time_delivery = Column(Boolean, nullable=False, default=True)
    cancellation_flag = Column(Boolean, nullable=False, default=False)

    order = relationship("Order", back_populates="performance_metric")

    def __repr__(self):
        return f"<PerformanceMetric for {self.order_id}: food_wait={self.food_wait_for_rider}m, rider_wait={self.rider_wait_for_food}m>"
