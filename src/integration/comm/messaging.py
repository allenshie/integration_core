"""Messaging client builder for integration communication flows."""
from __future__ import annotations

from smart_messaging_core import HttpConfig, MessagingClient, MessagingConfig, MqttConfig, RouteConfig


def build_messaging_client(config) -> MessagingClient:
    """Build a single messaging facade for edge ingestion + phase publish."""

    mqtt_cfg = getattr(config, "mqtt", None)
    edge_cfg = getattr(config, "edge_events", None)
    phase_cfg = getattr(config, "phase_messaging", None)
    phase_http = getattr(config, "phase_http", None)

    publish_backend = (getattr(phase_cfg, "backend", None) or "mqtt").strip().lower()
    subscribe_backend = (getattr(edge_cfg, "backend", None) or "mqtt").strip().lower()

    mqtt = None
    if mqtt_cfg is not None:
        mqtt = MqttConfig(
            host=mqtt_cfg.host,
            port=mqtt_cfg.port,
            qos=mqtt_cfg.qos,
            retain=mqtt_cfg.retain,
            client_id=mqtt_cfg.client_id,
            auth_enabled=mqtt_cfg.auth_enabled,
            username=mqtt_cfg.username,
            password=mqtt_cfg.password,
        )

    http_timeout = getattr(phase_http, "timeout_seconds", 5) if phase_http is not None else 5
    http_base_url = getattr(phase_http, "base_url", "") if phase_http is not None else ""
    http = HttpConfig(
        base_url=http_base_url,
        timeout_seconds=http_timeout,
        listen_host=getattr(edge_cfg, "host", "0.0.0.0"),
        listen_port=getattr(edge_cfg, "port", 9000),
    )

    routes = {
        "phase_publish": RouteConfig(
            backend=publish_backend,
            channel=getattr(phase_cfg, "channel", "integration/phase"),
        ),
        "edge_events": RouteConfig(
            backend=subscribe_backend,
            channel=getattr(edge_cfg, "channel", "edge/events"),
        ),
    }

    return MessagingClient(
        MessagingConfig(
            mqtt=mqtt,
            http=http,
            routes=routes,
        )
    )
