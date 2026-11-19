"""
Dashboard 4: Operational Analytics
Interactive Plotly visualizations and performance scorecards for network throughput,
kitchen prep accuracy, idling wait times, and delivery SLAs.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text

from src.database.connection import get_db_session, engine
from src.utils.metrics import compute_operational_kpis, get_store_performance_rankings
from config import CHARTS_DIR

st.set_page_config(page_title="Operational Analytics – KitchenSync AI", page_icon="📈", layout="wide")

st.title("📈 Operational Analytics & Performance Scorecard")
st.markdown("Comprehensive operational intelligence across kitchen preparation, rider dispatch efficiency, and SLA fulfillment.")

# KPI Ribbon
kpis = compute_operational_kpis()
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Avg Prep Time", f"{kpis['avg_prep_time_min']:.1f} m")
with c2:
    st.metric("Avg Food Wait", f"{kpis['avg_food_wait_min']:.1f} m")
with c3:
    st.metric("Avg Rider Wait", f"{kpis['avg_rider_wait_min']:.1f} m")
with c4:
    st.metric("On-Time Delivery", f"{kpis['on_time_delivery_pct']:.1f}%")
with c5:
    st.metric("Cancellation Rate", f"{kpis['cancellation_rate_pct']:.1f}%")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Kitchen Analytics", "🛵 Rider & Wait Time Dynamics", "🏪 Store Performance Scorecard"])

# TAB 1: KITCHEN ANALYTICS
with tab1:
    col_k1, col_k2 = st.columns(2)
    
    with col_k1:
        st.subheader("Hourly Order Demand & Kitchen Load")
        query_hourly = """
        SELECT strftime('%H', order_timestamp) AS order_hour, COUNT(order_id) AS order_count
        FROM orders
        GROUP BY order_hour
        ORDER BY order_hour ASC;
        """
        with get_db_session() as s:
            res = s.execute(text(query_hourly)).fetchall()
            df_hourly = pd.DataFrame(res, columns=["order_hour", "order_count"]) if res else pd.DataFrame({"order_hour": ["12", "13", "19", "20"], "order_count": [15, 22, 35, 28]})
        
        fig_hour = px.bar(
            df_hourly,
            x="order_hour",
            y="order_count",
            labels={"order_hour": "Hour of Day (24h)", "order_count": "Total Orders"},
            color="order_count",
            color_continuous_scale="Blues",
            title="Order Volume Distribution Across Hours of Day"
        )
        st.plotly_chart(fig_hour, use_container_width=True, key="chart_hourly_volume")

    with col_k2:
        st.subheader("Actual vs Predicted Kitchen Preparation (P50)")
        query_pred = """
        SELECT actual_prep_time, predicted_prep_time, predicted_prep_time_p90, item_count
        FROM orders
        WHERE actual_prep_time IS NOT NULL;
        """
        with get_db_session() as s:
            res = s.execute(text(query_pred)).fetchall()
            df_pred = pd.DataFrame(res, columns=["actual_prep_time", "predicted_prep_time", "predicted_prep_time_p90", "item_count"]) if res else pd.DataFrame()

        if not df_pred.empty:
            fig_scatter = px.scatter(
                df_pred,
                x="actual_prep_time",
                y="predicted_prep_time",
                size="item_count",
                color="actual_prep_time",
                color_continuous_scale="Viridis",
                labels={"actual_prep_time": "Actual Prep Time (min)", "predicted_prep_time": "P50 Predicted Prep Time (min)"},
                title="Actual vs Model Predicted Kitchen Duration"
            )
            # Add 1:1 diagonal line
            min_v = min(df_pred["actual_prep_time"].min(), df_pred["predicted_prep_time"].min())
            max_v = max(df_pred["actual_prep_time"].max(), df_pred["predicted_prep_time"].max())
            fig_scatter.add_shape(type="line", x0=min_v, y0=min_v, x1=max_v, y1=max_v, line=dict(color="red", dash="dash"))
            st.plotly_chart(fig_scatter, use_container_width=True, key="chart_scatter_prep")
        else:
            st.info("Insufficient historical delivered orders to plot actual vs predicted prep scatter.")

# TAB 2: RIDER & WAIT DYNAMICS
with tab2:
    col_w1, col_w2 = st.columns(2)

    with col_w1:
        st.subheader("Idling Wait Times (Food Wait vs Courier Wait)")
        query_waits = """
        SELECT pm.food_wait_for_rider, pm.rider_wait_for_food, o.traffic_level
        FROM performance_metrics pm
        JOIN orders o ON pm.order_id = o.order_id;
        """
        with get_db_session() as s:
            res = s.execute(text(query_waits)).fetchall()
            df_waits = pd.DataFrame(res, columns=["food_wait_for_rider", "rider_wait_for_food", "traffic_level"]) if res else pd.DataFrame()

        if not df_waits.empty:
            fig_box = go.Figure()
            fig_box.add_trace(go.Box(y=df_waits["food_wait_for_rider"], name="Food Wait for Rider (min)", marker_color="#3B82F6"))
            fig_box.add_trace(go.Box(y=df_waits["rider_wait_for_food"], name="Rider Wait for Food (min)", marker_color="#10B981"))
            fig_box.update_layout(title="Idle Waiting Time Distributions", yaxis_title="Minutes")
            st.plotly_chart(fig_box, use_container_width=True, key="chart_box_waits")
        else:
            st.info("No completed order metrics recorded yet.")

    with col_w2:
        st.subheader("Dispatch Delay by Traffic Conditions")
        query_traffic_delay = """
        SELECT o.traffic_level, AVG(dp.predicted_dispatch_delay) AS avg_delay, AVG(dp.predicted_rider_travel_time) AS avg_travel
        FROM orders o
        JOIN dispatch_predictions dp ON o.order_id = dp.order_id
        GROUP BY o.traffic_level;
        """
        with get_db_session() as s:
            res = s.execute(text(query_traffic_delay)).fetchall()
            df_td = pd.DataFrame(res, columns=["traffic_level", "avg_delay", "avg_travel"]) if res else pd.DataFrame()

        if not df_td.empty:
            fig_td = px.bar(
                df_td,
                x="traffic_level",
                y=["avg_delay", "avg_travel"],
                barmode="group",
                labels={"value": "Minutes", "variable": "Metric", "traffic_level": "Traffic Level"},
                title="Staged Dispatch Delay vs Transit Time by Traffic"
            )
            st.plotly_chart(fig_td, use_container_width=True, key="chart_bar_traffic_delay")
        else:
            st.info("No dispatch delay data available.")

# TAB 3: STORE PERFORMANCE SCORECARD
with tab3:
    st.subheader("Restaurant Hub Performance League Table")
    store_df = get_store_performance_rankings()
    if not store_df.empty:
        st.dataframe(
            store_df.rename(columns={
                "store_id": "Store Code",
                "store_name": "Restaurant Name",
                "location": "Hub Location",
                "order_volume": "Total Orders",
                "avg_prep_time": "Avg Prep (min)",
                "avg_food_wait": "Food Wait (min)",
                "avg_rider_wait": "Courier Wait (min)",
                "on_time_rate": "On-Time %",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No store data to display.")
