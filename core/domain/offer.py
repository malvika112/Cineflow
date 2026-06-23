"""
Offer / promotion domain entities.

This is the most rule-heavy part of the system: offers can be stackable
or not, capped per user, and time-windowed. The conflict resolution logic
(when two non-stackable offers both apply) lives in offer_service.py —
this file only defines what an Offer IS and how to check if it's valid
for a given moment, not how to RESOLVE conflicts between several.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DiscountType(str, Enum):
    FLAT = "flat"        # discount_value is paise, subtracted directly
    PERCENT = "percent"  # discount_value is 0-100, percentage of subtotal


@dataclass(frozen=True)
class Offer:
    id: str
    code: str
    discount_type: DiscountType
    discount_value: int          # paise if FLAT, 0-100 if PERCENT
    min_order_paise: int
    max_uses: int                # total redemptions allowed across all users
    per_user_cap: int            # redemptions allowed per session
    valid_from: datetime
    valid_until: datetime
    stackable: bool

    def is_within_window(self, now: datetime) -> bool:
        return self.valid_from <= now <= self.valid_until

    def meets_minimum(self, subtotal_paise: int) -> bool:
        return subtotal_paise >= self.min_order_paise

    def compute_discount(self, subtotal_paise: int) -> int:
        """Returns the discount amount in paise. Never returns more than
        the subtotal itself — a discount can't make a cart negative."""
        if self.discount_type == DiscountType.FLAT:
            raw = self.discount_value
        else:
            raw = (subtotal_paise * self.discount_value) // 100
        return min(raw, subtotal_paise)

    def is_eligible(
        self,
        now: datetime,
        subtotal_paise: int,
        global_redemptions: int,
        user_redemptions: int,
    ) -> bool:
        """A single offer is eligible if every individual rule passes.
        Conflict resolution BETWEEN multiple eligible offers happens one
        level up, in offer_service.resolve_conflicts() — this method only
        answers 'is this one offer usable right now, by this user'."""
        return (
            self.is_within_window(now)
            and self.meets_minimum(subtotal_paise)
            and global_redemptions < self.max_uses
            and user_redemptions < self.per_user_cap
        )
