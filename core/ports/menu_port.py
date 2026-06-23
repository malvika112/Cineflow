"""Menu repository port — catalogue data only, no stock numbers.

Stock lives behind IStockRepository on purpose: the menu catalogue
(name, price, description) changes rarely and can be cached aggressively,
while stock changes constantly and must always be read live. Splitting
them into two ports makes that distinction impossible to accidentally
blur in the adapter layer.
"""
from abc import ABC, abstractmethod
from core.domain.menu_item import MenuItem


class IMenuRepository(ABC):

    @abstractmethod
    def get_item(self, item_id: int) -> MenuItem | None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self, include_inactive: bool = False) -> list[MenuItem]:
        """Returns catalogue rows joined with current stock. include_inactive
        is for the admin view; patron-facing reads should always pass False."""
        raise NotImplementedError

    @abstractmethod
    def create_item(self, name: str, description: str, price_paise: int,
                     category: str, initial_quantity: int) -> MenuItem:
        raise NotImplementedError

    @abstractmethod
    def update_item(self, item_id: int, **fields) -> MenuItem:
        """Partial update — only fields passed are changed. Used by the
        admin edit screen and by deactivate (is_active=False)."""
        raise NotImplementedError
