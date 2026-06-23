"""
Order domain entities.

The important rule encoded here: an order's status can only move forward
through a fixed sequence, never skip a step, never go backward (except
to 'cancelled', which is a terminal state from any non-delivered status).

This file has zero knowledge of HTTP or SQL — test it in complete isolation.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    PLACED = "placed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# The only legal forward transitions. Anything not in this map is invalid.
_VALID_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),   # terminal
    OrderStatus.CANCELLED: set(),   # terminal
}


class InvalidStatusTransitionError(Exception):
    """Raised when code tries to skip a step or move a terminal order."""
    pass


@dataclass(frozen=True)
class OrderLine:
    """One line item within an order — a snapshot of price at order time.
    We snapshot unit_price_paise so that later menu price changes never
    retroactively change a historical order's total."""
    item_id: int
    item_name: str
    quantity: int
    unit_price_paise: int

    @property
    def subtotal_paise(self) -> int:
        return self.quantity * self.unit_price_paise


@dataclass
class Order:
    id: str
    session_id: str
    seat_number: str
    lines: list[OrderLine]
    status: OrderStatus = OrderStatus.PLACED
    discount_paise: int = 0
    offer_code: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def subtotal_paise(self) -> int:
        return sum(line.subtotal_paise for line in self.lines)

    @property
    def total_paise(self) -> int:
        return max(0, self.subtotal_paise - self.discount_paise)

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        return new_status in _VALID_TRANSITIONS[self.status]

    def transition_to(self, new_status: OrderStatus) -> "Order":
        """Returns a new Order with the status advanced. Raises if the
        transition isn't legal — this is the single gate that protects
        the order lifecycle from being corrupted by a bad API call."""
        if not self.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                f"Cannot move order {self.id} from {self.status.value} "
                f"to {new_status.value}"
            )
        self.status = new_status
        self.updated_at = _utcnow()
        return self
