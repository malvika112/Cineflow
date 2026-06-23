"""
Admin-facing HTTP routes.

All routes here require the X-Admin-Token header to match settings.ADMIN_TOKEN.
This is the single hardcoded admin auth mentioned in the design doc
assumptions — full RBAC is explicitly out of scope.
"""
from fastapi import APIRouter, HTTPException, Depends, Header

from api.schemas import (
    MenuItemOut, MenuItemCreate, MenuItemUpdate, RestockRequest, SetStockRequest,
    OrderOut, OrderLineOut, OrderStatusUpdateRequest,
    OfferCreateRequest, OfferOut,
)
from api.dependencies import get_menu_service, get_stock_service, get_order_service, get_offer_service
from core.domain.order import OrderStatus, InvalidStatusTransitionError
from core.domain.offer import Offer, DiscountType
from config import settings
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_token: str = Header(default="")):
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


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


# ── Menu management ──
@router.get("/menu", response_model=list[MenuItemOut], dependencies=[Depends(require_admin)])
def list_all_menu_items(menu_service=Depends(get_menu_service)):
    """Includes inactive items, unlike the patron-facing /api/menu."""
    items = menu_service.list_menu(include_inactive=True)
    return [_menu_item_to_out(i) for i in items]


@router.post("/menu", response_model=MenuItemOut, dependencies=[Depends(require_admin)])
def create_menu_item(body: MenuItemCreate, menu_service=Depends(get_menu_service)):
    item = menu_service.create_item(
        name=body.name, description=body.description, price_paise=body.price_paise,
        category=body.category, initial_quantity=body.initial_quantity,
    )
    return _menu_item_to_out(item)


@router.patch("/menu/{item_id}", response_model=MenuItemOut, dependencies=[Depends(require_admin)])
def update_menu_item(item_id: int, body: MenuItemUpdate, menu_service=Depends(get_menu_service)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    item = menu_service.update_item(item_id, **fields)
    return _menu_item_to_out(item)


@router.post("/menu/{item_id}/restock", response_model=MenuItemOut, dependencies=[Depends(require_admin)])
def restock_item(
    item_id: int, body: RestockRequest,
    stock_service=Depends(get_stock_service), menu_service=Depends(get_menu_service),
):
    """Kitchen made more popcorn — add to existing stock."""
    if body.quantity_delta > 0:
        stock_service.restock(item_id, body.quantity_delta)
    elif body.quantity_delta < 0:
        raise HTTPException(status_code=400, detail="Use /set-stock to reduce stock directly")
    item = menu_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _menu_item_to_out(item)


@router.post("/menu/{item_id}/set-stock", response_model=MenuItemOut, dependencies=[Depends(require_admin)])
def set_stock(
    item_id: int, body: SetStockRequest,
    stock_service=Depends(get_stock_service), menu_service=Depends(get_menu_service),
):
    """Hard-set stock — e.g. correcting a count after physical inventory."""
    stock_service.set_quantity(item_id, body.quantity)
    item = menu_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _menu_item_to_out(item)


# ── Order dashboard ──
@router.get("/orders", response_model=list[OrderOut], dependencies=[Depends(require_admin)])
def list_orders(status: str | None = None, order_service=Depends(get_order_service)):
    status_enum = OrderStatus(status) if status else None
    orders = order_service.list_orders(status_enum)
    return [_order_to_out(o) for o in orders]


@router.patch("/orders/{order_id}/status", response_model=OrderOut, dependencies=[Depends(require_admin)])
def advance_order_status(
    order_id: str, body: OrderStatusUpdateRequest, order_service=Depends(get_order_service),
):
    try:
        new_status = OrderStatus(body.status)
        order = order_service.update_status(order_id, new_status)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _order_to_out(order)


# ── Offers ──
@router.get("/offers", response_model=list[OfferOut], dependencies=[Depends(require_admin)])
def list_offers(offer_service=Depends(get_offer_service)):
    offers = offer_service._repo.list_active()
    return [
        OfferOut(
            id=o.id, code=o.code, discount_type=o.discount_type.value,
            discount_value=o.discount_value, min_order_paise=o.min_order_paise,
            max_uses=o.max_uses, per_user_cap=o.per_user_cap,
            valid_from=o.valid_from.isoformat(), valid_until=o.valid_until.isoformat(),
            stackable=o.stackable,
        )
        for o in offers
    ]


@router.post("/offers", response_model=OfferOut, dependencies=[Depends(require_admin)])
def create_offer(body: OfferCreateRequest, offer_service=Depends(get_offer_service)):
    import uuid
    offer = Offer(
        id=str(uuid.uuid4()),
        code=body.code,
        discount_type=DiscountType(body.discount_type),
        discount_value=body.discount_value,
        min_order_paise=body.min_order_paise,
        max_uses=body.max_uses,
        per_user_cap=body.per_user_cap,
        valid_from=datetime.fromisoformat(body.valid_from),
        valid_until=datetime.fromisoformat(body.valid_until),
        stackable=body.stackable,
    )
    created = offer_service._repo.create_offer(offer)
    return OfferOut(
        id=created.id, code=created.code, discount_type=created.discount_type.value,
        discount_value=created.discount_value, min_order_paise=created.min_order_paise,
        max_uses=created.max_uses, per_user_cap=created.per_user_cap,
        valid_from=created.valid_from.isoformat(), valid_until=created.valid_until.isoformat(),
        stackable=created.stackable,
    )
