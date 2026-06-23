"""
Stock service — the oversell-prevention boundary.

Every place in the codebase that wants to reserve stock MUST go through
reserve() here. Nothing else is allowed to touch IStockRepository directly.
That single chokepoint is what makes it possible to reason about and test
oversell prevention in one place instead of N places.
"""
from core.ports.stock_port import IStockRepository


class InsufficientStockError(Exception):
    def __init__(self, item_id: int, requested: int, available: int):
        self.item_id = item_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Cannot reserve {requested} of item {item_id}: only {available} available"
        )


class StockService:
    def __init__(self, stock_repo: IStockRepository):
        self._repo = stock_repo

    def reserve(self, item_id: int, qty: int) -> None:
        """Attempt to atomically reserve qty units of item_id.

        Raises InsufficientStockError if not enough stock exists — the
        caller (order_service) is expected to catch this per line item
        and fail the whole order, since a cinema cannot deliver half an
        order. We deliberately do NOT return a bool here (unlike the
        port) — at the service layer, failure is exceptional, so it's
        raised rather than silently returned, forcing callers to handle it.
        """
        if qty <= 0:
            raise ValueError("qty must be positive")

        succeeded = self._repo.decrement_if_available(item_id, qty)
        if not succeeded:
            available = self._repo.get_quantity(item_id)
            raise InsufficientStockError(item_id, qty, available)

    def release(self, item_id: int, qty: int) -> None:
        """Give stock back — used when an order is cancelled after stock
        was already reserved."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._repo.increment(item_id, qty)

    def get_quantity(self, item_id: int) -> int:
        return self._repo.get_quantity(item_id)

    def get_live_levels(self) -> dict[int, int]:
        """Used by menu_service to refresh its cache."""
        return self._repo.get_all_quantities()

    def restock(self, item_id: int, qty: int) -> None:
        """Admin operation: add new stock (e.g. kitchen made more popcorn)."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._repo.increment(item_id, qty)

    def set_quantity(self, item_id: int, qty: int) -> None:
        """Admin operation: hard-set stock to an exact count."""
        if qty < 0:
            raise ValueError("qty cannot be negative")
        self._repo.set_quantity(item_id, qty)
