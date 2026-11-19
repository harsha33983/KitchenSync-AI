"""
Exploratory Data Analysis and Visualizations Generator
Generates publication-quality charts in reports/charts/ and produces
the complete runnable exploratory_data_analysis.ipynb notebook.
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from config import PROCESSED_DATASET_PATH, CHARTS_DIR, BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({"font.size": 11, "figure.autolayout": True})


def generate_eda_charts():
    """Generates all 10 required EDA figures and saves them as PNG files."""
    df = pd.read_csv(PROCESSED_DATASET_PATH)
    logger.info(f"Loaded {len(df):,} records for EDA analysis.")

    # 1. Preparation Time Distribution
    plt.figure(figsize=(8, 5))
    sns.histplot(df["actual_prep_time"], kde=True, color="#2b5c8f", bins=30)
    plt.axvline(df["actual_prep_time"].median(), color="red", linestyle="--", label=f"Median: {df['actual_prep_time'].median():.1f} min")
    plt.axvline(df["actual_prep_time"].quantile(0.90), color="orange", linestyle="--", label=f"P90: {df['actual_prep_time'].quantile(0.90):.1f} min")
    plt.title("Distribution of Kitchen Food Preparation Time (Minutes)", fontsize=13, fontweight="bold")
    plt.xlabel("Preparation Time (min)")
    plt.ylabel("Order Frequency")
    plt.legend()
    plt.savefig(CHARTS_DIR / "prep_time_distribution.png", dpi=200)
    plt.close()

    # 2. Delivery Time Distribution
    plt.figure(figsize=(8, 5))
    sns.histplot(df["actual_rider_travel_time"], kde=True, color="#287d55", bins=30)
    plt.axvline(df["actual_rider_travel_time"].median(), color="red", linestyle="--", label=f"Median: {df['actual_rider_travel_time'].median():.1f} min")
    plt.title("Distribution of Rider Delivery Transit Time (Minutes)", fontsize=13, fontweight="bold")
    plt.xlabel("Delivery Travel Time (min)")
    plt.ylabel("Frequency")
    plt.legend()
    plt.savefig(CHARTS_DIR / "delivery_time_distribution.png", dpi=200)
    plt.close()

    # 3. Orders by Hour of Day
    plt.figure(figsize=(9, 4.5))
    hourly = df["hour_of_day"].value_counts().sort_index()
    sns.barplot(x=hourly.index, y=hourly.values, color="#48639c")
    plt.title("Order Volume by Hour of Day (Operational Peak Detection)", fontsize=13, fontweight="bold")
    plt.xlabel("Hour of Day (24-Hour Clock)")
    plt.ylabel("Total Orders Placed")
    plt.savefig(CHARTS_DIR / "orders_by_hour.png", dpi=200)
    plt.close()

    # 4. Orders by Day of Week
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    plt.figure(figsize=(7, 4.5))
    dow = df["day_of_week"].value_counts().sort_index()
    sns.barplot(x=[days[i] for i in dow.index], y=dow.values, palette="Blues_d")
    plt.title("Order Volume Across Days of Week", fontsize=13, fontweight="bold")
    plt.xlabel("Day of Week")
    plt.ylabel("Total Orders Placed")
    plt.savefig(CHARTS_DIR / "orders_by_day_of_week.png", dpi=200)
    plt.close()

    # 5. Item Count Distribution
    plt.figure(figsize=(8, 4.5))
    sns.countplot(data=df, x="item_count", palette="viridis")
    plt.title("Distribution of Items per Order", fontsize=13, fontweight="bold")
    plt.xlabel("Ordered Items Count")
    plt.ylabel("Frequency")
    plt.savefig(CHARTS_DIR / "item_count_distribution.png", dpi=200)
    plt.close()

    # 6. Restaurant Workload vs Prep Time
    plt.figure(figsize=(8, 5))
    sns.boxplot(x="kitchen_queue_depth", y="actual_prep_time", data=df, palette="Reds")
    plt.title("Impact of Kitchen Queue Depth on Preparation Time", fontsize=13, fontweight="bold")
    plt.xlabel("Active Kitchen Queue Depth (Orders in Backlog)")
    plt.ylabel("Kitchen Prep Time (min)")
    plt.savefig(CHARTS_DIR / "kitchen_workload_impact.png", dpi=200)
    plt.close()

    # 7. Traffic Impact on Rider Travel Time
    plt.figure(figsize=(8, 5))
    order = ["Low", "Medium", "High", "Jam"]
    sns.boxplot(x="traffic_level", y="actual_rider_travel_time", data=df, order=order, palette="Oranges")
    plt.title("Rider Delivery Travel Time by Traffic Intensity", fontsize=13, fontweight="bold")
    plt.xlabel("Road Traffic Level")
    plt.ylabel("Rider Travel Time (min)")
    plt.savefig(CHARTS_DIR / "traffic_impact.png", dpi=200)
    plt.close()

    # 8. Delivery Distance Distribution
    plt.figure(figsize=(8, 5))
    sns.histplot(df["distance_km"], kde=True, color="#6b4c9a", bins=25)
    plt.title("Delivery Distance Distribution (Great-Circle Haversine km)", fontsize=13, fontweight="bold")
    plt.xlabel("Distance (km)")
    plt.ylabel("Order Count")
    plt.savefig(CHARTS_DIR / "distance_distribution.png", dpi=200)
    plt.close()

    # 9. Correlation Heatmap
    num_cols = [
        "actual_prep_time",
        "actual_rider_travel_time",
        "item_count",
        "kitchen_queue_depth",
        "distance_km",
        "store_load",
        "order_complexity",
        "estimated_travel_time",
    ]
    plt.figure(figsize=(9, 7))
    corr = df[num_cols].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, square=True)
    plt.title("Operational Feature Correlation Heatmap", fontsize=13, fontweight="bold")
    plt.savefig(CHARTS_DIR / "correlation_heatmap.png", dpi=200)
    plt.close()

    # 10. Missing-Value Analysis (Cleaned Dataset)
    plt.figure(figsize=(8, 4))
    missing = df.isna().sum()
    sns.barplot(x=missing.index, y=missing.values, color="#348aa7")
    plt.xticks(rotation=45, ha="right")
    plt.title("Missing Value Audit across Cleaned Pipeline Features (Zero Nulls)", fontsize=13, fontweight="bold")
    plt.ylabel("Missing Count")
    plt.savefig(CHARTS_DIR / "missing_value_analysis.png", dpi=200)
    plt.close()

    logger.info("All 10 EDA figures generated and saved successfully.")


def generate_jupyter_notebook():
    """Generates the exploratory_data_analysis.ipynb file with cells and markdown."""
    notebook_path = BASE_DIR / "notebooks" / "exploratory_data_analysis.ipynb"
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# KitchenSync AI: Exploratory Data Analysis & Feature Investigation\n",
                "## Food Delivery & Q-Commerce Real-Time Kitchen Prep & Rider Dispatch Estimator\n",
                "\n",
                "This notebook performs exploratory data analysis on the real-world food delivery operations dataset.\n",
                "We examine preparation durations, delivery distances, traffic conditions, and kitchen workload."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "from pathlib import Path\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "import matplotlib.pyplot as plt\n",
                "import seaborn as sns\n",
                "\n",
                "# Set plot style\n",
                "sns.set_theme(style='whitegrid', palette='muted')\n",
                "plt.rcParams['figure.figsize'] = (10, 6)\n",
                "\n",
                "# Load processed dataset\n",
                "df = pd.read_csv('../data/processed/food_delivery_features.csv')\n",
                "print(f'Loaded dataset: {df.shape[0]:,} rows, {df.shape[1]} columns')\n",
                "df.head()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 1. Target Distributions: Food Preparation Time & Rider Transit Time"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "outputs": [],
            "source": [
                "fig, axes = plt.subplots(1, 2, figsize=(14, 5))\n",
                "sns.histplot(df['actual_prep_time'], kde=True, ax=axes[0], color='#2b5c8f')\n",
                "axes[0].set_title('Kitchen Preparation Time Distribution')\n",
                "axes[0].axvline(df['actual_prep_time'].median(), color='red', linestyle='--', label=f'P50 Median: {df[\"actual_prep_time\"].median():.1f}m')\n",
                "axes[0].axvline(df['actual_prep_time'].quantile(0.90), color='orange', linestyle='--', label=f'P90: {df[\"actual_prep_time\"].quantile(0.90):.1f}m')\n",
                "axes[0].legend()\n",
                "\n",
                "sns.histplot(df['actual_rider_travel_time'], kde=True, ax=axes[1], color='#287d55')\n",
                "axes[1].set_title('Rider Delivery Travel Time Distribution')\n",
                "axes[1].axvline(df['actual_rider_travel_time'].median(), color='red', linestyle='--', label=f'Median: {df[\"actual_rider_travel_time\"].median():.1f}m')\n",
                "axes[1].legend()\n",
                "plt.show()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 2. Operational Impact: Kitchen Queue Depth vs Preparation Time"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "outputs": [],
            "source": [
                "plt.figure(figsize=(10, 5))\n",
                "sns.boxplot(x='kitchen_queue_depth', y='actual_prep_time', data=df, palette='Reds')\n",
                "plt.title('Kitchen Queue Congestion vs Food Preparation Duration')\n",
                "plt.xlabel('Active Kitchen Orders in Queue')\n",
                "plt.ylabel('Preparation Duration (min)')\n",
                "plt.show()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 3. Traffic Conditions vs Rider Transit Travel Time"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 4,
            "metadata": {},
            "outputs": [],
            "source": [
                "plt.figure(figsize=(9, 5))\n",
                "sns.boxplot(x='traffic_level', y='actual_rider_travel_time', data=df, order=['Low', 'Medium', 'High', 'Jam'], palette='Oranges')\n",
                "plt.title('Impact of Road Traffic Density on Transit Duration')\n",
                "plt.xlabel('Traffic Density')\n",
                "plt.ylabel('Rider Travel Time (min)')\n",
                "plt.show()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 4. Correlation Heatmap across Engineered Features"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 5,
            "metadata": {},
            "outputs": [],
            "source": [
                "num_cols = ['actual_prep_time', 'actual_rider_travel_time', 'item_count', 'kitchen_queue_depth', 'distance_km', 'store_load', 'order_complexity']\n",
                "plt.figure(figsize=(9, 7))\n",
                "sns.heatmap(df[num_cols].corr(), annot=True, fmt='.2f', cmap='coolwarm', square=True)\n",
                "plt.title('Operational Feature Correlation Matrix')\n",
                "plt.show()"
            ]
        }
    ]

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.11.9"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    with open(notebook_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    logger.info(f"Notebook generated at {notebook_path}")


if __name__ == "__main__":
    generate_eda_charts()
    generate_jupyter_notebook()
