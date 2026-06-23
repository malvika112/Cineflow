"""Pydantic request/response models — the HTTP-facing shape of our data.

Deliberately separate from core/domain entities: domain entities are
plain dataclasses with no knowledge of HTTP or JSON serialisation rules.
This keeps a clean boundary — if we ever changed the API's JSON shape,
core domain logic is untouched.
"""
from pydantic import BaseModel, Field


# ── Menu ──
class MenuItemOut(BaseModel):
    id: int
    name: str
    description: str
    price_paise: int
    price_rupees: float
    category: str
    is_active: bool
    quantity_available: int
    is_sold_out: bool
    is_orderable: bool


class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    price_paise: int = Field(gt=0)
    category: str = "general"
    initial_quantity: int = Field(ge=0)


class MenuItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_paise: int | None = None
    category: str | None = None
    is_active: bool | None = None


class RestockRequest(BaseModel):
    quantity_delta: int = Field(description="Positive to add stock, e.g. 20")


class SetStockRequest(BaseModel):
    quantity: int = Field(ge=0)


# ── Session ──
class SessionCreateRequest(BaseModel):
    seat_number: str
    screen_id: str


class SessionOut(BaseModel):
    token: str
    seat_number: str
    screen_id: str


# ── Cart / Checkout ──
class CartLineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class CheckoutRequest(BaseModel):
    session_token: str
    seat_number: str
    items: list[CartLineIn]
    offer_code: str | None = None


class CartValidateRequest(BaseModel):
    session_token: str
    items: list[CartLineIn]
    offer_code: str | None = None


class CartValidateResponse(BaseModel):
    subtotal_paise: int
    discount_paise: int
    total_paise: int
    applied_offer_ids: list[str]
    rejected_lines: list[dict] = []


# ── Orders ──
class OrderLineOut(BaseModel):
    item_id: int
    item_name: str
    quantity: int
    unit_price_paise: int
    subtotal_paise: int


class OrderOut(BaseModel):
    id: str
    session_id: str
    seat_number: str
    status: str
    lines: list[OrderLineOut]
    subtotal_paise: int
    discount_paise: int
    total_paise: int
    offer_code: str | None


class OrderStatusUpdateRequest(BaseModel):
    status: str


# ── Offers ──
class OfferCreateRequest(BaseModel):
    code: str
    discount_type: str  # "flat" | "percent"
    discount_value: int
    min_order_paise: int = 0
    max_uses: int = 1000
    per_user_cap: int = 1
    valid_from: str  # ISO datetime
    valid_until: str
    stackable: bool = False


class OfferOut(BaseModel):
    id: str
    code: str
    discount_type: str
    discount_value: int
    min_order_paise: int
    max_uses: int
    per_user_cap: int
    valid_from: str
    valid_until: str
    stackable: bool


class ErrorResponse(BaseModel):
    detail: str
