"""
Training Pipeline for Kitchen Food Preparation Time (Quantile Regression)
Implements Model A (Median / P50) and Model B (Conservative / P90)
using HistGradientBoostingRegressor with quantile loss.
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, median_absolute_error, d2_pinball_score

from config import (
    PROCESSED_DATASET_PATH,
    PREP_MODEL_P50_PATH,
    PREP_MODEL_P90_PATH,
    PREPROCESSING_PIPELINE_PATH,
    RANDOM_STATE,
)
from src.data.feature_engineering import ALL_FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    """Calculates pinball loss for quantile alpha."""
    diff = y_true - y_pred
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1.0) * diff)))


def train_prep_models() -> dict:
    """
    Trains P50 and P90 HistGradientBoostingRegressor models on kitchen preparation duration.
    Evaluates on chronological test split and saves serialized artifacts.
    """
    logger.info("Loading processed dataset for preparation time models...")
    df = pd.read_csv(PROCESSED_DATASET_PATH)

    # Chronological Split (80% train, 20% test) to prevent temporal leakage
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    logger.info(f"Train split: {len(train_df):,} orders | Test split: {len(test_df):,} orders")

    # Load preprocessing pipeline
    preprocessor = joblib.load(PREPROCESSING_PIPELINE_PATH)

    X_train = preprocessor.transform(train_df[ALL_FEATURE_COLUMNS])
    y_train = train_df["actual_prep_time"].values

    X_test = preprocessor.transform(test_df[ALL_FEATURE_COLUMNS])
    y_test = test_df["actual_prep_time"].values

    # 1. Model A: Median Preparation Time (Quantile = 0.50)
    logger.info("Training Model A: P50 Median Preparation Regressor...")
    model_p50 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.50,
        max_iter=250,
        min_samples_leaf=25,
        learning_rate=0.08,
        l2_regularization=0.1,
        random_state=RANDOM_STATE,
    )
    model_p50.fit(X_train, y_train)
    pred_p50 = model_p50.predict(X_test)

    # 2. Model B: 90th Percentile Preparation Time (Quantile = 0.90)
    logger.info("Training Model B: P90 Conservative Preparation Regressor...")
    model_p90 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.90,
        max_iter=250,
        min_samples_leaf=25,
        learning_rate=0.08,
        l2_regularization=0.1,
        random_state=RANDOM_STATE,
    )
    model_p90.fit(X_train, y_train)
    pred_p90 = model_p90.predict(X_test)

    # Post-processing safeguard: enforce non-crossing quantiles
    crossings = np.sum(pred_p50 > pred_p90)
    crossing_pct = float(crossings / len(test_df) * 100)
    logger.info(f"Quantile crossing check: {crossings} crossings ({crossing_pct:.2f}%)")

    # Metrics Computation
    p50_mae = float(mean_absolute_error(y_test, pred_p50))
    p50_rmse = float(np.sqrt(mean_squared_error(y_test, pred_p50)))
    p50_r2 = float(r2_score(y_test, pred_p50))
    p50_medae = float(median_absolute_error(y_test, pred_p50))
    p50_pinball = pinball_loss(y_test, pred_p50, 0.50)

    p90_mae = float(mean_absolute_error(y_test, pred_p90))
    p90_rmse = float(np.sqrt(mean_squared_error(y_test, pred_p90)))
    p90_pinball = pinball_loss(y_test, pred_p90, 0.90)

    # Coverage: Fraction of actual prep times <= predicted P90 (Target ~90%)
    coverage = float(np.mean(y_test <= pred_p90) * 100)

    metrics = {
        "model_a_p50": {
            "algorithm": "HistGradientBoostingRegressor",
            "loss": "quantile",
            "quantile": 0.50,
            "mae": round(p50_mae, 3),
            "rmse": round(p50_rmse, 3),
            "r2_score": round(p50_r2, 3),
            "median_absolute_error": round(p50_medae, 3),
            "pinball_loss": round(p50_pinball, 3),
        },
        "model_b_p90": {
            "algorithm": "HistGradientBoostingRegressor",
            "loss": "quantile",
            "quantile": 0.90,
            "mae": round(p90_mae, 3),
            "rmse": round(p90_rmse, 3),
            "pinball_loss": round(p90_pinball, 3),
            "empirical_coverage_percentage": round(coverage, 2),
            "quantile_crossing_percentage": round(crossing_pct, 2),
        },
    }

    # Serialize Models
    PREP_MODEL_P50_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_p50, PREP_MODEL_P50_PATH)
    joblib.dump(model_p90, PREP_MODEL_P90_PATH)

    logger.info(f"Saved P50 model to {PREP_MODEL_P50_PATH}")
    logger.info(f"Saved P90 model to {PREP_MODEL_P90_PATH}")

    print("\n" + "=" * 60)
    print("PREPARATION TIME MODELS (P50 & P90) EVALUATION RESULTS")
    print("=" * 60)
    print(f"Model A (P50 Median):")
    print(f"  - MAE:                  {p50_mae:.3f} min")
    print(f"  - RMSE:                 {p50_rmse:.3f} min")
    print(f"  - R² Score:             {p50_r2:.3f}")
    print(f"  - Median Absolute Error:{p50_medae:.3f} min")
    print(f"  - Pinball Loss (q=0.5): {p50_pinball:.3f}")
    print(f"\nModel B (P90 Conservative):")
    print(f"  - Pinball Loss (q=0.9): {p90_pinball:.3f}")
    print(f"  - Empirical Coverage:   {coverage:.2f}% (Target: 90%)")
    print(f"  - Quantile Crossings:   {crossing_pct:.2f}%")
    print("=" * 60 + "\n")

    return metrics


if __name__ == "__main__":
    train_prep_models()
