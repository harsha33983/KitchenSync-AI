"""
Configuration settings for KitchenSync AI - Smart Food Delivery & Q-Commerce Dispatch Estimator
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
SYNTHETIC_SIM_DIR = DATA_DIR / "synthetic_simulation"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
POWERBI_DIR = BASE_DIR / "powerbi"

# Database Configuration (Mandatory SQLite)
DATABASE_FILE = DATA_DIR / "food_delivery.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"

# Model Artifact Paths
PREP_MODEL_P50_PATH = MODELS_DIR / "prep_time_p50.pkl"
PREP_MODEL_P90_PATH = MODELS_DIR / "prep_time_p90.pkl"
TRAVEL_MODEL_PATH = MODELS_DIR / "rider_travel_model.pkl"
PREPROCESSING_PIPELINE_PATH = MODELS_DIR / "preprocessing_pipeline.pkl"
EVALUATION_REPORT_PATH = REPORTS_DIR / "model_evaluation.json"

# Processed Feature Dataset
PROCESSED_DATASET_PATH = PROCESSED_DATA_DIR / "food_delivery_features.csv"

# Dispatch Engine Parameters
DEFAULT_SAFETY_BUFFER_MIN = 3.0  # Buffer in minutes before dispatching
URGENT_BUFFER_MIN = 1.0
PACKING_TIME_MIN = 3.0           # Average time for food packing after cooking
MAX_DISPATCH_DELAY_MIN = 60.0    # Upper bound sanity check on delay
DEFAULT_RIDER_SPEED_KMH = 22.0   # Urban bike/scooter average speed in km/h

# Order Status Constants
ORDER_STATUS_PLACED = "PLACED"
ORDER_STATUS_PREPARING = "PREPARING"
ORDER_STATUS_PACKING = "PACKING"
ORDER_STATUS_READY = "READY"
ORDER_STATUS_DISPATCHED = "DISPATCHED"
ORDER_STATUS_PICKED_UP = "PICKED_UP"
ORDER_STATUS_DELIVERED = "DELIVERED"
ORDER_STATUS_CANCELLED = "CANCELLED"

ACTIVE_ORDER_STATUSES = [
    ORDER_STATUS_PLACED,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_PACKING,
]

# Random Seed for Reproducibility
RANDOM_STATE = 42
