-- KitchenSync AI Database Schema (SQLite 3)
-- Enforces referential integrity, indexes, and constraints

PRAGMA foreign_keys = ON;

-- 1. Stores Table
CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    average_prep_time REAL NOT NULL DEFAULT 18.0
);

-- 2. Orders Table
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    order_timestamp DATETIME NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 1,
    order_status TEXT NOT NULL CHECK(order_status IN ('PLACED', 'PREPARING', 'PACKING', 'READY', 'DISPATCHED', 'PICKED_UP', 'DELIVERED', 'CANCELLED')),
    predicted_prep_time REAL,
    predicted_prep_time_p90 REAL,
    actual_prep_time REAL,
    food_ready_timestamp DATETIME,
    pickup_timestamp DATETIME,
    delivery_timestamp DATETIME,
    distance_km REAL NOT NULL,
    traffic_level TEXT NOT NULL,
    weather_condition TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id) ON DELETE CASCADE
);

-- 3. Riders Table
CREATE TABLE IF NOT EXISTS riders (
    rider_id TEXT PRIMARY KEY,
    rider_status TEXT NOT NULL CHECK(rider_status IN ('AVAILABLE', 'ASSIGNED', 'BUSY', 'OFFLINE')),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    vehicle_type TEXT NOT NULL
);

-- 4. Dispatch Predictions Table
CREATE TABLE IF NOT EXISTS dispatch_predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    prediction_created_at DATETIME NOT NULL,
    predicted_dispatch_delay REAL NOT NULL,
    predicted_rider_travel_time REAL NOT NULL,
    recommended_dispatch_timestamp DATETIME NOT NULL,
    predicted_arrival_timestamp DATETIME NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 5. Kitchen Events Table
CREATE TABLE IF NOT EXISTS kitchen_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_timestamp DATETIME NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 6. Performance Metrics Table
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    food_wait_for_rider REAL NOT NULL DEFAULT 0.0,
    rider_wait_for_food REAL NOT NULL DEFAULT 0.0,
    on_time_delivery BOOLEAN NOT NULL DEFAULT 1,
    cancellation_flag BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- Operational Indexes
CREATE INDEX IF NOT EXISTS idx_orders_store_status ON orders(store_id, order_status);
CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON orders(order_timestamp);
CREATE INDEX IF NOT EXISTS idx_kitchen_events_store_time ON kitchen_events(store_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_dispatch_order ON dispatch_predictions(order_id);
