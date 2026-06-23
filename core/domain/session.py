"""
Patron session — binds a device to a seat for the duration of a show.

We deliberately do NOT build full user accounts (out of scope per the
design doc). A session is just enough identity to: (a) let the offer
service enforce per-user caps, and (b) let a patron reload the order
status page and still see their order.
"""
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_session_token() -> str:
    return secrets.token_urlsafe(24)


@dataclass(frozen=True)
class PatronSession:
    token: str
    seat_number: str
    screen_id: str
    created_at: datetime = field(default_factory=_utcnow)

    @classmethod
    def create(cls, seat_number: str, screen_id: str) -> "PatronSession":
        return cls(token=generate_session_token(), seat_number=seat_number, screen_id=screen_id)
