"""SQLite implementation of IOrderRepository."""
import sqlite3
import threading

from core.domain.order import Order, OrderLine, OrderStatus
from core.ports.order_port import IOrderRepository


def _row_to_order(conn, row) -> Order:
    item_rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (row["id"],)
    ).fetchall()
    lines = [
        OrderLine(
            item_id=r["item_id"],
            item_name=r["item_name"],
            quantity=r["quantity"],
            unit_price_paise=r["unit_price_paise"],
        )
        for r in item_rows
    ]
    return Order(
        id=row["id"],
        session_id=row["session_id"],
        seat_number=row["seat_number"],
        lines=lines,
        status=OrderStatus(row["status"]),
        discount_paise=row["discount_paise"],
        offer_code=row["offer_code"],
    )


class SQLiteOrderRepository(IOrderRepository):
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def save(self, order: Order) -> Order:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO orders (id, session_id, seat_number, status, discount_paise, offer_code)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order.id, order.session_id, order.seat_number, order.status.value,
                 order.discount_paise, order.offer_code),
            )
            for line in order.lines:
                self._conn.execute(
                    """
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price_paise)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (order.id, line.item_id, line.item_name, line.quantity, line.unit_price_paise),
                )
            self._conn.commit()
            return order

    def get(self, order_id: str) -> Order | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row is None:
                return None
            return _row_to_order(self._conn, row)

    def update_status(self, order_id: str, new_status: OrderStatus) -> Order:
        with self._lock:
            self._conn.execute(
                "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (new_status.value, order_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            return _row_to_order(self._conn, row)

    def list_by_status(self, status: OrderStatus | None = None) -> list[Order]:
        with self._lock:
            if status is None:
                rows = self._conn.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                ).fetchall()
            return [_row_to_order(self._conn, row) for row in rows]
