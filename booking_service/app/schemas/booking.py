from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class CreateBookingRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    flight_id: UUID
    passenger_name: str = Field(..., min_length=2, max_length=255)
    passenger_email: EmailStr
    seat_count: int = Field(..., gt=0, le=10)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    flight_id: UUID
    passenger_name: str
    passenger_email: EmailStr
    seat_count: int
    total_price: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
