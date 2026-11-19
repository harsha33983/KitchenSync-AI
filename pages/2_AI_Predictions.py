"""
Dashboard 2: AI Prediction Engine
Displays live quantile predictions (P50/P90), rider transit durations,
staged dispatch delays, and interactive What-If simulation playground.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

from src.models.predict import DeliveryPredictionEngine
from src.dispatch.dispatch_optimizer import default_optimizer
from src.services.order_service import order_service
from src.database.connection import get_db_session
from src.database.models import Store, Order, DispatchPrediction

st.set_page_config(page_title="AI Prediction Engine – KitchenSync AI", page_icon="🧠", layout="wide")

st.title("🧠 AI Prediction Engine (Quantile Prep Time & Rider Dispatch)")
st.markdown("Detailed breakdown of HistGradientBoostingRegressor quantile outputs, travel time regressions, and dispatch delay mathematics.")

tab_live, tab_simulator = st.tabs(["📊 Live Order Predictions", "🎛️ Interactive 'What-If' Dispatch Simulator"])

# TAB 1: LIVE ORDER PREDICTIONS
with tab_live:
    st.subheader("Recent Order Inferences & Quantile Intervals")
    
    recent_data = []
    with get_db_session() as s:
        recent = (
            s.query(Order, DispatchPrediction)
            .join(DispatchPrediction, Order.order_id == DispatchPrediction.order_id)
            .order_by(Order.order_timestamp.desc())
            .limit(10)
            .all()
        )
        for o, dp in recent:
            recent_data.append({
                "order_id": o.order_id,
                "store_id": o.store_id,
                "order_status": o.order_status,
                "order_timestamp": o.order_timestamp,
                "predicted_prep_time": o.predicted_prep_time,
                "predicted_prep_time_p90": o.predicted_prep_time_p90,
                "predicted_rider_travel_time": dp.predicted_rider_travel_time,
                "predicted_dispatch_delay": dp.predicted_dispatch_delay,
                "recommended_dispatch_timestamp": dp.recommended_dispatch_timestamp,
                "predicted_arrival_timestamp": dp.predicted_arrival_timestamp,
            })

    if not recent_data:
        st.info("No recent predictions recorded. Place an order in Live Orders tab to trigger real ML inferences.")
    else:
        for idx, item in enumerate(recent_data):
            with st.expander(f"📦 Order {item['order_id']} ({item['store_id']}) — Status: {item['order_status']}", expanded=(idx == 0)):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("P50 Prep Time (Median)", f"{item['predicted_prep_time']:.1f} min")
                with c2:
                    st.metric("P90 Prep Time (Conservative)", f"{item['predicted_prep_time_p90']:.1f} min", delta=f"+{item['predicted_prep_time_p90'] - item['predicted_prep_time']:.1f} min buffer")
                with c3:
                    st.metric("Rider Travel Time", f"{item['predicted_rider_travel_time']:.1f} min")
                with c4:
                    st.metric("Optimal Dispatch Delay", f"{item['predicted_dispatch_delay']:.1f} min", delta="Staged" if item['predicted_dispatch_delay'] > 0 else "Immediate")

                # Timeline calculation
                ready_ts = item['order_timestamp'] + timedelta(minutes=item['predicted_prep_time'])
                dispatch_ts = item['recommended_dispatch_timestamp']
                arrival_ts = item['predicted_arrival_timestamp']

                st.markdown(
                    f"""
                    **Timestamps & Synchronization Timeline:**
                    - **Order Placed:** `{item['order_timestamp'].strftime('%H:%M:%S')}`
                    - **Recommended Rider Dispatch:** `{dispatch_ts.strftime('%H:%M:%S')}` (Hold for {item['predicted_dispatch_delay']:.1f} min)
                    - **Expected Rider Arrival at Store:** `{arrival_ts.strftime('%H:%M:%S')}`
                    - **Expected Food Ready on Counter:** `{ready_ts.strftime('%H:%M:%S')}`
                    """
                )
                
                # Visual sync chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=["Timeline"],
                    x=[item['predicted_prep_time']],
                    name="Kitchen Food Prep (P50)",
                    orientation='h',
                    marker=dict(color="#2563EB")
                ))
                fig.add_trace(go.Bar(
                    y=["Timeline"],
                    x=[item['predicted_dispatch_delay']],
                    name="Dispatch Staging Delay",
                    orientation='h',
                    marker=dict(color="#F59E0B")
                ))
                fig.add_trace(go.Bar(
                    y=["Timeline"],
                    x=[item['predicted_rider_travel_time']],
                    name="Rider Transit Duration",
                    orientation='h',
                    marker=dict(color="#10B981")
                ))
                fig.update_layout(
                    barmode="stack",
                    height=180,
                    margin=dict(l=20, r=20, t=30, b=20),
                    title="Time Synchronization Profile",
                    xaxis_title="Minutes from Order Placement"
                )
                st.plotly_chart(fig, use_container_width=True)

# TAB 2: WHAT-IF SIMULATOR
with tab_simulator:
    st.subheader("Operational 'What-If' Parameter Sensitivity Playground")
    st.markdown("Adjust parameters dynamically to observe how the ML models and dispatch engine adapt to kitchen congestion and traffic spikes.")

    col_sim_left, col_sim_right = st.columns([1, 1])

    with col_sim_left:
        sim_items = st.slider("Item Count in Order", 1, 15, 4)
        sim_queue = st.slider("Active Kitchen Queue Depth (Orders in Backlog)", 0, 10, 3)
        sim_dist = st.slider("Delivery Distance (km)", 1.0, 20.0, 6.5, step=0.5)
        sim_traffic = st.selectbox("Road Traffic Density", ["Low", "Medium", "High", "Jam"], index=1)
        sim_weather = st.selectbox("Weather Condition", ["Sunny", "Cloudy", "Rainy", "Foggy", "Windy", "Stormy"], index=0)
        sim_hour = st.slider("Time of Day (Hour)", 0, 23, 20)

    # Run inference directly on singleton engine
    engine = DeliveryPredictionEngine.get_instance()
    sim_features = {
        "item_count": sim_items,
        "hour_of_day": sim_hour,
        "day_of_week": 4,
        "is_weekend": 0,
        "kitchen_queue_depth": sim_queue,
        "average_prep_time": 18.0,
        "store_load": (sim_queue * 1.2) + (1.5 if sim_hour in [12, 13, 14, 19, 20, 21, 22] else 0.0),
        "distance_km": sim_dist,
        "rider_availability": 7,
        "estimated_travel_time": (sim_dist / 20.0) * 60.0,
        "peak_hour": 1 if sim_hour in [12, 13, 14, 19, 20, 21, 22] else 0,
        "order_complexity": 2.0 + 0.15 * sim_items,
        "traffic_level": sim_traffic,
        "weather_condition": sim_weather,
        "vehicle_type": "Scooter",
    }
    
    sim_preds = engine.predict(sim_features)
    sim_opt = default_optimizer.optimize_dispatch(
        predicted_prep_time_p50=sim_preds["predicted_prep_time_p50"],
        predicted_prep_time_p90=sim_preds["predicted_prep_time_p90"],
        predicted_rider_travel_time=sim_preds["predicted_rider_travel_time"],
        current_time=datetime.utcnow(),
    )

    with col_sim_right:
        st.markdown("#### Real-Time Engine Inferences")
        
        sc1, sc2 = st.columns(2)
        with sc1:
            st.metric("P50 Prep Time", f"{sim_preds['predicted_prep_time_p50']} min")
            st.metric("P90 Prep Time", f"{sim_preds['predicted_prep_time_p90']} min")
        with sc2:
            st.metric("Rider Travel Time", f"{sim_preds['predicted_rider_travel_time']} min")
            st.metric("Optimal Dispatch Delay", f"{sim_opt['p50_plan']['dispatch_delay_min']} min")

        st.markdown("---")
        st.markdown(f"**Dispatch Explanation:**\n> {sim_opt['p50_plan']['explanation']}")
        
        p50_delay = sim_opt['p50_plan']['dispatch_delay_min']
        p90_delay = sim_opt['p90_plan']['dispatch_delay_min']

        st.info(
            f"""
            - **Standard P50 Delay:** Hold for **{p50_delay} min** (balances rider waiting vs food cooling).
            - **Conservative P90 Delay:** Hold for **{p90_delay} min** (ensures 90% confidence food is ready before courier arrives).
            """
        )
