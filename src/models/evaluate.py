"""
Model Evaluation and Diagnostic Reporting Module
Computes test metrics, quantile coverage, pinball loss, and generates
all evaluation diagnostic figures in reports/charts/ and reports/model_evaluation.json.
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, median_absolute_error
from sklearn.inspection import permutation_importance

from config import (
    PROCESSED_DATASET_PATH,
    PREP_MODEL_P50_PATH,
    PREP_MODEL_P90_PATH,
    TRAVEL_MODEL_PATH,
    PREPROCESSING_PIPELINE_PATH,
    EVALUATION_REPORT_PATH,
    CHARTS_DIR,
    RANDOM_STATE,
)
from src.data.feature_engineering import ALL_FEATURE_COLUMNS, NUMERICAL_FEATURES, CATEGORICAL_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", palette="muted")


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    diff = y_true - y_pred
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1.0) * diff)))


def run_full_evaluation():
    """Executes full evaluation on chronological test data and generates diagnostic charts."""
    logger.info("Loading test dataset and serialized models...")
    df = pd.read_csv(PROCESSED_DATASET_PATH)

    # Chronological Split (80% train, 20% test)
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:].copy()

    preprocessor = joblib.load(PREPROCESSING_PIPELINE_PATH)
    model_p50 = joblib.load(PREP_MODEL_P50_PATH)
    model_p90 = joblib.load(PREP_MODEL_P90_PATH)
    travel_model = joblib.load(TRAVEL_MODEL_PATH)

    X_test = preprocessor.transform(test_df[ALL_FEATURE_COLUMNS])
    y_test_prep = test_df["actual_prep_time"].values
    y_test_travel = test_df["actual_rider_travel_time"].values

    # Model Predictions
    pred_p50 = model_p50.predict(X_test)
    pred_p90 = model_p90.predict(X_test)
    pred_travel = travel_model.predict(X_test)

    # 1. Metrics Computation
    # Prep Time P50
    p50_mae = float(mean_absolute_error(y_test_prep, pred_p50))
    p50_rmse = float(np.sqrt(mean_squared_error(y_test_prep, pred_p50)))
    p50_r2 = float(r2_score(y_test_prep, pred_p50))
    p50_medae = float(median_absolute_error(y_test_prep, pred_p50))
    p50_pinball = pinball_loss(y_test_prep, pred_p50, 0.50)

    # Prep Time P90
    p90_mae = float(mean_absolute_error(y_test_prep, pred_p90))
    p90_rmse = float(np.sqrt(mean_squared_error(y_test_prep, pred_p90)))
    p90_pinball = pinball_loss(y_test_prep, pred_p90, 0.90)
    coverage = float(np.mean(y_test_prep <= pred_p90) * 100)
    crossings = int(np.sum(pred_p50 > pred_p90))
    crossing_pct = float(crossings / len(test_df) * 100)

    # Rider Travel Model
    travel_mae = float(mean_absolute_error(y_test_travel, pred_travel))
    travel_rmse = float(np.sqrt(mean_squared_error(y_test_travel, pred_travel)))
    travel_r2 = float(r2_score(y_test_travel, pred_travel))
    travel_medae = float(median_absolute_error(y_test_travel, pred_travel))

    report = {
        "dataset_name": "Indian Food Delivery Operations Dataset (Zomato / Swiggy Logistics)",
        "total_records": len(df),
        "test_records": len(test_df),
        "models": {
            "prep_time_p50": {
                "model_name": "HistGradientBoostingRegressor (P50)",
                "loss_function": "quantile (0.50)",
                "mae_minutes": round(p50_mae, 3),
                "rmse_minutes": round(p50_rmse, 3),
                "r2_score": round(p50_r2, 3),
                "median_absolute_error": round(p50_medae, 3),
                "pinball_loss": round(p50_pinball, 3),
            },
            "prep_time_p90": {
                "model_name": "HistGradientBoostingRegressor (P90)",
                "loss_function": "quantile (0.90)",
                "mae_minutes": round(p90_mae, 3),
                "rmse_minutes": round(p90_rmse, 3),
                "pinball_loss": round(p90_pinball, 3),
                "empirical_coverage_percentage": round(coverage, 2),
                "quantile_crossing_percentage": round(crossing_pct, 2),
                "target_coverage_percentage": 90.0,
            },
            "rider_travel_model": {
                "model_name": "HistGradientBoostingRegressor",
                "loss_function": "squared_error",
                "mae_minutes": round(travel_mae, 3),
                "rmse_minutes": round(travel_rmse, 3),
                "r2_score": round(travel_r2, 3),
                "median_absolute_error": round(travel_medae, 3),
            },
        },
    }

    # Save JSON Report
    EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVALUATION_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Evaluation report saved to {EVALUATION_REPORT_PATH}")

    # 2. Generate Evaluation Charts
    logger.info("Generating evaluation diagnostic figures...")

    # Chart 1: Actual vs Predicted Preparation Time
    plt.figure(figsize=(7, 6))
    plt.scatter(y_test_prep[:600], pred_p50[:600], alpha=0.4, color="#2b5c8f", s=25, label="Test Orders")
    min_v, max_v = min(y_test_prep[:600].min(), pred_p50[:600].min()), max(y_test_prep[:600].max(), pred_p50[:600].max())
    plt.plot([min_v, max_v], [min_v, max_v], "r--", linewidth=2, label="Perfect Agreement (1:1)")
    plt.title("Actual vs Predicted Kitchen Preparation Time (P50)", fontsize=13, fontweight="bold")
    plt.xlabel("Actual Preparation Time (min)")
    plt.ylabel("Predicted P50 Prep Time (min)")
    plt.legend()
    plt.savefig(CHARTS_DIR / "actual_vs_predicted_prep.png", dpi=200)
    plt.close()

    # Chart 2: Residual Distribution
    residuals = y_test_prep - pred_p50
    plt.figure(figsize=(8, 5))
    sns.histplot(residuals, kde=True, color="#c94c4c", bins=30)
    plt.axvline(0, color="black", linestyle="--")
    plt.title("Preparation Time Residual Distribution (Actual - P50 Pred)", fontsize=13, fontweight="bold")
    plt.xlabel("Residual Error (min)")
    plt.ylabel("Frequency")
    plt.savefig(CHARTS_DIR / "residual_distribution.png", dpi=200)
    plt.close()

    # Chart 3: P50 vs P90 Comparison
    sample_indices = np.argsort(y_test_prep[:80])
    plt.figure(figsize=(11, 5.5))
    plt.plot(np.arange(len(sample_indices)), y_test_prep[:80][sample_indices], "k-o", label="Actual Prep Time", markersize=4)
    plt.plot(np.arange(len(sample_indices)), pred_p50[:80][sample_indices], "b--s", label="P50 Predicted (Median)", markersize=4)
    plt.plot(np.arange(len(sample_indices)), pred_p90[:80][sample_indices], "g-.^", label="P90 Predicted (Conservative)", markersize=4)
    plt.fill_between(np.arange(len(sample_indices)), pred_p50[:80][sample_indices], pred_p90[:80][sample_indices], color="lightgreen", alpha=0.3, label="P50-P90 Prediction Interval")
    plt.title("P50 vs P90 Quantile Prediction Interval on Test Orders", fontsize=13, fontweight="bold")
    plt.xlabel("Test Order Sample (Sorted by Duration)")
    plt.ylabel("Preparation Time (min)")
    plt.legend()
    plt.savefig(CHARTS_DIR / "p50_vs_p90_comparison.png", dpi=200)
    plt.close()

    # Chart 4: Prediction Error Distribution
    plt.figure(figsize=(8, 5))
    travel_errors = y_test_travel - pred_travel
    sns.histplot(travel_errors, kde=True, color="#4a7c59", bins=30)
    plt.axvline(0, color="black", linestyle="--")
    plt.title("Rider Travel Time Prediction Error Distribution", fontsize=13, fontweight="bold")
    plt.xlabel("Error (min)")
    plt.ylabel("Frequency")
    plt.savefig(CHARTS_DIR / "travel_error_distribution.png", dpi=200)
    plt.close()

    # Chart 5: Feature Importance via Permutation Importance on Model A
    logger.info("Computing permutation importance for P50 model...")
    # Use 1500 test samples for fast, reliable permutation scoring
    perm_res = permutation_importance(
        model_p50,
        X_test[:1500],
        y_test_prep[:1500],
        n_repeats=5,
        random_state=RANDOM_STATE,
        scoring="neg_mean_absolute_error",
    )
    # Get feature names from preprocessor
    cat_encoder = preprocessor.named_transformers_["cat"]
    cat_names = cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES).tolist()
    feature_names = NUMERICAL_FEATURES + cat_names

    top_n = min(12, len(feature_names))
    sorted_idx = perm_res.importances_mean.argsort()[-top_n:]
    plt.figure(figsize=(9, 6))
    plt.barh(np.arange(top_n), perm_res.importances_mean[sorted_idx], color="#2b5c8f")
    plt.yticks(np.arange(top_n), [feature_names[i] for i in sorted_idx])
    plt.title("Permutation Feature Importance for Kitchen Preparation Model (P50)", fontsize=13, fontweight="bold")
    plt.xlabel("Mean Drop in Test Negative MAE (min)")
    plt.savefig(CHARTS_DIR / "feature_importance.png", dpi=200)
    plt.close()

    # Chart 6: Model Performance Comparison
    plt.figure(figsize=(8, 5))
    models_list = ["Prep P50", "Prep P90", "Rider Travel"]
    mae_list = [p50_mae, p90_mae, travel_mae]
    rmse_list = [p50_rmse, p90_rmse, travel_rmse]

    x = np.arange(len(models_list))
    width = 0.35
    plt.bar(x - width/2, mae_list, width, label="MAE (min)", color="#2b5c8f")
    plt.bar(x + width/2, rmse_list, width, label="RMSE (min)", color="#e07a5f")
    plt.xticks(x, models_list)
    plt.ylabel("Error (minutes)")
    plt.title("Model Error Comparison (MAE vs RMSE)", fontsize=13, fontweight="bold")
    plt.legend()
    plt.savefig(CHARTS_DIR / "model_performance_comparison.png", dpi=200)
    plt.close()

    logger.info("All evaluation charts generated successfully.")
    return report


if __name__ == "__main__":
    rep = run_full_evaluation()
    print("\nFull Model Evaluation completed successfully.")
    print(json.dumps(rep, indent=2))
