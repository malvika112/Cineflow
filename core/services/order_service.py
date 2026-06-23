"""
Order service — orchestrates the checkout flow.

This is the one place that calls BOTH stock_service and offer_service,
because placing an order is the one operation that genuinely spans both
domains. Everywhere else, Stock and Offers stay fully decoupled from
each other.

Checkout sequence (also documented in the design doc's 25k walkthrough):
  1. Validate the cart isn't empty and items exist.
  2. Reserve stock for EVERY line item. If any single line fails, release
     whatever was already reserved for earlier lines in this same order
     (compensating action) and reject the whole order — a cinema can't
     deliver "everything except the popcorn", so we don't do partial orders.
  3. Evaluate + apply offers against the now-confirmed subtotal.
  4. Persist the order via IOrderRepository.
"""
import uuid
from datetime import datetime, timezone

from core.domain.order import Order, OrderLine, OrderStatus, InvalidStatusTransitionError
from core.ports.order_port import IOrderRepository
from core.services.stock_service import StockService, InsufficientStockError
from core.services.menu_service import MenuService
from core.services.offer_service import OfferService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmptyCartError(Exception):
    pass


class OrderService:
    def __init__(
        self,
        order_repo: IOrderRepository,
        stock_service: StockService,
        menu_service: MenuService,
        offer_service: OfferService | None = None,
    ):
        self._order_repo = order_repo
        self._stock_service = stock_service
        self._menu_service = menu_service
        self._offer_service = offer_service

    def place_order(
        self,
        session_id: str,
        seat_number: str,
        cart_items: list[dict],   # [{"item_id": int, "quantity": int}, ...]
        offer_code: str | None = None,
    ) -> Order:
        if not cart_items:
            raise EmptyCartError("Cart is empty")

        # ── Step 1: resolve menu items + build order lines at current price ──
        lines: list[OrderLine] = []
        for entry in cart_items:
            item = self._menu_service.get_item(entry["item_id"])
            if item is None:
                raise ValueError(f"Unknown item_id {entry['item_id']}")
            lines.append(OrderLine(
                item_id=item.id,
                item_name=item.name,
                quantity=entry["quantity"],
                unit_price_paise=item.price_paise,
            ))

        # ── Step 2: reserve stock for every line; roll back on partial failure ──
        reserved: list[tuple[int, int]] = []
        try:
            for line in lines:
                self._stock_service.reserve(line.item_id, line.quantity)
                reserved.append((line.item_id, line.quantity))
        except InsufficientStockError:
            # Compensating action — give back whatever we already took
            # for earlier lines in this same checkout attempt.
            for item_id, qty in reserved:
                self._stock_service.release(item_id, qty)
            raise

        # ── Step 3: build the order, apply offers against confirmed subtotal ──
        order_id = str(uuid.uuid4())
        order = Order(
            id=order_id,
            session_id=session_id,
            seat_number=seat_number,
            lines=lines,
        )

        if offer_code and self._offer_service is not None:
            result = self._offer_service.apply_to_order(
                subtotal_paise=order.subtotal_paise,
                session_id=session_id,
                order_id=order_id,
            )
            order.discount_paise = result.total_discount_paise
            if result.applied_offer_ids:
                order.offer_code = offer_code

        # ── Step 4: persist ──
        return self._order_repo.save(order)

    def get_order(self, order_id: str) -> Order | None:
        return self._order_repo.get(order_id)

    def update_status(self, order_id: str, new_status: OrderStatus) -> Order:
        order = self._order_repo.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        if not order.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                f"Cannot move order {order_id} from {order.status.value} to {new_status.value}"
            )

        if new_status == OrderStatus.CANCELLED:
            # Release reserved stock back to the pool.
            for line in order.lines:
                self._stock_service.release(line.item_id, line.quantity)

        return self._order_repo.update_status(order_id, new_status)

    def list_orders(self, status: OrderStatus | None = None) -> list[Order]:
        return self._order_repo.list_by_status(status)
