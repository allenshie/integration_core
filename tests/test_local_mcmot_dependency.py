from __future__ import annotations

import json
from importlib.metadata import distribution

from mcmot import MCMOT


EXPECTED_MCMOT_COMMIT = "9b0a04be1e79e02b382d7dbcb71c6b70bd9edfa5"


def test_uv_loads_pinned_mcmot_batch_api():
    direct_url = json.loads(distribution("MCMOT").read_text("direct_url.json") or "{}")

    vcs_info = direct_url["vcs_info"]
    assert direct_url["url"] == "ssh://git@github.com/ChenPingChen/MCMOT.git"
    assert vcs_info["vcs"] == "git"
    assert vcs_info["requested_revision"] == EXPECTED_MCMOT_COMMIT
    assert vcs_info["commit_id"] == EXPECTED_MCMOT_COMMIT

    assert hasattr(MCMOT, "process_trajectory_snapshot")
