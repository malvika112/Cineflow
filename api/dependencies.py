"""
Dependency injection — the ONLY file in the codebase that knows both
the ports AND the concrete adapters that implement them. Everywhere
else, code depends on the abstract port interfaces.

This is the "wiring" hexagonal architecture talks about: swap
SQLiteStockRepository for a future PostgresStockRepository here, and
nothing in core/ or the route handlers needs to change.
"""
from functools import lru_cache

from adapters.outbound.sqlite_stock_repo import SQLiteStockRepository
from adapters.outbound.sqlite_menu_repo import SQLiteMenuRepository
from adapters.outbound.sqlite_order_repo import SQLiteOrderRepository
from adapters.outbound.sqlite_offer_repo import SQLiteOfferRepository
from adapters.outbound.sse_event_bus import SSEEventBus

from core.services.stock_service import StockService
from core.services.menu_service import MenuService
from core.services.order_service import OrderService
from core.services.offer_service import OfferService

from config import settings


@lru_cache
def get_stock_repo() -> SQLiteStockRepository:
    return SQLiteStockRepository(settings.DB_PATH)


@lru_cache
def get_menu_repo() -> SQLiteMenuRepository:
    return SQLiteMenuRepository(settings.DB_PATH)


@lru_cache
def get_order_repo() -> SQLiteOrderRepository:
    return SQLiteOrderRepository(settings.DB_PATH)


@lru_cache
def get_offer_repo() -> SQLiteOfferRepository:
    return SQLiteOfferRepository(settings.DB_PATH)


@lru_cache
def get_event_bus() -> SSEEventBus:
    return SSEEventBus()


@lru_cache
def get_stock_service() -> StockService:
    return StockService(get_stock_repo())


@lru_cache
def get_menu_service() -> MenuService:
    return MenuService(get_menu_repo(), get_stock_repo())


@lru_cache
def get_offer_service() -> OfferService:
    return OfferService(get_offer_repo())


@lru_cache
def get_order_service() -> OrderService:
    return OrderService(
        get_order_repo(),
        get_stock_service(),
        get_menu_service(),
        get_offer_service(),
    )
