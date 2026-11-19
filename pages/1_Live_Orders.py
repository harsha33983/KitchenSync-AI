"""
Dashboard 1: Live Order Management
Interactive operational board for monitoring kitchen queues, creating new delivery orders,
updating preparation statuses, and executing SQLite window functions.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

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
from src.database.models import Store, Order, Rider
from src.services.order_service import order_service
from src.services.rider_service import rider_service

st.set_page_config(page_title="Live Order Management – KitchenSync AI", page_icon="📋", layout="wide")

st.title("📋 Live Order Management & Kitchen Queues")
st.markdown("Track active restaurant workloads, create new orders with real-time ML estimates, and update order statuses.")

# Refresh Controls
col_top1, col_top2 = st.columns([4, 1])
with col_top2:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# 1. Fetch Store List & Active Queues via SQL Window Function
with get_db_session() as s:
    stores = s.query(Store).all()
    store_options = {s.store_id: f"{s.store_name} ({s.location})" for s in stores}
    active_queues = calculate_active_kitchen_orders(s)
    total_active = sum(active_queues.values()) if active_queues else 0
    available_riders = s.query(Rider).filter(Rider.rider_status == "AVAILABLE").count()

# Metric Bar
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total Active Orders", total_active, help="Orders currently in PLACED, PREPARING, or PACKING status")
with m2:
    st.metric("Active Kitchen Hubs", len([k for k, v in active_queues.items() if v > 0]), help="Stores with orders in queue")
with m3:
    st.metric("Available Couriers", available_riders, help="Couriers ready for dispatch in fleet")
with m4:
    max_queue_store = max(active_queues.items(), key=lambda x: x[1])[0] if active_queues else "None"
    max_queue_val = active_queues.get(max_queue_store, 0)
    st.metric("Peak Store Queue", f"{max_queue_val} orders", help=f"Heaviest store load at {max_queue_store}")

st.markdown("---")

tab_orders, tab_create, tab_queues = st.tabs(["🔥 Active Orders Board", "➕ Create New Order", "🏪 Kitchen Queue Window Analysis"])

# TAB 1: ACTIVE ORDERS BOARD
with tab_orders:
    st.subheader("In-Flight Kitchen & Dispatch Orders")
    active_orders = order_service.get_active_orders()

    if not active_orders:
        st.info("No active orders in flight right now. Create a new order in the 'Create New Order' tab or inject demo orders.")
    else:
        df_active = pd.DataFrame(active_orders)
        
        # Display summary table
        cols_display = [
            "order_id", "store_id", "order_status", "item_count", "distance_km",
            "traffic_level", "weather_condition", "predicted_prep_time_p50",
            "predicted_dispatch_delay", "predicted_rider_travel_time"
        ]
        st.dataframe(
            df_active[cols_display].rename(columns={
                "order_id": "Order ID",
                "store_id": "Store",
                "order_status": "Status",
                "item_count": "Items",
                "distance_km": "Dist (km)",
                "traffic_level": "Traffic",
                "weather_condition": "Weather",
                "predicted_prep_time_p50": "P50 Prep (m)",
                "predicted_dispatch_delay": "Dispatch Delay (m)",
                "predicted_rider_travel_time": "Rider Travel (m)",
            }),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Update Order Preparation Status")
        col_up1, col_up2, col_up3 = st.columns([2, 2, 1])
        with col_up1:
            selected_order = st.selectbox(
                "Select Order to Progress",
                options=[o["order_id"] for o in active_orders],
            )
        with col_up2:
            new_status = st.selectbox(
                "New Lifecycle Status",
                options=[
                    ORDER_STATUS_PREPARING,
                    ORDER_STATUS_PACKING,
                    ORDER_STATUS_READY,
                    ORDER_STATUS_DISPATCHED,
                    ORDER_STATUS_PICKED_UP,
                    ORDER_STATUS_DELIVERED,
                    ORDER_STATUS_CANCELLED,
                ],
            )
        with col_up3:
            st.markdown("<div style='padding-top: 1.8rem;'></div>", unsafe_allow_html=True)
            if st.button("Update Status", use_container_width=True):
                order_service.update_order_status(selected_order, new_status)
                st.success(f"Updated {selected_order} to {new_status}!")
                st.rerun()

# TAB 2: CREATE NEW ORDER
with tab_create:
    st.subheader("Place New Delivery Order")
    with st.form("new_order_form"):
        fc1, fc2 = st.columns(2)
        with fc1:
            selected_store_id = st.selectbox(
                "Restaurant / Dark Store",
                options=list(store_options.keys()),
                format_func=lambda x: store_options[x],
            )
            item_count = st.number_input("Number of Items in Order", min_value=1, max_value=20, value=3)
            distance_km = st.number_input("Delivery Distance (km)", min_value=0.5, max_value=25.0, value=5.2, step=0.5)

        with fc2:
            traffic_level = st.selectbox("Current Road Traffic Density", options=["Low", "Medium", "High", "Jam"], index=1)
            weather_condition = st.selectbox("Current Weather Condition", options=["Sunny", "Cloudy", "Rainy", "Foggy", "Windy", "Stormy"], index=0)
            auto_assign_rider = st.checkbox("Auto-assign nearest available rider upon dispatch", value=True)

        submitted = st.form_submit_button("🚀 Submit Order & Calculate ML Dispatch", use_container_width=True)

        if submitted:
            result = order_service.create_order(
                store_id=selected_store_id,
                item_count=int(item_count),
                distance_km=float(distance_km),
                traffic_level=traffic_level,
                weather_condition=weather_condition,
            )
            st.success(f"Order **{result['order_id']}** created and committed to SQLite!")
            
            # Show live prediction outputs
            st.info(
                f"""
                **AI Dispatch Recommendation:**
                - **Predicted Food Preparation (P50):** {result['predicted_prep_time_p50']} min (P90: {result['predicted_prep_time_p90']} min)
                - **Predicted Rider Travel Time:** {result['predicted_rider_travel_time']} min
                - **Recommended Dispatch Delay:** **{result['recommended_dispatch_delay']} minutes**
                - **Active Store Queue Depth (Window Function):** {result['active_queue_after_insert']} active orders
                
                *Explanation:* {result['explanation']}
                """
            )
            if auto_assign_rider:
                assigned_rider = rider_service.assign_available_rider()
                if assigned_rider:
                    st.caption(f"Courier {assigned_rider} reserved for this dispatch window.")

# TAB 3: KITCHEN QUEUE WINDOW ANALYSIS
with tab_queues:
    st.subheader("Real-Time Store Queue Depths (SQL Window Function Query)")
    st.markdown(
        """
        Active queue depths are calculated using SQLite partition window functions:
        ```sql
        WITH active_orders AS (
            SELECT order_id, store_id, order_status
            FROM orders
            WHERE order_status IN ('PLACED', 'PREPARING', 'PACKING')
        )
        SELECT order_id, store_id, COUNT(*) OVER (PARTITION BY store_id) AS active_orders_per_store
        FROM active_orders;
        ```
        """
    )
    if active_queues:
        queue_table = []
        for s_id, count in active_queues.items():
            name = store_options.get(s_id, s_id)
            queue_table.append({
                "Store ID": s_id,
                "Store Name": name,
                "Active Kitchen Orders (Backlog)": count,
                "Workload Status": "High Load 🔴" if count >= 4 else ("Moderate 🟡" if count >= 2 else "Optimal 🟢"),
            })
        st.dataframe(pd.DataFrame(queue_table).sort_values("Active Kitchen Orders (Backlog)", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.write("No active kitchen queues at this moment.")
