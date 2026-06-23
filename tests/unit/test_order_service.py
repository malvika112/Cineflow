"""Unit tests for order service — status transitions and checkout flow."""
import pytest

from core.domain.order import OrderStatus, InvalidStatusTransitionError
from core.services.order_service import OrderService, EmptyCartError
from core.services.stock_service import StockService, InsufficientStockError
from core.services.menu_service import MenuService
from core.services.offer_service import OfferService
from tests.unit.fakes import FakeStockRepo, FakeMenuRepo, FakeOrderRepo, FakeOfferRepo


@pytest.fixture
def services():
    stock_repo = FakeStockRepo()
    menu_repo = FakeMenuRepo()
    order_repo = FakeOrderRepo()
    offer_repo = FakeOfferRepo()

    stock_svc = StockService(stock_repo)
    menu_svc = MenuService(menu_repo, stock_repo)
    offer_svc = OfferService(offer_repo)
    order_svc = OrderService(order_repo, stock_svc, menu_svc, offer_svc)

    # Seed one menu item
    item = menu_repo.create_item("Popcorn", "Large", 25000, "snacks", 10)
    stock_repo.set_quantity(item.id, 10)

    return order_svc, stock_repo, menu_repo, order_repo, item


def test_place_order_success(services):
    order_svc, stock_repo, _, _, item = services
    order = order_svc.place_order(
        session_id="s1", seat_number="A1",
        cart_items=[{"item_id": item.id, "quantity": 2}],
    )
    assert order.status == OrderStatus.PLACED
    assert order.total_paise == 50000
    assert stock_repo.get_quantity(item.id) == 8


def test_empty_cart_rejected(services):
    order_svc, *_ = services
    with pytest.raises(EmptyCartError):
        order_svc.place_order(session_id="s1", seat_number="A1", cart_items=[])


def test_unknown_item_rejected(services):
    order_svc, *_ = services
    with pytest.raises(ValueError):
        order_svc.place_order(
            session_id="s1", seat_number="A1",
            cart_items=[{"item_id": 9999, "quantity": 1}],
        )


def test_insufficient_stock_rolls_back(services):
    order_svc, stock_repo, menu_repo, _, item = services
    # Add a second item with only 0 stock
    item2 = menu_repo.create_item("Nachos", "Cheese", 22000, "snacks", 0)
    stock_repo.set_quantity(item2.id, 0)

    with pytest.raises(InsufficientStockError):
        order_svc.place_order(
            session_id="s1", seat_number="A1",
            cart_items=[
                {"item_id": item.id, "quantity": 2},   # this would succeed
                {"item_id": item2.id, "quantity": 1},  # this fails → rollback
            ],
        )
    # Critically: item1 stock must be RESTORED (rollback happened)
    assert stock_repo.get_quantity(item.id) == 10


def test_status_placed_to_preparing(services):
    order_svc, _, _, _, item = services
    order = order_svc.place_order("s1", "A1", [{"item_id": item.id, "quantity": 1}])
    updated = order_svc.update_status(order.id, OrderStatus.PREPARING)
    assert updated.status == OrderStatus.PREPARING


def test_invalid_status_skip_raises(services):
    order_svc, _, _, _, item = services
    order = order_svc.place_order("s1", "A1", [{"item_id": item.id, "quantity": 1}])
    with pytest.raises(InvalidStatusTransitionError):
        order_svc.update_status(order.id, OrderStatus.DELIVERED)


def test_cancel_restores_stock(services):
    order_svc, stock_repo, _, _, item = services
    order = order_svc.place_order("s1", "A1", [{"item_id": item.id, "quantity": 3}])
    assert stock_repo.get_quantity(item.id) == 7
    order_svc.update_status(order.id, OrderStatus.CANCELLED)
    assert stock_repo.get_quantity(item.id) == 10


def test_get_order(services):
    order_svc, _, _, _, item = services
    order = order_svc.place_order("s1", "A1", [{"item_id": item.id, "quantity": 1}])
    fetched = order_svc.get_order(order.id)
    assert fetched.id == order.id


def test_list_orders_by_status(services):
    order_svc, _, _, _, item = services
    o1 = order_svc.place_order("s1", "A1", [{"item_id": item.id, "quantity": 1}])
    o2 = order_svc.place_order("s2", "B2", [{"item_id": item.id, "quantity": 1}])
    order_svc.update_status(o1.id, OrderStatus.PREPARING)

    placed = order_svc.list_orders(OrderStatus.PLACED)
    preparing = order_svc.list_orders(OrderStatus.PREPARING)

    assert len(placed) == 1 and placed[0].id == o2.id
    assert len(preparing) == 1 and preparing[0].id == o1.id
