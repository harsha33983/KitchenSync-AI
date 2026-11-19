-- KitchenSync AI SQL Queries Collection
-- Includes Required Window Functions and Operational Metrics

-- 1. MANDATORY ACTIVE KITCHEN ORDER CALCULATION USING SQLITE WINDOW FUNCTION
-- Calculates real-time active workload per store partition for active orders
-- :param store_id_filter (optional)
WITH active_orders AS (
    SELECT
        order_id,
        store_id,
        order_status
    FROM orders
    WHERE order_status IN (
        'PLACED',
        'PREPARING',
        'PACKING'
    )
)
SELECT
    order_id,
    store_id,
    COUNT(*) OVER (
        PARTITION BY store_id
    ) AS active_orders_per_store
FROM active_orders;

-- 2. Store Level Operational Summary
SELECT
    s.store_id,
    s.store_name,
    COUNT(o.order_id) AS total_orders,
    AVG(o.actual_prep_time) AS avg_prep_time,
    AVG(pm.food_wait_for_rider) AS avg_food_wait,
    AVG(pm.rider_wait_for_food) AS avg_rider_wait,
    100.0 * SUM(CASE WHEN pm.on_time_delivery = 1 THEN 1 ELSE 0 END) / COUNT(o.order_id) AS on_time_rate
FROM stores s
LEFT JOIN orders o ON s.store_id = o.store_id
LEFT JOIN performance_metrics pm ON o.order_id = pm.order_id
GROUP BY s.store_id, s.store_name;

-- 3. Live Dispatch Queue Query
SELECT
    o.order_id,
    o.store_id,
    o.order_status,
    o.order_timestamp,
    o.distance_km,
    dp.predicted_dispatch_delay,
    dp.predicted_rider_travel_time,
    dp.recommended_dispatch_timestamp,
    dp.predicted_arrival_timestamp
FROM orders o
JOIN dispatch_predictions dp ON o.order_id = dp.order_id
WHERE o.order_status IN ('PLACED', 'PREPARING', 'PACKING', 'READY')
ORDER BY dp.recommended_dispatch_timestamp ASC;
