"""
Stock repository port.

This is the most important interface in the whole system. The entire
oversell-prevention guarantee rests on decrement_if_available() being
implemented as a single atomic operation by whatever adapter sits behind
this port — see adapters/outbound/sqlite_stock_repo.py for the real
implementation, and tests/unit/test_stock_service.py for the proof.

core/services/stock_service.py depends ONLY on this interface, never on
SQLite directly. That's what makes the oversell logic testable without
a real database (see tests/unit, which uses an in-memory fake of this port).
"""
from abc import ABC, abstractmethod


class IStockRepository(ABC):

    @abstractmethod
    def decrement_if_available(self, item_id: int, qty: int) -> bool:
        """Atomically decrement stock by qty, but only if enough stock
        exists. Must be implemented as a single atomic operation at the
        adapter level (e.g. one SQL UPDATE with a WHERE qty >= ? guard).

        Returns:
            True  - decrement succeeded, qty units were reserved
            False - insufficient stock, nothing was changed
        """
        raise NotImplementedError

    @abstractmethod
    def increment(self, item_id: int, qty: int) -> None:
        """Add qty back to stock. Used for: admin restock, and releasing
        a reservation when an order is cancelled."""
        raise NotImplementedError

    @abstractmethod
    def get_quantity(self, item_id: int) -> int:
        """Live read of current stock level. Never cached — callers that
        need a fast/cached view should go through menu_service instead,
        which is allowed to be a little stale."""
        raise NotImplementedError

    @abstractmethod
    def get_all_quantities(self) -> dict[int, int]:
        """Bulk read, used by menu_service to build the cached menu view."""
        raise NotImplementedError

    @abstractmethod
    def set_quantity(self, item_id: int, qty: int) -> None:
        """Admin-only: hard-set stock to an exact value (e.g. initial
        stocking, or correcting a count after a physical inventory check)."""
        raise NotImplementedError
