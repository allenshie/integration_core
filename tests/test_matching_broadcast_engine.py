from __future__ import annotations

import logging
from types import SimpleNamespace

from integration.pipeline.tasks.nodes.matching_broadcast.constants import MATCHING_BROADCAST_ROUTE
from integration.pipeline.tasks.nodes.matching_broadcast.engine import DefaultMatchingBroadcastEngine


class DummyMessagingClient:
    def __init__(self, publish_result: bool = True) -> None:
        self.publish_result = publish_result
        self.calls: list[tuple[str, dict[str, object]]] = []

    def publish(self, route: str, payload: dict[str, object]) -> bool:
        self.calls.append((route, payload))
        return self.publish_result


class DummyContext:
    def __init__(self, enabled: bool, tracked_objects: list[dict[str, object]], publish_result: bool = True) -> None:
        self.config = SimpleNamespace(matching_broadcast=SimpleNamespace(enabled=enabled))
        self.logger = logging.getLogger("matching-broadcast-engine-test")
        self._resources = {
            "mc_mot_tracked": tracked_objects,
            "messaging_client": DummyMessagingClient(publish_result=publish_result),
        }

    def get_resource(self, key: str):
        return self._resources.get(key)


def test_default_matching_broadcast_engine_skips_when_disabled() -> None:
    context = DummyContext(
        enabled=False,
        tracked_objects=[{"camera_id": "cam01", "local_id": 1, "global_id": 99, "class_name": "car"}],
    )

    result = DefaultMatchingBroadcastEngine().broadcast(context.get_resource("mc_mot_tracked"), context)

    assert result.skipped == 1
    assert result.reason == "disabled"
    assert context.get_resource("messaging_client").calls == []


def test_default_matching_broadcast_engine_publishes_grouped_payload() -> None:
    context = DummyContext(
        enabled=True,
        tracked_objects=[
            {"camera_id": "cam02", "local_id": 4, "global_id": 30, "class_name": "truck"},
            {"camera_id": "cam01", "local_id": 1, "global_id": 10, "class_name": "car"},
            {"camera_id": "cam01", "local_id": 2, "global_id": 11, "class_name": "bus"},
        ],
    )

    result = DefaultMatchingBroadcastEngine().broadcast(context.get_resource("mc_mot_tracked"), context)

    assert result.dispatched == 1
    assert result.message_payload is not None
    calls = context.get_resource("messaging_client").calls
    assert len(calls) == 1
    route, payload = calls[0]
    assert route == MATCHING_BROADCAST_ROUTE
    assert payload["message_type"] == "matching_result"
    assert payload["schema_version"] == 1
    assert list(payload["camera_matches"].keys()) == ["cam01", "cam02"]
    assert payload["camera_matches"]["cam01"][0]["local_id"] == 1
    assert payload["camera_matches"]["cam01"][1]["global_id"] == 11
    assert payload["camera_matches"]["cam02"][0]["class_name"] == "truck"
