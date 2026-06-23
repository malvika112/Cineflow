"""
Stock service tests — the most important tests in the suite, since the
assignment explicitly calls out oversell as THE hard problem to solve.

test_concurrent_oversell uses real threads against the real SQLite
adapter (not the fake) deliberately — the in-memory fake's dict
operations are already atomic under Python's GIL for simple cases,
so testing concurrency against it wouldn't actually prove anything
about the production code path. The SQLite adapter test is the one
that matters.
"""
import os
import sqlite3
import threading

import pytest

from core.services.stock_service import StockService, InsufficientStockError
from adapters.outbound.sqlite_stock_repo import SQLiteStockRepository
from tests.unit.fakes import FakeStockRepo

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "db", "schema.sql")


@pytest.fixture
def stock_service():
    repo = FakeStockRepo()
    return StockService(repo), repo


def test_reserve_success(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 5)
    service.reserve(1, 3)
    assert repo.get_quantity(1) == 2


def test_reserve_exact_remaining_stock(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 5)
    service.reserve(1, 5)
    assert repo.get_quantity(1) == 0


def test_reserve_oversell_raises(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 0)
    with pytest.raises(InsufficientStockError):
        service.reserve(1, 1)
    assert repo.get_quantity(1) == 0, "stock must be unchanged after a failed reservation"


def test_reserve_more_than_available_raises(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 3)
    with pytest.raises(InsufficientStockError) as exc_info:
        service.reserve(1, 5)
    assert exc_info.value.requested == 5
    assert exc_info.value.available == 3
    assert repo.get_quantity(1) == 3, "partial decrement must never happen"


def test_release_restores_stock(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 5)
    service.reserve(1, 2)
    assert repo.get_quantity(1) == 3
    service.release(1, 2)
    assert repo.get_quantity(1) == 5


def test_reserve_rejects_non_positive_qty(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 5)
    with pytest.raises(ValueError):
        service.reserve(1, 0)
    with pytest.raises(ValueError):
        service.reserve(1, -1)


def test_restock_increases_quantity(stock_service):
    service, repo = stock_service
    repo.set_quantity(1, 5)
    service.restock(1, 10)
    assert repo.get_quantity(1) == 15


# ── The critical concurrency test — real SQLite, real threads ──

@pytest.fixture
def sqlite_repo(tmp_path):
    db_path = str(tmp_path / "oversell_test.db")
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.execute("INSERT INTO menu_items (id, name, price_paise) VALUES (1, 'Last Popcorn', 25000)")
    conn.execute("INSERT INTO stock (item_id, quantity) VALUES (1, 1)")  # exactly 1 unit
    conn.commit()
    conn.close()
    return SQLiteStockRepository(db_path)


def test_concurrent_oversell_exactly_one_winner(sqlite_repo):
    """THE test. 50 threads simultaneously try to buy the last unit of
    stock. Exactly one must succeed; the other 49 must be cleanly
    rejected with no partial decrements and no negative stock."""
    NUM_THREADS = 50
    results = []
    results_lock = threading.Lock()

    def try_buy():
        success = sqlite_repo.decrement_if_available(item_id=1, qty=1)
        with results_lock:
            results.append(success)

    threads = [threading.Thread(target=try_buy) for _ in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(results)
    assert successes == 1, f"Expected exactly 1 success, got {successes} (OVERSELL BUG)"
    assert sqlite_repo.get_quantity(1) == 0
    assert sqlite_repo.get_quantity(1) >= 0, "stock must never go negative"


def test_concurrent_oversell_with_higher_stock(sqlite_repo):
    """Same test but with 5 units of stock and 50 threads — exactly 5
    should succeed, proving the guard works at non-trivial quantities too,
    not just the qty=1 edge case."""
    sqlite_repo.set_quantity(1, 5)

    NUM_THREADS = 50
    results = []
    results_lock = threading.Lock()

    def try_buy():
        success = sqlite_repo.decrement_if_available(item_id=1, qty=1)
        with results_lock:
            results.append(success)

    threads = [threading.Thread(target=try_buy) for _ in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(results)
    assert successes == 5
    assert sqlite_repo.get_quantity(1) == 0


def test_sqlite_get_quantity_reflects_decrement(sqlite_repo):
    assert sqlite_repo.get_quantity(1) == 1
    sqlite_repo.decrement_if_available(1, 1)
    assert sqlite_repo.get_quantity(1) == 0


def test_sqlite_increment_restores_stock(sqlite_repo):
    sqlite_repo.decrement_if_available(1, 1)
    sqlite_repo.increment(1, 1)
    assert sqlite_repo.get_quantity(1) == 1
