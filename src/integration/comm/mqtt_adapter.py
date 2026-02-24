"""MQTT-based edge communication adapter."""
from __future__ import annotations

from typing import Callable

from smart_messaging_core import HttpConfig, MessagingClient, MessagingConfig, MqttConfig

from .base import EdgeCommAdapter


class MqttEdgeCommAdapter(EdgeCommAdapter):
    """Use MQTT subscribe for ingestion and MQTT/HTTP for phase publish."""

    def __init__(self, config, logger=None) -> None:
        self._cfg = config
        self._logger = logger
        mqtt_cfg = config.mqtt
        self._event_topic = config.edge_event_topic
        self._phase_topic = mqtt_cfg.topic
        self._publish_backend = getattr(config.phase_publish, "backend", "mqtt")
        self._client = MessagingClient(
            MessagingConfig(
                publish_backend="mqtt",
                subscribe_backend="mqtt",
                mqtt=MqttConfig(
                    host=mqtt_cfg.host,
                    port=mqtt_cfg.port,
                    qos=mqtt_cfg.qos,
                    retain=mqtt_cfg.retain,
                    client_id=mqtt_cfg.client_id,
                ),
            )
        )
        self._http_phase_client: MessagingClient | None = None
        if self._publish_backend == "http":
            phase_http = getattr(config, "phase_http", None)
            if phase_http and phase_http.base_url:
                self._http_phase_client = MessagingClient(
                    MessagingConfig(
                        publish_backend="http",
                        subscribe_backend="none",
                        http=HttpConfig(
                            base_url=phase_http.base_url,
                            timeout_seconds=phase_http.timeout_seconds,
                        ),
                    )
                )

    def start_event_ingestion(self, on_event: Callable[[dict], None]) -> None:
        self._client.subscribe(self._event_topic, on_event)

    def publish_phase(self, phase_name: str, timestamp: float) -> bool:
        payload = {"phase": phase_name, "timestamp": timestamp}
        if self._publish_backend == "http":
            if self._http_phase_client is None:
                if self._logger:
                    self._logger.warning("phase publish backend=http but PHASE_HTTP_BASE_URL not configured")
                return False
            return self._http_phase_client.publish(self._phase_topic, payload)
        return self._client.publish(self._phase_topic, payload)

    def stop(self) -> None:
        # MessagingClient does not require explicit close in current integration flow.
        return None
