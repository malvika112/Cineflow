"""Event bus port — used to push stock updates to connected patrons.

v1 ships with an SSE adapter implementing this, but the patron frontend
uses polling and isn't wired to it yet (see design doc section 6.2).
The port exists so the upgrade is a pure adapter swap with zero changes
to stock_service.
"""
from abc import ABC, abstractmethod
from typing import Any


class IEventBus(ABC):

    @abstractmethod
    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, topic: str):
        """Returns an async generator/iterator of payloads for that topic.
        Used by the SSE route handler."""
        raise NotImplementedError
