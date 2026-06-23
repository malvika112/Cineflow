"""
SQLite implementation of IStockRepository.

THIS IS THE FILE THAT PREVENTS OVERSELL.

decrement_if_available() runs a single atomic UPDATE with a WHERE guard:

    UPDATE stock
    SET quantity = quantity - ?, last_updated = datetime('now')
    WHERE item_id = ? AND quantity >= ?

SQLite serialises all writers against the same database file (it takes an
exclusive lock for the duration of a write transaction), so when two
threads/requests try to decrement the same row concurrently, one of them
runs to completion first. By the time the second one's UPDATE executes,
it sees the already-decremented quantity. If that's not enough to satisfy
the WHERE clause, the UPDATE matches zero rows — cursor.rowcount == 0 —
and we return False. No row is ever allowed to go negative; the CHECK
(quantity >= 0) constraint in schema.sql is a second, redundant backstop.

We use Python's sqlite3 module directly (not an ORM) specifically so this
guarantee is visible and auditable in one place, rather than hidden
behind ORM session/flush semantics.
"""
import sqlite3
import threading

from core.ports.stock_port import IStockRepository


class SQLiteStockRepository(IStockRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path
        # check_same_thread=False because FastAPI may serve requests from
        # different worker threads; a lock guards each individual call so
        # we never have two threads issuing statements on one connection
        # at once. SQLite itself still serialises at the file level.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()

    def decrement_if_available(self, item_id: int, qty: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE stock
                SET quantity = quantity - ?, last_updated = datetime('now')
                WHERE item_id = ? AND quantity >= ?
                """,
                (qty, item_id, qty),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def increment(self, item_id: int, qty: int) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE stock
                SET quantity = quantity + ?, last_updated = datetime('now')
                WHERE item_id = ?
                """,
                (qty, item_id),
            )
            self._conn.commit()

    def get_quantity(self, item_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT quantity FROM stock WHERE item_id = ?", (item_id,)
            ).fetchone()
            return row[0] if row else 0

    def get_all_quantities(self) -> dict[int, int]:
        with self._lock:
            rows = self._conn.execute("SELECT item_id, quantity FROM stock").fetchall()
            return {item_id: qty for item_id, qty in rows}

    def set_quantity(self, item_id: int, qty: int) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO stock (item_id, quantity, last_updated)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(item_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    last_updated = excluded.last_updated
                """,
                (item_id, qty),
            )
            self._conn.commit()
