import ast
import json
from pathlib import Path

import pytest

from xeno.evaluation.runner import demo, replay
from xeno.service.schemas import EpisodeConfig
from xeno.simulation.core import REGISTRY


def test_run_artifacts_and_recorded_replay(tmp_path):
    output = tmp_path / "episode"
    result = demo(output, EpisodeConfig(family="mineral_growth"), "fixed")
    loaded = replay(output / "observations.jsonl")
    assert loaded["final_status"] == "concluded"
    assert loaded["conclusion"]["target_score"] == result["score"]
    assert (output / "fields.private.npz").exists()
    assert "source_sha256" in json.loads((output / "metadata.json").read_text())
    with pytest.raises(ValueError, match="already exists"):
        demo(output, EpisodeConfig(), "fixed")
    lines = (output / "observations.jsonl").read_text().splitlines()
    (output / "broken.jsonl").write_text("\n".join(lines[1:]))
    with pytest.raises(ValueError, match="missing"):
        replay(output / "broken.jsonl")


def test_investigator_import_boundary():
    directory = Path(__file__).parents[1] / "xeno" / "investigator"
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("xeno.simulation", "xeno.evaluation", "xeno.service", "xeno.laboratory")
                )


def test_registry_token_stoichiometry_and_evidence():
    for reaction in REGISTRY["reactions"]:
        assert sum(reaction["stoichiometry"]) == 0
        assert reaction["evidence_class"] == "hypothetical"
