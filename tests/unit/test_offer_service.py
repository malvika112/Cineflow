"""
Offer service tests — the conflict resolution engine (Tier 1, pillar A).

Covers exactly what the brief calls out: stackability, per-user caps,
showtime windows, and deterministic conflict resolution.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.domain.offer import Offer, DiscountType
from core.services.offer_service import OfferService
from tests.unit.fakes import FakeOfferRepo


def make_offer(id, code, discount_type, discount_value, stackable,
                min_order=0, max_uses=1000, per_user_cap=10,
                hours_from=-1, hours_until=1):
    now = datetime.now(timezone.utc)
    return Offer(
        id=id, code=code, discount_type=discount_type, discount_value=discount_value,
        min_order_paise=min_order, max_uses=max_uses, per_user_cap=per_user_cap,
        valid_from=now + timedelta(hours=hours_from),
        valid_until=now + timedelta(hours=hours_until),
        stackable=stackable,
    )


@pytest.fixture
def offer_service():
    repo = FakeOfferRepo()
    return OfferService(repo), repo


def test_no_offers_no_discount(offer_service):
    service, repo = offer_service
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s1")
    assert result.total_discount_paise == 0
    assert result.applied_offer_ids == []


def test_single_eligible_offer_applied(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "SAVE10", DiscountType.PERCENT, 10, stackable=False))
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s1")
    assert result.applied_offer_ids == ["o1"]
    assert result.total_discount_paise == 5000


def test_expired_offer_not_applied(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer(
        "o1", "EXPIRED", DiscountType.PERCENT, 10, stackable=False,
        hours_from=-5, hours_until=-1,  # entirely in the past
    ))
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s1")
    assert result.applied_offer_ids == []


def test_future_offer_not_applied(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer(
        "o1", "FUTURE", DiscountType.PERCENT, 10, stackable=False,
        hours_from=1, hours_until=5,  # entirely in the future
    ))
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s1")
    assert result.applied_offer_ids == []


def test_below_minimum_order_not_applied(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "BIG50", DiscountType.FLAT, 5000, stackable=False, min_order=100000))
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s1")  # below the 1000-rupee minimum
    assert result.applied_offer_ids == []


def test_per_user_cap_enforced(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "ONCE", DiscountType.PERCENT, 10, stackable=False, per_user_cap=1))

    # First use succeeds
    result1 = service.apply_to_order(subtotal_paise=50000, session_id="s1", order_id="ord1")
    assert result1.applied_offer_ids == ["o1"]

    # Second use by the SAME session should be rejected by the cap
    result2 = service.evaluate_cart(subtotal_paise=50000, session_id="s1")
    assert result2.applied_offer_ids == []

    # A DIFFERENT session should still be able to use it
    result3 = service.evaluate_cart(subtotal_paise=50000, session_id="s2")
    assert result3.applied_offer_ids == ["o1"]


def test_global_max_uses_enforced(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer(
        "o1", "LIMITED", DiscountType.PERCENT, 10, stackable=False,
        max_uses=2, per_user_cap=10,
    ))
    service.apply_to_order(subtotal_paise=50000, session_id="s1", order_id="ord1")
    service.apply_to_order(subtotal_paise=50000, session_id="s2", order_id="ord2")

    # Third redemption by a third session should fail — global cap reached
    result = service.evaluate_cart(subtotal_paise=50000, session_id="s3")
    assert result.applied_offer_ids == []


def test_non_stackable_conflict_highest_discount_wins(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "SMALL5", DiscountType.PERCENT, 5, stackable=False))
    repo.create_offer(make_offer("o2", "BIG20", DiscountType.PERCENT, 20, stackable=False))

    result = service.evaluate_cart(subtotal_paise=100000, session_id="s1")
    assert result.applied_offer_ids == ["o2"], "the 20% offer should win over the 5% offer"
    assert result.total_discount_paise == 20000


def test_deterministic_tiebreak_on_equal_discount(offer_service):
    """Two non-stackable offers with IDENTICAL discount value — the
    result must be reproducible (same winner every time), not random."""
    service, repo = offer_service
    repo.create_offer(make_offer("zzz", "OFFERZ", DiscountType.PERCENT, 10, stackable=False))
    repo.create_offer(make_offer("aaa", "OFFERA", DiscountType.PERCENT, 10, stackable=False))

    results = set()
    for _ in range(10):
        repo2 = FakeOfferRepo()
        repo2.create_offer(make_offer("zzz", "OFFERZ", DiscountType.PERCENT, 10, stackable=False))
        repo2.create_offer(make_offer("aaa", "OFFERA", DiscountType.PERCENT, 10, stackable=False))
        svc2 = OfferService(repo2)
        r = svc2.evaluate_cart(subtotal_paise=100000, session_id="s1")
        results.add(tuple(r.applied_offer_ids))

    assert len(results) == 1, f"Tiebreak must be deterministic, got varying results: {results}"


def test_stackable_offers_combine(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "STACK5", DiscountType.PERCENT, 5, stackable=True))
    repo.create_offer(make_offer("o2", "STACK3", DiscountType.PERCENT, 3, stackable=True))

    result = service.evaluate_cart(subtotal_paise=100000, session_id="s1")
    assert set(result.applied_offer_ids) == {"o1", "o2"}
    assert result.total_discount_paise == 8000  # 5% + 3% of 100000


def test_stackable_plus_non_stackable_combine(offer_service):
    """One non-stackable winner + all eligible stackable offers apply together."""
    service, repo = offer_service
    repo.create_offer(make_offer("ns1", "BIGWIN", DiscountType.PERCENT, 15, stackable=False))
    repo.create_offer(make_offer("ns2", "SMALLLOSE", DiscountType.PERCENT, 5, stackable=False))
    repo.create_offer(make_offer("s1off", "EXTRA", DiscountType.PERCENT, 2, stackable=True))

    result = service.evaluate_cart(subtotal_paise=100000, session_id="s1")
    assert "ns1" in result.applied_offer_ids   # non-stackable winner
    assert "ns2" not in result.applied_offer_ids  # non-stackable loser excluded
    assert "s1off" in result.applied_offer_ids   # stackable always included
    assert result.total_discount_paise == 17000  # 15% + 2% of 100000


def test_discount_never_exceeds_subtotal(offer_service):
    """Sanity guard: even with multiple large stackable discounts, the
    total discount should never make the order go negative."""
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "HALF", DiscountType.PERCENT, 60, stackable=True))
    repo.create_offer(make_offer("o2", "HALF2", DiscountType.PERCENT, 60, stackable=True))

    result = service.evaluate_cart(subtotal_paise=10000, session_id="s1")
    assert result.total_discount_paise <= 10000


def test_apply_to_order_records_redemption(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "REC", DiscountType.PERCENT, 10, stackable=False))
    service.apply_to_order(subtotal_paise=50000, session_id="s1", order_id="ord1")
    assert repo.count_redemptions("o1", session_id="s1") == 1


def test_flat_discount_type(offer_service):
    service, repo = offer_service
    repo.create_offer(make_offer("o1", "FLAT50", DiscountType.FLAT, 5000, stackable=False))
    result = service.evaluate_cart(subtotal_paise=100000, session_id="s1")
    assert result.total_discount_paise == 5000
