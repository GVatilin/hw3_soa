from sqlalchemy import select
from sqlalchemy.orm import Session

from flight_service.app.db.models import SeatReservation, SeatReservationStatus


class SeatReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_booking_id(self, booking_id: str) -> SeatReservation | None:
        stmt = select(SeatReservation).where(SeatReservation.booking_id == booking_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def lock_by_booking_id(self, booking_id: str) -> SeatReservation | None:
        stmt = select(SeatReservation).where(SeatReservation.booking_id == booking_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_by_booking_id(self, booking_id: str) -> SeatReservation | None:
        stmt = select(SeatReservation).where(
            SeatReservation.booking_id == booking_id,
            SeatReservation.status == SeatReservationStatus.ACTIVE,
        )
        return self.db.execute(stmt).scalar_one_or_none()
