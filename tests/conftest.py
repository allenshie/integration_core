"""Pytest fixtures for integration_core tests."""
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SMART_WORKFLOW_ROOT = Path(__file__).resolve().parents[3] / "smart-workflow"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SMART_WORKFLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(SMART_WORKFLOW_ROOT))

for module_name in list(sys.modules):
    if module_name == "integration" or module_name.startswith("integration."):
        sys.modules.pop(module_name)
    if module_name == "smart_workflow" or module_name.startswith("smart_workflow."):
        sys.modules.pop(module_name)
