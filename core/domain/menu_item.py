"""
Menu domain entities.

Pure Python — no FastAPI, no SQL, no I/O. This module only knows about
the *rules* of a menu item: what makes it valid, what makes it sold out.
Everything here can be unit tested without a database or a web server.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    """A single sellable item on the menu.

    price_paise is an integer (1 rupee = 100 paise) to avoid floating
    point rounding errors in money math.
    """
    id: int
    name: str
    description: str
    price_paise: int
    category: str
    is_active: bool
    quantity_available: int

    def __post_init__(self):
        if self.price_paise < 0:
            raise ValueError("price_paise cannot be negative")
        if self.quantity_available < 0:
            raise ValueError("quantity_available cannot be negative")

    @property
    def is_sold_out(self) -> bool:
        """An item is sold out if there is no stock left, regardless of
        whether an admin has also deactivated it."""
        return self.quantity_available <= 0

    @property
    def is_orderable(self) -> bool:
        """The single source of truth for 'can a patron buy this right now'.
        Used by both the API response and any internal validation —
        never duplicate this check elsewhere."""
        return self.is_active and not self.is_sold_out

    def price_rupees(self) -> float:
        """Convenience for display only. Never use this for money math —
        always compute totals in paise and convert at the very end."""
        return self.price_paise / 100
