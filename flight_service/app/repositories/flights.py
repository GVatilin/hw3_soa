from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from flight_service.app.db.models import Flight, FlightStatus


class FlightRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, flight_id: str) -> Flight | None:
        return self.db.get(Flight, flight_id)

    def lock_by_id(self, flight_id: str) -> Flight | None:
        stmt = select(Flight).where(Flight.id == flight_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def search_scheduled(self, origin: str, destination: str, departure_date: date | None) -> list[Flight]:
        stmt = (
            select(Flight)
            .where(
                Flight.origin == origin,
                Flight.destination == destination,
                Flight.status == FlightStatus.SCHEDULED,
            )
            .order_by(Flight.departure_time.asc())
        )

        if departure_date:
            stmt = stmt.where(Flight.departure_date == departure_date)

        return list(self.db.execute(stmt).scalars().all())
