"""Messaging initialization and edge event receiver lifecycle helpers."""
from __future__ import annotations

from contextlib import suppress

from integration.comm import build_messaging_client


def init_messaging_client(config, context, logger) -> None:
    messaging = build_messaging_client(config)
    context.set_resource("messaging_client", messaging)
    edge_backend = getattr(getattr(config, "edge_events", None), "backend", "mqtt")
    phase_backend = getattr(getattr(config, "phase_messaging", None), "backend", "mqtt")
    logger.info(
        "messaging client ready (edge_events=%s, phase_publish=%s)",
        edge_backend,
        phase_backend,
    )


def start_edge_event_receiver(config, context, store, logger) -> None:
    edge_cfg = getattr(config, "edge_events", None)
    backend = (getattr(edge_cfg, "backend", None) or "mqtt").strip().lower()

    messaging = context.get_resource("messaging_client")
    if messaging is None:
        logger.warning("edge event receiver skipped: messaging_client not ready")
        return

    try:
        messaging.subscribe("edge_events", store.add_event)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("edge event ingestion start failed: %s", exc)
        return

    logger.info("edge event receiver ready (backend=%s route=edge_events)", backend)


def close_messaging_client(context) -> None:
    messaging = context.get_resource("messaging_client")
    if messaging is None:
        return
    with suppress(Exception):
        messaging.close()
