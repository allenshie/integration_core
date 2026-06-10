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

        # 未啟用時直接回傳 skip，保留原有 pipeline 行為。
        if not enabled:
            context.logger.debug("matching broadcast disabled, skip %d tracked objects", len(tracked_list))
            return MatchingBroadcastResult(
                skipped=1,
                reason="disabled",
                task_payload={"reason": "disabled", "tracked": len(tracked_list)},
            )

        # 沒有可廣播的追蹤物件時，不送出空 payload。
        if not tracked_list:
            context.logger.debug("matching broadcast skipped: no tracked objects")
            return MatchingBroadcastResult(
                skipped=1,
                reason="no_tracked_objects",
                task_payload={"reason": "no_tracked_objects"},
            )

        # 將 local/global 對照整理成單一廣播 payload。
        payload = MatchingBroadcastPayload.from_tracked_objects(tracked_list).to_dict()
        # 若過濾後沒有任何 camera 可用資料，視為本輪無有效結果。
        if not payload.get("camera_matches"):
            context.logger.debug("matching broadcast skipped: no valid camera matches")
            return MatchingBroadcastResult(
                skipped=1,
                reason="no_valid_tracks",
                task_payload={"reason": "no_valid_tracks"},
            )

        # 取得 messaging client，由上層統一負責 route 與 backend。
        messaging = context.get_resource("messaging_client")
        if messaging is None:
            context.logger.warning("matching broadcast skipped: messaging_client not ready")
            return MatchingBroadcastResult(
                skipped=1,
                reason="messaging_client_not_ready",
                task_payload={"reason": "messaging_client_not_ready"},
                message_payload=payload,
            )

        # publish 失敗時回傳 failed，讓 task 可以統計與記錄。
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

        # backend 明確拒絕送出時，也視為失敗。
        if not published:
            context.logger.warning("matching broadcast failed: backend rejected publish")
            return MatchingBroadcastResult(
                failed=1,
                reason="publish_rejected",
                task_payload={"reason": "publish_rejected"},
                message_payload=payload,
            )

        # 成功送出後，只回報本輪統計。
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
