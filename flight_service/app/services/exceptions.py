class FlightNotFoundError(Exception):
    pass


class ReservationNotFoundError(Exception):
    pass


class NotEnoughSeatsError(Exception):
    pass


class InvalidReservationStateError(Exception):
    pass


class ValidationError(Exception):
    pass
