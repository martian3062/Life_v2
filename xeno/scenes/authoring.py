"""Sequential, fixed-scope adapter to UE 5.8's native local MCP server.

Luna proposes a schema-validated scene. The trusted coordinator asks Unreal to
build only that approved file with its exact CRC. No arbitrary editor tools,
Python, shell commands or paths can be supplied by a prompt.
"""

import json
import os
import subprocess
import threading
import time
import zlib
from pathlib import Path

import httpx

_LOCK = threading.Lock()
_START_LOCK = threading.Lock()
ENDPOINT = "http://127.0.0.1:8000/mcp"


class UnrealMCP:
    def __init__(self):
        self.client = httpx.Client(
            timeout=60,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        self.sequence = 0

    def rpc(self, method, params):
        self.sequence += 1
        response = self.client.post(
            ENDPOINT,
            json={"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params},
        )
        response.raise_for_status()
        session = response.headers.get("mcp-session-id")
        if session:
            self.client.headers["Mcp-Session-Id"] = session
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            messages = [
                json.loads(line[5:])
                for line in response.text.splitlines()
                if line.startswith("data:")
            ]
            value = next(v for v in messages if v.get("id") == self.sequence)
        else:
            value = response.json()
        if "error" in value:
            raise RuntimeError(f"Unreal MCP rejected {method}: {value['error']}")
        return value.get("result", {})

    def initialize(self):
        return self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "xeno-approved-authoring", "version": "1.0"},
            },
        )

    def call(self, name, arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError("Unreal authoring tool reported an error")
        return result


def build_approved_scene(path: Path):
    with _LOCK:
        client = UnrealMCP()
        try:
            client.initialize()
            crc = str(zlib.crc32(path.read_bytes()))
            started = time.time()
            result = client.call(
                "call_tool",
                {
                    "toolset_name": "XenoAuthoring.XenoAuthoringToolset",
                    "tool_name": "BuildApprovedScene",
                    "arguments": {"expectedCrc": crc},
                },
            )
            acknowledgment = path.parent / "authoring-status.json"
            if not acknowledgment.exists() or acknowledgment.stat().st_mtime < started:
                raise RuntimeError("Unreal did not acknowledge this authoring request")
            native = json.loads(acknowledgment.read_text(encoding="utf-8-sig"))
            if native.get("spec_crc") != int(crc) or native.get("state") != "authored":
                raise RuntimeError("Unreal authored a different plan")
            if str(zlib.crc32(path.read_bytes())) != crc:
                raise RuntimeError("The approved plan changed while Unreal was building")
            return {"state": "authored", "spec_crc": int(crc), "result": result}
        finally:
            client.client.close()


def _start_and_author(path: Path, workspace: Path):
    with _START_LOCK:
        script = workspace / "scripts/Start-XenoAuthoring.ps1"
        binary = workspace / "unreal/Xeno/Binaries/Win64/UnrealEditor-XenoAuthoring.dll"
        if not script.exists() or not binary.exists():
            raise RuntimeError("Build the XENO editor first")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            raise RuntimeError("The XENO authoring editor could not start")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = False
            with _LOCK:
                client = UnrealMCP()
                try:
                    client.initialize()
                    listing = client.call("list_toolsets", {})
                    ready = "XenoAuthoring.XenoAuthoringToolset" in json.dumps(listing)
                except (httpx.HTTPError, RuntimeError, ValueError):
                    pass
                finally:
                    client.client.close()
            if ready:
                return build_approved_scene(path)
            time.sleep(0.5)
        raise RuntimeError("The authoring editor did not become ready")


def try_author_scene(path: Path, workspace: Path | None = None):
    try:
        return build_approved_scene(path)
    except httpx.ConnectError:
        if workspace is not None:
            try:
                return _start_and_author(path, workspace)
            except (RuntimeError, httpx.HTTPError, OSError, subprocess.TimeoutExpired):
                return {
                    "state": "authoring_failed",
                    "message": "The authoring editor could not start. Check its local log.",
                }
        return {
            "state": "editor_unavailable",
            "message": "Start the XENO authoring editor to use native MCP.",
        }
    except (httpx.HTTPError, RuntimeError, ValueError, StopIteration):
        return {
            "state": "authoring_failed",
            "message": "Unreal did not acknowledge this approved scene. Check the authoring log.",
        }
