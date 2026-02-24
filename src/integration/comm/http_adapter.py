"""HTTP-based edge communication adapter."""
from __future__ import annotations

import threading
from typing import Callable

from smart_messaging_core import HttpConfig, MessagingClient, MessagingConfig, MqttConfig

from integration.api.http_server import start_edge_event_server

from .base import EdgeCommAdapter


class _CallbackEventStore:
    """Bridge http_server store contract to callback-based adapter API."""

    def __init__(self, on_event: Callable[[dict], None]) -> None:
        self._on_event = on_event

    def add_event(self, event: dict) -> None:
        self._on_event(event)


class HttpEdgeCommAdapter(EdgeCommAdapter):
    """Use HTTP ingestion and HTTP/MQTT phase publish."""

    def __init__(self, config, logger=None) -> None:
        self._cfg = config
        self._logger = logger
        self._phase_topic = config.mqtt.topic
        self._publish_backend = getattr(config.phase_publish, "backend", "http")
        self._server = None
        self._server_thread: threading.Thread | None = None
        self._http_phase_client: MessagingClient | None = None
        self._mqtt_phase_client: MessagingClient | None = None

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
        elif self._publish_backend == "mqtt":
            mqtt_cfg = config.mqtt
            self._mqtt_phase_client = MessagingClient(
                MessagingConfig(
                    publish_backend="mqtt",
                    subscribe_backend="none",
                    mqtt=MqttConfig(
                        host=mqtt_cfg.host,
                        port=mqtt_cfg.port,
                        qos=mqtt_cfg.qos,
                        retain=mqtt_cfg.retain,
                        client_id=mqtt_cfg.client_id,
                    ),
                )
            )

    def start_event_ingestion(self, on_event: Callable[[dict], None]) -> None:
        callback_store = _CallbackEventStore(on_event)
        self._server = start_edge_event_server(
            self._cfg.edge_event_host,
            self._cfg.edge_event_port,
            callback_store,
        )
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def publish_phase(self, phase_name: str, timestamp: float) -> bool:
        payload = {"phase": phase_name, "timestamp": timestamp}
        if self._publish_backend == "mqtt":
            if self._mqtt_phase_client is None:
                if self._logger:
                    self._logger.warning("phase publish backend=mqtt but mqtt config unavailable")
                return False
            return self._mqtt_phase_client.publish(self._phase_topic, payload)

        if self._http_phase_client is None:
            if self._logger:
                self._logger.warning("phase publish backend=http but PHASE_HTTP_BASE_URL not configured")
            return False
        return self._http_phase_client.publish(self._phase_topic, payload)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
