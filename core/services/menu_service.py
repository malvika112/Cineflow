"""
Menu service.

Combines catalogue data (rarely changes, cacheable) with live stock data
(changes constantly, never cached) into the MenuItem view the patron app
displays. The 10s-TTL cache the design doc describes lives one layer up,
in the FastAPI adapter (adapters/inbound/http) — this service is cache-
agnostic and always does a live join. The HTTP layer decides whether to
call this every request or serve a memoised copy.
"""
from dataclasses import replace
from core.domain.menu_item import MenuItem
from core.ports.menu_port import IMenuRepository
from core.ports.stock_port import IStockRepository


class MenuService:
    def __init__(self, menu_repo: IMenuRepository, stock_repo: IStockRepository):
        self._menu_repo = menu_repo
        self._stock_repo = stock_repo

    def list_menu(self, include_inactive: bool = False) -> list[MenuItem]:
        """Patron-facing by default (include_inactive=False) — admin view
        passes True to also see deactivated items."""
        items = self._menu_repo.list_all(include_inactive=include_inactive)
        levels = self._stock_repo.get_all_quantities()
        return [
            replace(item, quantity_available=levels.get(item.id, 0))
            for item in items
        ]

    def list_available(self) -> list[MenuItem]:
        """Strictly what a patron should be able to add to cart: active
        AND in stock. This is the method the patron /menu endpoint calls."""
        return [item for item in self.list_menu(include_inactive=False) if item.is_orderable]

    def get_item(self, item_id: int) -> MenuItem | None:
        item = self._menu_repo.get_item(item_id)
        if item is None:
            return None
        qty = self._stock_repo.get_quantity(item_id)
        return replace(item, quantity_available=qty)

    def create_item(self, name: str, description: str, price_paise: int,
                     category: str, initial_quantity: int) -> MenuItem:
        return self._menu_repo.create_item(
            name, description, price_paise, category, initial_quantity
        )

    def update_item(self, item_id: int, **fields) -> MenuItem:
        return self._menu_repo.update_item(item_id, **fields)
