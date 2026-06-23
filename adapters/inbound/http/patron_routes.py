"""
Patron-facing HTTP routes.

This is an inbound adapter — it CALLS into core/services, never the
other way around. Route handlers are intentionally thin: parse request,
call one service method, map domain exceptions to HTTP status codes,
serialise response. No business logic lives here.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends

from api.schemas import (
    MenuItemOut, SessionCreateRequest, SessionOut,
    CartValidateRequest, CartValidateResponse, CheckoutRequest,
    OrderOut, OrderLineOut,
)
from api.dependencies import get_menu_service, get_order_service, get_offer_service, get_event_bus
from core.domain.session import PatronSession
from core.services.order_service import EmptyCartError
from core.services.stock_service import InsufficientStockError

router = APIRouter(prefix="/api", tags=["patron"])

# In-memory session store. Out of scope per design doc: persistent auth.
# Sessions are lost on server restart — acceptable for a single-show context.
_sessions: dict[str, PatronSession] = {}


def _menu_item_to_out(item) -> MenuItemOut:
    return MenuItemOut(
        id=item.id, name=item.name, description=item.description,
        price_paise=item.price_paise, price_rupees=item.price_rupees(),
        category=item.category, is_active=item.is_active,
        quantity_available=item.quantity_available,
        is_sold_out=item.is_sold_out, is_orderable=item.is_orderable,
    )


def _order_to_out(order) -> OrderOut:
    lines = [
        OrderLineOut(
            item_id=l.item_id, item_name=l.item_name, quantity=l.quantity,
            unit_price_paise=l.unit_price_paise, subtotal_paise=l.subtotal_paise,
        )
        for l in order.lines
    ]
    return OrderOut(
        id=order.id, session_id=order.session_id, seat_number=order.seat_number,
        status=order.status.value, lines=lines, subtotal_paise=order.subtotal_paise,
        discount_paise=order.discount_paise, total_paise=order.total_paise,
        offer_code=order.offer_code,
    )


@router.post("/session", response_model=SessionOut)
def create_session(body: SessionCreateRequest):
    """Bind a device to a seat. No password, no account — see design doc
    assumptions for why full auth is out of scope."""
    session = PatronSession.create(seat_number=body.seat_number, screen_id=body.screen_id)
    _sessions[session.token] = session
    return SessionOut(token=session.token, seat_number=session.seat_number, screen_id=session.screen_id)


@router.get("/menu", response_model=list[MenuItemOut])
def get_menu(menu_service=Depends(get_menu_service)):
    """Patron menu view: only active items, stock-aware. Frontend polls
    this every 10s to catch sold-out transitions (see design doc 6.2)."""
    items = menu_service.list_menu(include_inactive=False)
    return [_menu_item_to_out(i) for i in items]


@router.post("/cart/validate", response_model=CartValidateResponse)
def validate_cart(
    body: CartValidateRequest,
    menu_service=Depends(get_menu_service),
    offer_service=Depends(get_offer_service),
):
    """Pure read-only preview: what would this cart cost, with offers
    applied, WITHOUT reserving any stock. Lets the patron see the total
    on the cart screen before committing to checkout."""
    subtotal = 0
    rejected = []
    for line in body.items:
        item = menu_service.get_item(line.item_id)
        if item is None:
            rejected.append({"item_id": line.item_id, "reason": "not_found"})
            continue
        if not item.is_orderable:
            rejected.append({"item_id": line.item_id, "reason": "sold_out"})
            continue
        subtotal += item.price_paise * line.quantity

    discount = 0
    applied_ids: list[str] = []
    if body.offer_code:
        result = offer_service.evaluate_cart(subtotal_paise=subtotal, session_id=body.session_token)
        discount = result.total_discount_paise
        applied_ids = result.applied_offer_ids

    return CartValidateResponse(
        subtotal_paise=subtotal,
        discount_paise=discount,
        total_paise=max(0, subtotal - discount),
        applied_offer_ids=applied_ids,
        rejected_lines=rejected,
    )


@router.post("/checkout", response_model=OrderOut)
def checkout(
    body: CheckoutRequest,
    order_service=Depends(get_order_service),
    event_bus=Depends(get_event_bus),
):
    """The hot path. Calls order_service.place_order(), which internally
    reserves stock atomically per line and rolls back on partial failure
    (see core/services/order_service.py docstring)."""
    try:
        order = order_service.place_order(
            session_id=body.session_token,
            seat_number=body.seat_number,
            cart_items=[{"item_id": l.item_id, "quantity": l.quantity} for l in body.items],
            offer_code=body.offer_code,
        )
    except EmptyCartError:
        raise HTTPException(status_code=400, detail="Cart is empty")
    except InsufficientStockError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Notify any SSE subscribers that stock changed for these items —
    # production stock-sync path; patron frontend still polls in v1.
    for line in body.items:
        event_bus.publish("stock_updates", {"item_id": line.item_id, "event": "decremented"})

    return _order_to_out(order)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, order_service=Depends(get_order_service)):
    order = order_service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_out(order)
