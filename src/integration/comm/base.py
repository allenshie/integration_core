"""Base protocol for edge communication adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class EdgeCommAdapter(ABC):
    """Unifies edge-event ingestion and phase publishing transport."""

    @abstractmethod
    def start_event_ingestion(self, on_event: Callable[[dict], None]) -> None:
        """Start receiving edge events and forward them to `on_event`."""

    @abstractmethod
    def publish_phase(self, phase_name: str, timestamp: float) -> bool:
        """Publish current phase to edge side."""

    @abstractmethod
    def stop(self) -> None:
        """Release transport resources if needed."""
