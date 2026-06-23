"""Offer repository port."""
from abc import ABC, abstractmethod
from core.domain.offer import Offer


class IOfferRepository(ABC):

    @abstractmethod
    def list_active(self) -> list[Offer]:
        """All offers regardless of time window — offer_service filters
        by valid_from/valid_until itself, since that's a domain rule,
        not a query concern."""
        raise NotImplementedError

    @abstractmethod
    def get_by_code(self, code: str) -> Offer | None:
        raise NotImplementedError

    @abstractmethod
    def count_redemptions(self, offer_id: str, session_id: str | None = None) -> int:
        """If session_id is given, returns that user's redemption count
        (for per_user_cap). If None, returns the global count (for max_uses)."""
        raise NotImplementedError

    @abstractmethod
    def record_redemption(self, offer_id: str, session_id: str, order_id: str) -> None:
        """Must be called inside the same transaction as order creation —
        see offer_service.apply_to_order() and sqlite_offer_repo's
        implementation for how the atomicity is guaranteed."""
        raise NotImplementedError

    @abstractmethod
    def create_offer(self, offer: Offer) -> Offer:
        raise NotImplementedError
