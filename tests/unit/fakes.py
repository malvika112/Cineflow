"""
In-memory fake adapters used across the unit test suite.

These implement the same Port interfaces as the real SQLite adapters,
which is the entire point of hexagonal architecture: business logic in
core/services can be tested with zero database, zero I/O, by swapping
in a fake that satisfies the same contract.
"""
from core.domain.menu_item import MenuItem
from core.ports.stock_port import IStockRepository
from core.ports.menu_port import IMenuRepository
from core.ports.order_port import IOrderRepository
from core.ports.offer_port import IOfferRepository


class FakeStockRepo(IStockRepository):
    def __init__(self):
        self.stock: dict[int, int] = {}

    def decrement_if_available(self, item_id: int, qty: int) -> bool:
        if self.stock.get(item_id, 0) >= qty:
            self.stock[item_id] -= qty
            return True
        return False

    def increment(self, item_id: int, qty: int) -> None:
        self.stock[item_id] = self.stock.get(item_id, 0) + qty

    def get_quantity(self, item_id: int) -> int:
        return self.stock.get(item_id, 0)

    def get_all_quantities(self) -> dict[int, int]:
        return dict(self.stock)

    def set_quantity(self, item_id: int, qty: int) -> None:
        self.stock[item_id] = qty


class FakeMenuRepo(IMenuRepository):
    def __init__(self):
        self.items: dict[int, MenuItem] = {}
        self._next_id = 1

    def get_item(self, item_id: int):
        return self.items.get(item_id)

    def list_all(self, include_inactive: bool = False):
        return [i for i in self.items.values() if include_inactive or i.is_active]

    def create_item(self, name, description, price_paise, category, initial_quantity):
        item = MenuItem(self._next_id, name, description, price_paise, category, True, initial_quantity)
        self.items[item.id] = item
        self._next_id += 1
        return item

    def update_item(self, item_id, **fields):
        old = self.items[item_id]
        merged = {**old.__dict__, **fields}
        new = MenuItem(**merged)
        self.items[item_id] = new
        return new


class FakeOrderRepo(IOrderRepository):
    def __init__(self):
        self.orders = {}

    def save(self, order):
        self.orders[order.id] = order
        return order

    def get(self, order_id):
        return self.orders.get(order_id)

    def update_status(self, order_id, new_status):
        self.orders[order_id].status = new_status
        return self.orders[order_id]

    def list_by_status(self, status=None):
        if status is None:
            return list(self.orders.values())
        return [o for o in self.orders.values() if o.status == status]


class FakeOfferRepo(IOfferRepository):
    def __init__(self):
        self.offers = {}
        self.redemptions: list[tuple[str, str, str]] = []

    def list_active(self):
        return list(self.offers.values())

    def get_by_code(self, code):
        return next((o for o in self.offers.values() if o.code == code), None)

    def count_redemptions(self, offer_id, session_id=None):
        return len([
            r for r in self.redemptions
            if r[0] == offer_id and (session_id is None or r[1] == session_id)
        ])

    def record_redemption(self, offer_id, session_id, order_id):
        self.redemptions.append((offer_id, session_id, order_id))

    def create_offer(self, offer):
        self.offers[offer.id] = offer
        return offer
