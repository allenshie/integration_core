"""Phase publish adapters for different protocols."""
from __future__ import annotations

from abc import ABC, abstractmethod

from smart_messaging_core import HttpConfig, MessagingClient, MessagingConfig, MqttConfig
from smart_workflow import TaskError


class BasePhasePublisher(ABC):
    @abstractmethod
    def publish(self, phase_name: str, timestamp: float) -> bool:
        """Publish a phase update."""


class MqttPhasePublisher(BasePhasePublisher):
    def __init__(self, cfg, client: MessagingClient | None = None) -> None:
        self._topic = cfg.topic
        if client is not None:
            self._client = client
        else:
            self._client = MessagingClient(
                MessagingConfig(
                    publish_backend="mqtt",
                    subscribe_backend="none",
                    mqtt=MqttConfig(
                        host=cfg.host,
                        port=cfg.port,
                        qos=cfg.qos,
                        retain=cfg.retain,
                        client_id=cfg.client_id,
                    ),
                )
            )

    def publish(self, phase_name: str, timestamp: float) -> bool:
        return self._client.publish(self._topic, {"phase": phase_name, "timestamp": timestamp})


class HttpPhasePublisher(BasePhasePublisher):
    def __init__(self, http_cfg, topic: str) -> None:
        if not http_cfg or not http_cfg.base_url:
            raise TaskError("PHASE_HTTP_BASE_URL 未設定，無法使用 http 廣播")
        self._topic = topic
        self._client = MessagingClient(
            MessagingConfig(
                publish_backend="http",
                subscribe_backend="none",
                http=HttpConfig(
                    base_url=http_cfg.base_url,
                    timeout_seconds=http_cfg.timeout_seconds,
                ),
            )
        )

    def publish(self, phase_name: str, timestamp: float) -> bool:
        return self._client.publish(self._topic, {"phase": phase_name, "timestamp": timestamp})


class PhasePublisherRegistry:
    def __init__(self, cfg, http_cfg, logger=None, mqtt_client: MessagingClient | None = None) -> None:
        self._topic = cfg.topic if cfg else None
        self._publishers: dict[str, BasePhasePublisher] = {}
        self._missing: dict[str, str] = {}
        self._logger = logger

        if cfg and cfg.enabled and cfg.host:
            self._publishers["mqtt"] = MqttPhasePublisher(cfg, client=mqtt_client)
        else:
            self._missing["mqtt"] = "MQTT_ENABLED=1 且需設定 MQTT_HOST"

        if http_cfg and http_cfg.base_url:
            self._publishers["http"] = HttpPhasePublisher(http_cfg, self._topic or "")
        else:
            self._missing["http"] = "需設定 PHASE_HTTP_BASE_URL"

        if self._logger:
            enabled = sorted(self._publishers.keys())
            missing = {key: hint for key, hint in self._missing.items() if key not in self._publishers}
            self._logger.info("phase publishers enabled: %s", enabled)
            if missing:
                self._logger.info("phase publishers unavailable: %s", missing)

    def get(self, backend: str) -> BasePhasePublisher:
        key = (backend or "mqtt").strip().lower()
        publisher = self._publishers.get(key)
        if publisher is None:
            missing_hint = self._missing.get(key)
            if missing_hint:
                raise TaskError(f"phase publish backend {key} 尚未啟用，缺少設定: {missing_hint}")
            raise TaskError(f"不支援的 phase publish backend: {backend}")
        return publisher

    def publish(self, backend: str, phase_name: str, timestamp: float) -> bool:
        publisher = self.get(backend)
        return publisher.publish(phase_name, timestamp)
