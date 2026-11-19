"""
Rider Management Service
Handles rider availability, assignment, status updates, and fleet analytics.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.connection import get_db_session
from src.database.models import Rider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RiderService:
    """Manages courier operations and assignments."""

    @staticmethod
    def get_all_riders(session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all riders in the fleet."""
        def _query(s: Session):
            riders = s.query(Rider).all()
            return [
                {
                    "rider_id": r.rider_id,
                    "rider_status": r.rider_status,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "vehicle_type": r.vehicle_type,
                }
                for r in riders
            ]

        if session:
            return _query(session)
        with get_db_session() as s:
            return _query(s)

    @staticmethod
    def get_available_riders(session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns riders with status AVAILABLE."""
        def _query(s: Session):
            riders = s.query(Rider).filter(Rider.rider_status == "AVAILABLE").all()
            return [
                {
                    "rider_id": r.rider_id,
                    "rider_status": r.rider_status,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "vehicle_type": r.vehicle_type,
                }
                for r in riders
            ]

        if session:
            return _query(session)
        with get_db_session() as s:
            return _query(s)

    @staticmethod
    def update_rider_status(rider_id: str, new_status: str, session: Optional[Session] = None) -> bool:
        """Updates a rider's operational status."""
        def _update(s: Session):
            rider = s.query(Rider).filter(Rider.rider_id == rider_id).first()
            if not rider:
                return False
            rider.rider_status = new_status
            return True

        if session:
            return _update(session)
        with get_db_session() as s:
            return _update(s)

    @staticmethod
    def assign_available_rider(session: Optional[Session] = None) -> Optional[str]:
        """Finds and assigns the first available rider, updating their status to ASSIGNED."""
        def _assign(s: Session):
            rider = s.query(Rider).filter(Rider.rider_status == "AVAILABLE").first()
            if rider:
                rider.rider_status = "ASSIGNED"
                return rider.rider_id
            return None

        if session:
            return _assign(session)
        with get_db_session() as s:
            return _assign(s)


rider_service = RiderService()
