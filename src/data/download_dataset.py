"""
Dataset Downloader and Verification Module
Downloads real-world publicly available food delivery datasets from verified public endpoints.
Preserves original raw data integrity.
"""

import os
import sys
import logging
from pathlib import Path
import pandas as pd
import requests

from config import RAW_DATA_DIR, EXTERNAL_DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PRIMARY_TRAIN_URL = (
    "https://huggingface.co/datasets/aneesarom/Food-Delivery/resolve/main/data/train-00000-of-00001.parquet"
)
PRIMARY_TEST_URL = (
    "https://huggingface.co/datasets/aneesarom/Food-Delivery/resolve/main/data/test-00000-of-00001.parquet"
)
BENCHMARK_CSV_URL = (
    "https://raw.githubusercontent.com/bayuptrdn/Food_Delivery_Time_Prediction/main/Food_Delivery_Times.csv"
)


def download_file(url: str, dest_path: Path) -> Path:
    """Download a file with streaming and user-agent header."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading from {url} to {dest_path}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KitchenSyncAI/1.0"}
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)

    file_size_mb = dest_path.stat().st_size / (1024 * 1024)
    logger.info(f"Downloaded {dest_path.name} ({file_size_mb:.2f} MB)")
    return dest_path


def download_all_datasets() -> dict:
    """
    Downloads primary Zomato/Swiggy logistics dataset and secondary benchmark dataset.
    Returns dictionary of dataset stats.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXTERNAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    train_parquet_path = RAW_DATA_DIR / "zomato_train.parquet"
    test_parquet_path = RAW_DATA_DIR / "zomato_test.parquet"
    raw_consolidated_csv = RAW_DATA_DIR / "zomato_delivery_raw.csv"
    benchmark_csv_path = EXTERNAL_DATA_DIR / "food_delivery_times_benchmark.csv"

    # 1. Download Primary Train Parquet
    if not train_parquet_path.exists():
        download_file(PRIMARY_TRAIN_URL, train_parquet_path)
    df_train = pd.read_parquet(train_parquet_path)
    logger.info(f"Primary train partition: {df_train.shape[0]} rows, {df_train.shape[1]} columns")

    # 2. Download Primary Test Parquet
    if not test_parquet_path.exists():
        download_file(PRIMARY_TEST_URL, test_parquet_path)
    df_test = pd.read_parquet(test_parquet_path)
    logger.info(f"Primary test partition: {df_test.shape[0]} rows, {df_test.shape[1]} columns")

    # Combine into single raw canonical dataset
    df_combined = pd.concat([df_train, df_test], ignore_index=True)
    df_combined.to_csv(raw_consolidated_csv, index=False)
    logger.info(f"Consolidated raw Zomato dataset saved: {df_combined.shape[0]} rows to {raw_consolidated_csv}")

    # 3. Download Secondary Benchmark CSV
    if not benchmark_csv_path.exists():
        download_file(BENCHMARK_CSV_URL, benchmark_csv_path)
    df_benchmark = pd.read_csv(benchmark_csv_path)
    logger.info(f"Benchmark dataset saved: {df_benchmark.shape[0]} rows to {benchmark_csv_path}")

    stats = {
        "primary_records": len(df_combined),
        "primary_columns": list(df_combined.columns),
        "benchmark_records": len(df_benchmark),
        "benchmark_columns": list(df_benchmark.columns),
        "raw_csv_path": str(raw_consolidated_csv),
        "benchmark_csv_path": str(benchmark_csv_path),
    }

    print("\n" + "=" * 60)
    print("DATASET DOWNLOAD & INTEGRITY REPORT")
    print("=" * 60)
    print(f"Primary Logistics Dataset: {len(df_combined):,} records")
    print(f"  - Source: Hugging Face (aneesarom/Food-Delivery, Kaggle Mirror)")
    print(f"  - Train Partition: {len(df_train):,} rows")
    print(f"  - Test Partition: {len(df_test):,} rows")
    print(f"  - Features: {len(df_combined.columns)} columns")
    print(f"  - Saved to: {raw_consolidated_csv}")
    print(f"\nSecondary Benchmark Dataset: {len(df_benchmark):,} records")
    print(f"  - Source: GitHub bayuptrdn/Food_Delivery_Time_Prediction")
    print(f"  - Saved to: {benchmark_csv_path}")
    print("=" * 60 + "\n")

    return stats


if __name__ == "__main__":
    download_all_datasets()
