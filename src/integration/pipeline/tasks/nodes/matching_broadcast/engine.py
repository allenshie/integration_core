"""Matching result broadcast engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from smart_workflow import TaskContext

from .constants import MATCHING_BROADCAST_ROUTE
from .schema import MatchingBroadcastPayload


@dataclass(slots=True)
class MatchingBroadcastResult:
    """Summary returned by matching broadcast engines."""

    dispatched: int = 0
    skipped: int = 0
    failed: int = 0
    task_payload: dict[str, Any] | None = None
    message_payload: dict[str, Any] | None = None
    reason: str | None = None


class BaseMatchingBroadcastEngine(ABC):
    """Base interface for matching result broadcast engines."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def broadcast(
        self,
        tracked_objects: Iterable[Mapping[str, Any]],
        context: TaskContext,
    ) -> MatchingBroadcastResult:
        """Build and publish matching result payloads."""


class DefaultMatchingBroadcastEngine(BaseMatchingBroadcastEngine):
    """Fallback engine that publishes grouped matching snapshots."""

    def broadcast(
        self,
        tracked_objects: Iterable[Mapping[str, Any]],
        context: TaskContext,
    ) -> MatchingBroadcastResult:
        tracked_list = list(tracked_objects)
        broadcast_cfg = getattr(context.config, "matching_broadcast", None)
        enabled = bool(getattr(broadcast_cfg, "enabled", False)) if broadcast_cfg is not None else False

        if not enabled:
            context.logger.debug("matching broadcast disabled, skip %d tracked objects", len(tracked_list))
            return MatchingBroadcastResult(
                skipped=1,
                reason="disabled",
                task_payload={"reason": "disabled", "tracked": len(tracked_list)},
            )

        if not tracked_list:
            context.logger.debug("matching broadcast skipped: no tracked objects")
            return MatchingBroadcastResult(
                skipped=1,
                reason="no_tracked_objects",
                task_payload={"reason": "no_tracked_objects"},
            )

        payload = MatchingBroadcastPayload.from_tracked_objects(tracked_list).to_dict()
        if not payload.get("camera_matches"):
            context.logger.debug("matching broadcast skipped: no valid camera matches")
            return MatchingBroadcastResult(
                skipped=1,
                reason="no_valid_tracks",
                task_payload={"reason": "no_valid_tracks"},
            )

        messaging = context.get_resource("messaging_client")
        if messaging is None:
            context.logger.warning("matching broadcast skipped: messaging_client not ready")
            return MatchingBroadcastResult(
                skipped=1,
                reason="messaging_client_not_ready",
                task_payload={"reason": "messaging_client_not_ready"},
                message_payload=payload,
            )

        try:
            published = messaging.publish(MATCHING_BROADCAST_ROUTE, payload)
        except Exception as exc:  # pylint: disable=broad-except
            context.logger.warning("matching broadcast failed: %s", exc)
            return MatchingBroadcastResult(
                failed=1,
                reason="publish_exception",
                task_payload={"reason": "publish_exception", "error": str(exc)},
                message_payload=payload,
            )

        if not published:
            context.logger.warning("matching broadcast failed: backend rejected publish")
            return MatchingBroadcastResult(
                failed=1,
                reason="publish_rejected",
                task_payload={"reason": "publish_rejected"},
                message_payload=payload,
            )

        context.logger.debug(
            "matching broadcast completed: cameras=%d tracked=%d",
            len(payload.get("camera_matches") or {}),
            len(tracked_list),
        )
        return MatchingBroadcastResult(
            dispatched=1,
            task_payload={
                "dispatched": 1,
                "cameras": len(payload.get("camera_matches") or {}),
                "tracked": len(tracked_list),
            },
            message_payload=payload,
        )
