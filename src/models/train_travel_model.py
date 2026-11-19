"""
Training Pipeline for Rider Travel / Transit Time Estimation (Model C)
Compares HistGradientBoostingRegressor, GradientBoostingRegressor, and RandomForestRegressor.
Selects the champion model based on chronological validation performance (MAE, RMSE, R²).
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import (
    PROCESSED_DATASET_PATH,
    TRAVEL_MODEL_PATH,
    PREPROCESSING_PIPELINE_PATH,
    RANDOM_STATE,
)
from src.data.feature_engineering import ALL_FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def train_rider_travel_models() -> dict:
    """
    Trains and compares multiple candidate algorithms for rider travel time estimation.
    Selects champion based on test MAE and serializes to models/rider_travel_model.pkl.
    """
    logger.info("Loading processed dataset for rider travel time modeling...")
    df = pd.read_csv(PROCESSED_DATASET_PATH)

    # Chronological Split (80% train, 20% test)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    # Load feature preprocessing pipeline
    preprocessor = joblib.load(PREPROCESSING_PIPELINE_PATH)

    X_train = preprocessor.transform(train_df[ALL_FEATURE_COLUMNS])
    y_train = train_df["actual_rider_travel_time"].values

    X_test = preprocessor.transform(test_df[ALL_FEATURE_COLUMNS])
    y_test = test_df["actual_rider_travel_time"].values

    logger.info(f"Training candidates on {len(X_train):,} samples; validating on {len(X_test):,} samples...")

    candidates = {
        "HistGradientBoostingRegressor": HistGradientBoostingRegressor(
            max_iter=200,
            learning_rate=0.08,
            min_samples_leaf=20,
            random_state=RANDOM_STATE,
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=120,
            learning_rate=0.1,
            max_depth=5,
            random_state=RANDOM_STATE,
        ),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            n_jobs=-1,
            random_state=RANDOM_STATE,
        ),
    }

    results = {}
    best_name = None
    best_mae = float("inf")
    best_model = None

    for name, model in candidates.items():
        logger.info(f"Fitting candidate: {name}...")
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        r2 = float(r2_score(y_test, preds))

        results[name] = {
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2_score": round(r2, 3),
        }
        logger.info(f"  {name} -> MAE: {mae:.3f} min | RMSE: {rmse:.3f} min | R²: {r2:.3f}")

        if mae < best_mae:
            best_mae = mae
            best_name = name
            best_model = model

    logger.info(f"Champion Model selected: {best_name} with MAE = {best_mae:.3f} min")

    # Serialize champion model
    TRAVEL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, TRAVEL_MODEL_PATH)
    logger.info(f"Saved champion rider travel model to {TRAVEL_MODEL_PATH}")

    output_summary = {
        "champion_model": best_name,
        "champion_metrics": results[best_name],
        "all_candidates": results,
    }

    print("\n" + "=" * 60)
    print("RIDER TRAVEL TIME MODEL SELECTION REPORT")
    print("=" * 60)
    for model_name, m in results.items():
        tag = " [CHAMPION]" if model_name == best_name else ""
        print(f"{model_name}{tag}:")
        print(f"  - MAE:      {m['mae']:.3f} min")
        print(f"  - RMSE:     {m['rmse']:.3f} min")
        print(f"  - R² Score: {m['r2_score']:.3f}")
    print("=" * 60 + "\n")

    return output_summary


if __name__ == "__main__":
    train_rider_travel_models()
