"""Communication helpers for edge event ingestion and phase publish."""

from .messaging import build_messaging_client

__all__ = ["build_messaging_client"]
