"""Stub repository for zone state tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict


@dataclass
class ZoneStateRepository:
    """Stores zone state update markers (placeholder for PostgreSQL)."""

    _updated: Dict[date, bool] = field(default_factory=dict)

    def is_zone_state_updated(self, target_date: date) -> bool:
        return self._updated.get(target_date, False)

    def mark_zone_state_updated(self, target_date: date) -> None:
        self._updated[target_date] = True
