"""Helpers for resolving integration core directories."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_CORE_ROOT: Optional[Path] = None
_CONFIG_ROOT: Optional[Path] = None


def set_core_root(path: str | Path) -> None:
    """Explicitly set the integration core root directory."""
    global _CORE_ROOT  # pylint: disable=global-statement
    resolved = Path(path).resolve()
    _CORE_ROOT = resolved
    os.environ["SW_CORE_ROOT"] = str(resolved)


def set_config_root(path: str | Path) -> None:
    """Explicitly set the config root directory."""
    global _CONFIG_ROOT  # pylint: disable=global-statement
    resolved = Path(path).resolve()
    _CONFIG_ROOT = resolved
    os.environ["CONFIG_ROOT"] = str(resolved)


def get_core_root() -> Path:
    """Return the integration core root directory."""
    global _CORE_ROOT  # pylint: disable=global-statement
    if _CORE_ROOT is not None:
        return _CORE_ROOT
    env_value = os.getenv("SW_CORE_ROOT")
    if env_value:
        _CORE_ROOT = Path(env_value).resolve()
        return _CORE_ROOT
    _CORE_ROOT = Path(__file__).resolve().parents[3]
    return _CORE_ROOT


def get_config_root() -> Path:
    """Return the config root directory for resolving relative paths."""
    global _CONFIG_ROOT  # pylint: disable=global-statement
    if _CONFIG_ROOT is not None:
        return _CONFIG_ROOT
    env_value = os.getenv("CONFIG_ROOT")
    if env_value:
        _CONFIG_ROOT = Path(env_value).resolve()
        return _CONFIG_ROOT
    _CONFIG_ROOT = get_core_root()
    return _CONFIG_ROOT
