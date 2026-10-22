import json
import os

import pytest

from xeno.scenes.authoring import build_approved_scene


def test_authoring_rejects_stale_native_acknowledgment(tmp_path, monkeypatch):
    class Client:
        def __init__(self):
            self.client = self

        def initialize(self):
            pass

        def call(self, name, arguments):
            return {"content": [{"type": "text", "text": "ERROR: CRC mismatch"}]}

        def close(self):
            pass

    monkeypatch.setattr("xeno.scenes.authoring.UnrealMCP", Client)
    path = tmp_path / "active-scene.json"
    path.write_text("{}")
    acknowledgment = tmp_path / "authoring-status.json"
    acknowledgment.write_text(json.dumps({"state": "authored", "spec_crc": 2745614147}))
    os.utime(acknowledgment, (1, 1))
    with pytest.raises(RuntimeError, match="did not acknowledge"):
        build_approved_scene(path)
