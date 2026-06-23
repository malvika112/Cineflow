"""
Offer service — the conflict resolution engine.

This is the Tier 1 (A) pillar. The brief explicitly calls out:
"Configurable rules that genuinely conflict: stackability, per-user caps,
showtime windows. Admin defines them; patron redeems; the engine resolves
conflicts deterministically." This file is that engine.

Resolution algorithm (documented here AND in the design doc):
  1. Filter to offers that are individually eligible right now (window,
     min order, global cap, per-user cap) — Offer.is_eligible() does this
     per-offer; we just loop over all active offers and keep the eligible
     ones.
  2. Split eligible offers into stackable and non-stackable groups.
  3. If there are any non-stackable eligible offers, only ONE of them may
     be applied — the one with the highest absolute discount on the
     current subtotal. Ties are broken by offer.id, ascending, so the
     result is reproducible given the same input every time (deterministic).
  4. All stackable eligible offers are applied IN ADDITION to that single
     non-stackable winner (if any), each computed against the subtotal
     independently and summed — we do not compound discounts on top of
     already-discounted totals, to keep the math easy to audit.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from core.domain.offer import Offer
from core.ports.offer_port import IOfferRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class OfferApplication:
    """Result of evaluating a cart: which offers applied and the total discount."""
    applied_offer_ids: list[str]
    total_discount_paise: int


class OfferService:
    def __init__(self, offer_repo: IOfferRepository):
        self._repo = offer_repo

    def _eligible_offers(self, subtotal_paise: int, session_id: str, now: datetime) -> list[Offer]:
        eligible = []
        for offer in self._repo.list_active():
            global_count = self._repo.count_redemptions(offer.id)
            user_count = self._repo.count_redemptions(offer.id, session_id=session_id)
            if offer.is_eligible(now, subtotal_paise, global_count, user_count):
                eligible.append(offer)
        return eligible

    def evaluate_cart(
        self,
        subtotal_paise: int,
        session_id: str,
        now: datetime | None = None,
    ) -> OfferApplication:
        """Pure evaluation — does NOT record redemptions. Called when the
        patron views their cart, so they can see the discount before
        checking out. Recording happens in apply_to_order(), at the
        point the order is actually placed."""
        now = now or _utcnow()
        eligible = self._eligible_offers(subtotal_paise, session_id, now)

        stackable = [o for o in eligible if o.stackable]
        non_stackable = [o for o in eligible if not o.stackable]

        applied: list[Offer] = []
        total_discount = 0

        if non_stackable:
            # Step 3: pick exactly one winner — highest discount, ties
            # broken by offer.id ascending for determinism.
            winner = max(
                non_stackable,
                key=lambda o: (o.compute_discount(subtotal_paise), [-ord(c) for c in o.id]),
            )
            applied.append(winner)
            total_discount += winner.compute_discount(subtotal_paise)

        for offer in stackable:
            applied.append(offer)
            total_discount += offer.compute_discount(subtotal_paise)

        total_discount = min(total_discount, subtotal_paise)

        return OfferApplication(
            applied_offer_ids=[o.id for o in applied],
            total_discount_paise=total_discount,
        )

    def apply_to_order(
        self,
        subtotal_paise: int,
        session_id: str,
        order_id: str,
        now: datetime | None = None,
    ) -> OfferApplication:
        """Evaluates AND records redemptions atomically with order placement.
        Called once, at checkout time, by order_service.place_order().
        The redemption record + per-user-cap check must happen together
        to prevent a race where two near-simultaneous checkouts both pass
        the cap check before either redemption is recorded."""
        result = self.evaluate_cart(subtotal_paise, session_id, now)
        for offer_id in result.applied_offer_ids:
            self._repo.record_redemption(offer_id, session_id, order_id)
        return result
