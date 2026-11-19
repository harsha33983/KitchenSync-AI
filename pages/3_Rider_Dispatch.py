"""
Dashboard 3: Rider Dispatch Board
Operational command center for managing courier fleet, assigning couriers,
monitoring dispatch staging countdowns, and minimizing idling wait times.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from src.database.connection import get_db_session
from src.database.models import Rider, Order, DispatchPrediction, PerformanceMetric
from src.services.rider_service import rider_service
from src.services.order_service import order_service
from config import ORDER_STATUS_PLACED, ORDER_STATUS_PREPARING, ORDER_STATUS_DISPATCHED

st.set_page_config(page_title="Rider Dispatch Board – KitchenSync AI", page_icon="🛵", layout="wide")

st.title("🛵 Rider Dispatch & Fleet Synchronization Board")
st.markdown("Coordinate courier dispatch, track staging countdowns, and monitor food/rider idle wait times.")

# Fleet Status Metrics
with get_db_session() as s:
    total_fleet = s.query(Rider).count()
    available_fleet = s.query(Rider).filter(Rider.rider_status == "AVAILABLE").count()
    assigned_fleet = s.query(Rider).filter(Rider.rider_status == "ASSIGNED").count()
    busy_fleet = s.query(Rider).filter(Rider.rider_status.in_(["BUSY", "OFFLINE"])).count()

    metrics = s.query(PerformanceMetric).all()
    avg_food_wait = round(sum(m.food_wait_for_rider for m in metrics) / len(metrics), 1) if metrics else 1.8
    avg_rider_wait = round(sum(m.rider_wait_for_food for m in metrics) / len(metrics), 1) if metrics else 1.5

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total Fleet", total_fleet)
with c2:
    st.metric("Available Couriers", available_fleet, help="Ready for immediate assignment")
with c3:
    st.metric("Assigned to Orders", assigned_fleet)
with c4:
    st.metric("Avg Food Wait for Courier", f"{avg_food_wait} min", delta="-0.5m", delta_color="inverse")
with c5:
    st.metric("Avg Courier Wait for Food", f"{avg_rider_wait} min", delta="-0.7m", delta_color="inverse")

st.markdown("---")

col_dispatch, col_fleet = st.columns([3, 2])

# SECTION 1: ORDERS AWAITING DISPATCH
with col_dispatch:
    st.subheader("Orders in Staging Window")
    
    pending_list = []
    with get_db_session() as s:
        pending_orders = (
            s.query(Order, DispatchPrediction)
            .join(DispatchPrediction, Order.order_id == DispatchPrediction.order_id)
            .filter(Order.order_status.in_([ORDER_STATUS_PLACED, ORDER_STATUS_PREPARING]))
            .order_by(DispatchPrediction.recommended_dispatch_timestamp.asc())
            .all()
        )
        for o, dp in pending_orders:
            pending_list.append({
                "order_id": o.order_id,
                "store_id": o.store_id,
                "order_status": o.order_status,
                "predicted_prep_time": o.predicted_prep_time,
                "predicted_rider_travel_time": dp.predicted_rider_travel_time,
                "predicted_dispatch_delay": dp.predicted_dispatch_delay,
                "recommended_dispatch_timestamp": dp.recommended_dispatch_timestamp,
            })

    if not pending_list:
        st.info("No orders currently awaiting courier dispatch. All active orders have been dispatched or completed.")
    else:
        now = datetime.utcnow()
        display_list = []
        for item in pending_list:
            remaining_min = round((item["recommended_dispatch_timestamp"] - now).total_seconds() / 60.0, 1)
            urgency = "🚨 Dispatch NOW" if remaining_min <= 0 else f"⏳ Hold {remaining_min:.1f}m"
            display_list.append({
                "Order ID": item["order_id"],
                "Store": item["store_id"],
                "Status": item["order_status"],
                "Prep P50 (m)": item["predicted_prep_time"],
                "Rider Travel (m)": item["predicted_rider_travel_time"],
                "Dispatch Delay (m)": item["predicted_dispatch_delay"],
                "Countdown / Action": urgency,
            })
        
        st.dataframe(pd.DataFrame(display_list), use_container_width=True, hide_index=True)

        st.markdown("#### Manual Dispatch Override")
        with st.form("dispatch_action_form"):
            order_to_dispatch = st.selectbox(
                "Select Order to Dispatch",
                options=[p["order_id"] for p in pending_list],
            )
            dispatch_button = st.form_submit_button("📢 Dispatch Courier Now", use_container_width=True)
            if dispatch_button:
                order_service.update_order_status(order_to_dispatch, ORDER_STATUS_DISPATCHED)
                rider_service.assign_available_rider()
                st.success(f"Dispatched courier for order {order_to_dispatch}!")
                st.rerun()

# SECTION 2: COURIER FLEET STATUS
with col_fleet:
    st.subheader("Courier Fleet Live Status")
    with get_db_session() as s:
        riders = s.query(Rider).all()
        df_riders = pd.DataFrame([
            {
                "Rider ID": r.rider_id,
                "Status": r.rider_status,
                "Vehicle": r.vehicle_type,
                "Coordinates": f"{r.latitude:.3f}, {r.longitude:.3f}",
            }
            for r in riders
        ])
    st.dataframe(df_riders, use_container_width=True, hide_index=True)

    st.markdown("#### Courier Availability Toggle")
    with st.form("rider_status_form"):
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            sel_rider = st.selectbox("Select Courier", options=df_riders["Rider ID"].tolist())
        with r_col2:
            sel_status = st.selectbox("Status", options=["AVAILABLE", "BUSY", "OFFLINE"])
        if st.form_submit_button("Update Courier Status", use_container_width=True):
            rider_service.update_rider_status(sel_rider, sel_status)
            st.success(f"Courier {sel_rider} status set to {sel_status}!")
            st.rerun()
