"""
SQLite implementation of IOfferRepository.

record_redemption() and the per-user-cap check it supports together
need to be race-safe: two near-simultaneous checkouts by the same
session, both using a per_user_cap=1 offer, must not both succeed.
We rely on SQLite's single-writer serialisation the same way the stock
repo does — the lock ensures count_redemptions() (read) and
record_redemption() (write) within one offer_service.apply_to_order()
call are never interleaved with another thread's read+write pair.
"""
import sqlite3
import threading
from datetime import datetime, timezone

from core.domain.offer import Offer, DiscountType
from core.ports.offer_port import IOfferRepository


def _parse_dt(value: str) -> datetime:
    """Offers are stored as ISO strings. Seed data and admin-created
    offers may arrive naive (no UTC offset) — we treat all stored
    timestamps as UTC and normalise to timezone-aware here, once, at
    the adapter boundary. This keeps every datetime that reaches the
    domain layer comparably aware, avoiding the classic naive-vs-aware
    TypeError when offer_service compares against datetime.now(timezone.utc)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_offer(row) -> Offer:
    return Offer(
        id=row["id"],
        code=row["code"],
        discount_type=DiscountType(row["discount_type"]),
        discount_value=row["discount_value"],
        min_order_paise=row["min_order_paise"],
        max_uses=row["max_uses"],
        per_user_cap=row["per_user_cap"],
        valid_from=_parse_dt(row["valid_from"]),
        valid_until=_parse_dt(row["valid_until"]),
        stackable=bool(row["stackable"]),
    )


class SQLiteOfferRepository(IOfferRepository):
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def list_active(self) -> list[Offer]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM offers").fetchall()
            return [_row_to_offer(r) for r in rows]

    def get_by_code(self, code: str) -> Offer | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM offers WHERE code = ?", (code,)
            ).fetchone()
            return _row_to_offer(row) if row else None

    def count_redemptions(self, offer_id: str, session_id: str | None = None) -> int:
        with self._lock:
            if session_id is None:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM offer_redemptions WHERE offer_id = ?",
                    (offer_id,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM offer_redemptions WHERE offer_id = ? AND session_id = ?",
                    (offer_id, session_id),
                ).fetchone()
            return row[0]

    def record_redemption(self, offer_id: str, session_id: str, order_id: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO offer_redemptions (offer_id, session_id, order_id)
                VALUES (?, ?, ?)
                """,
                (offer_id, session_id, order_id),
            )
            self._conn.commit()

    def create_offer(self, offer: Offer) -> Offer:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO offers (id, code, discount_type, discount_value, min_order_paise,
                                     max_uses, per_user_cap, valid_from, valid_until, stackable)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (offer.id, offer.code, offer.discount_type.value, offer.discount_value,
                 offer.min_order_paise, offer.max_uses, offer.per_user_cap,
                 offer.valid_from.isoformat(), offer.valid_until.isoformat(),
                 int(offer.stackable)),
            )
            self._conn.commit()
            return offer
