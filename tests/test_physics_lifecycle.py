import os
import subprocess
import sys

from xeno.physics.lifecycle import process_running


def test_process_liveness_tracks_an_owned_child_without_signaling_it():
    assert process_running(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        assert process_running(child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)
    assert not process_running(child.pid)
