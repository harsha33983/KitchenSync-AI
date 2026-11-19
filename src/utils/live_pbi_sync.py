"""
Live Power BI Database Synchronizer Daemon
Monitors SQLite database changes in real time using PRAGMA data_version
and automatically updates Power BI star-schema datasets whenever the database changes.
"""

import time
import sqlite3
import logging
import argparse
from config import DATABASE_FILE
from src.utils.export_powerbi import export_powerbi_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_current_data_version(db_path) -> int:
    """Fetches SQLite engine transaction version counter."""
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cur = conn.cursor()
        cur.execute("PRAGMA data_version;")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Error querying data_version: {e}")
        return -1


def sync_once():
    """Forces an immediate export from SQLite to Power BI data mart."""
    logger.info("Executing immediate database -> Power BI synchronization...")
    export_powerbi_datasets()
    logger.info("Synchronization complete.")


def run_sync_daemon(poll_interval_sec: float = 2.0, max_iterations: int = None):
    """Continuously watches SQLite database and updates Power BI marts on transaction commits."""
    logger.info(f"Starting Live Power BI Sync Daemon on {DATABASE_FILE} (Poll: {poll_interval_sec}s)...")
    last_version = get_current_data_version(DATABASE_FILE)
    iterations = 0

    # Initial export
    sync_once()

    try:
        while True:
            time.sleep(poll_interval_sec)
            current_version = get_current_data_version(DATABASE_FILE)
            if current_version != last_version and current_version != -1:
                logger.info(f"Database change detected! (Version {last_version} -> {current_version})")
                sync_once()
                last_version = current_version

            iterations += 1
            if max_iterations and iterations >= max_iterations:
                break
    except KeyboardInterrupt:
        logger.info("Live Power BI Sync Daemon stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Power BI Database Synchronizer")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous background watcher")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.daemon:
        run_sync_daemon(poll_interval_sec=args.interval)
    else:
        sync_once()
