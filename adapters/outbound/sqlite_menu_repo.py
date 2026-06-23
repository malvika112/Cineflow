"""SQLite implementation of IMenuRepository."""
import sqlite3
import threading

from core.domain.menu_item import MenuItem
from core.ports.menu_port import IMenuRepository


def _row_to_item(row, quantity: int = 0) -> MenuItem:
    return MenuItem(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price_paise=row["price_paise"],
        category=row["category"],
        is_active=bool(row["is_active"]),
        quantity_available=quantity,
    )


class SQLiteMenuRepository(IMenuRepository):
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def get_item(self, item_id: int) -> MenuItem | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM menu_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                return None
            # quantity_available is filled in by the caller (menu_service)
            # via a join with stock — repository returns 0 here as a
            # placeholder since this repo has no knowledge of stock.
            return _row_to_item(row, quantity=0)

    def list_all(self, include_inactive: bool = False) -> list[MenuItem]:
        with self._lock:
            if include_inactive:
                rows = self._conn.execute("SELECT * FROM menu_items").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM menu_items WHERE is_active = 1"
                ).fetchall()
            return [_row_to_item(row) for row in rows]

    def create_item(self, name: str, description: str, price_paise: int,
                     category: str, initial_quantity: int) -> MenuItem:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO menu_items (name, description, price_paise, category, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (name, description, price_paise, category),
            )
            item_id = cur.lastrowid
            self._conn.execute(
                "INSERT INTO stock (item_id, quantity) VALUES (?, ?)",
                (item_id, initial_quantity),
            )
            self._conn.commit()
            return MenuItem(
                id=item_id, name=name, description=description,
                price_paise=price_paise, category=category, is_active=True,
                quantity_available=initial_quantity,
            )

    def update_item(self, item_id: int, **fields) -> MenuItem:
        if not fields:
            return self.get_item(item_id)

        allowed = {"name", "description", "price_paise", "category", "is_active"}
        set_clauses = []
        values = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            set_clauses.append(f"{key} = ?")
            values.append(int(value) if key == "is_active" else value)

        with self._lock:
            if set_clauses:
                values.append(item_id)
                self._conn.execute(
                    f"UPDATE menu_items SET {', '.join(set_clauses)} WHERE id = ?",
                    values,
                )
                self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM menu_items WHERE id = ?", (item_id,)
            ).fetchone()
            return _row_to_item(row)
