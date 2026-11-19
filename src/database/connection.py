"""
SQLite Database Connection and Initialization Module
Ensures thread-safe connections, foreign key enforcement, schema creation,
and active kitchen queue window function execution.
"""

import logging
from pathlib import Path
from contextlib import contextmanager
import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from config import DATABASE_URL, DATABASE_FILE, RAW_DATA_DIR, PROCESSED_DATASET_PATH
from src.database.models import Base, Store, Rider, Order, DispatchPrediction, KitchenEvent, PerformanceMetric

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Ensure data directory exists
DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Create SQLAlchemy Engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


# Mandatory: Enable SQLite Foreign Keys for every connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session():
    """Context manager for transactional database operations."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session rolled back due to error: {e}")
        raise
    finally:
        session.close()


def calculate_active_kitchen_orders(session: Session, store_id: str = None) -> dict:
    """
    Executes the mandatory SQLite WINDOW FUNCTION query:
    Calculates active kitchen orders per store using COUNT(*) OVER (PARTITION BY store_id).
    Returns a dictionary mapping store_id -> active_orders_count.
    """
    sql_query = text(
        """
        WITH active_orders AS (
            SELECT
                order_id,
                store_id,
                order_status
            FROM orders
            WHERE order_status IN (
                'PLACED',
                'PREPARING',
                'PACKING'
            )
        )
        SELECT
            order_id,
            store_id,
            COUNT(*) OVER (
                PARTITION BY store_id
            ) AS active_orders_per_store
        FROM active_orders;
        """
    )

    result = session.execute(sql_query).fetchall()
    store_queue_counts = {}
    for row in result:
        # row: (order_id, store_id, active_orders_per_store)
        store_queue_counts[row[1]] = row[2]

    if store_id:
        return store_queue_counts.get(store_id, 0)
    return store_queue_counts


def seed_stores_and_riders(session: Session):
    """Populates stores and riders from real dataset if tables are empty."""
    store_count = session.query(Store).count()
    if store_count == 0:
        logger.info("Seeding store catalog from real dataset...")
        raw_csv = RAW_DATA_DIR / "zomato_delivery_raw.csv"
        if raw_csv.exists():
            df_raw = pd.read_csv(raw_csv)
            df_raw["store_id"] = (
                df_raw["Delivery_person_ID"]
                .astype(str)
                .apply(lambda x: x.split("DEL")[0] if "DEL" in x else x[:8])
            )
            top_stores = (
                df_raw.groupby("store_id")
                .agg({
                    "Restaurant_latitude": "median",
                    "Restaurant_longitude": "median",
                    "City": "first",
                })
                .reset_index()
                .head(25)
            )

            city_names = {
                "JAP": "Jaipur", "IND": "Indore", "MYS": "Mysore", "PUN": "Pune",
                "SUR": "Surat", "BAN": "Bangalore", "COI": "Coimbatore", "DEL": "Delhi",
                "HYD": "Hyderabad", "CHE": "Chennai", "KOC": "Kochi", "LUD": "Ludhiana"
            }

            for _, r in top_stores.iterrows():
                sid = str(r["store_id"])
                prefix = sid[:3]
                cname = city_names.get(prefix, "Central")
                sname = f"{cname} Gourmet Kitchen ({sid})"
                lat = float(abs(r["Restaurant_latitude"])) if pd.notna(r["Restaurant_latitude"]) else 26.9124
                lon = float(abs(r["Restaurant_longitude"])) if pd.notna(r["Restaurant_longitude"]) else 75.7873
                if lat < 5.0: lat = 26.9124
                if lon < 60.0: lon = 75.7873

                store = Store(
                    store_id=sid,
                    store_name=sname,
                    location=f"{cname} Commercial Hub",
                    latitude=round(lat, 4),
                    longitude=round(lon, 4),
                    average_prep_time=18.0,
                )
                session.add(store)

        session.commit()
        logger.info(f"Seeded {session.query(Store).count()} stores.")

    rider_count = session.query(Rider).count()
    if rider_count == 0:
        logger.info("Seeding initial rider delivery fleet...")
        vehicles = ["Scooter", "Bike", "Electric Scooter", "Bicycle"]
        statuses = ["AVAILABLE", "AVAILABLE", "AVAILABLE", "ASSIGNED"]
        for i in range(1, 26):
            rid = f"RIDER_{i:03d}"
            v_type = vehicles[i % len(vehicles)]
            stat = statuses[i % len(statuses)]
            rider = Rider(
                rider_id=rid,
                rider_status=stat,
                latitude=round(26.9124 + (i * 0.003), 4),
                longitude=round(75.7873 + (i * 0.003), 4),
                vehicle_type=v_type,
            )
            session.add(rider)
        session.commit()
        logger.info(f"Seeded {session.query(Rider).count()} riders.")


def init_database():
    """Initializes schema and tables in food_delivery.db and seeds initial master records."""
    logger.info(f"Initializing SQLite database at {DATABASE_FILE}...")
    Base.metadata.create_all(bind=engine)
    with get_db_session() as session:
        seed_stores_and_riders(session)
    logger.info("Database initialized successfully.")


if __name__ == "__main__":
    init_database()
    with get_db_session() as s:
        print("Stores count:", s.query(Store).count())
        print("Riders count:", s.query(Rider).count())
        # Test window function
        queues = calculate_active_kitchen_orders(s)
        print("Active Kitchen Queues (Window Function Result):", queues)
