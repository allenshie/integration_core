from __future__ import annotations

import json
from importlib.metadata import distribution

from mcmot import MCMOT


EXPECTED_MCMOT_COMMIT = "20d4c930f3c95ff7f26bc305432b66ac2192b091"


def test_uv_loads_pinned_mcmot_batch_api():
    direct_url = json.loads(distribution("MCMOT").read_text("direct_url.json") or "{}")

    vcs_info = direct_url["vcs_info"]
    assert direct_url["url"] == "ssh://git@github.com/ChenPingChen/MCMOT.git"
    assert vcs_info["vcs"] == "git"
    assert vcs_info["requested_revision"] == EXPECTED_MCMOT_COMMIT
    assert vcs_info["commit_id"] == EXPECTED_MCMOT_COMMIT

    assert hasattr(MCMOT, "process_trajectory_snapshot")
