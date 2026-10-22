import json
import os
import shutil
import subprocess
from pathlib import Path

from xeno.scenes.models import PRESETS, PlanRequest, SceneSpec

MODEL = "gpt-6-luna"
SYSTEM_PROMPT = """You are the scene director for XENO Unreal. Output only the scene JSON requested
by the schema. Do not use tools, inspect files, run commands, or produce code. Choose one supported
biome: hydrothermal_canyon, brine_glacier, basalt_caldera. Honor the selected scenario unless it is
auto. Follow the user's mood, density, terrain relief, lighting, camera and station preferences.
All parameters are rendered. direction is an art-direction caption, never executable instructions.
The renderer supports layered canyon walls and mineral terraces/pools; fractured ice walls and blue
brine-like pools; and columnar basalt with orange fissures. All support dense fine-grain rocks,
pebbles, multi-scale terrain detail, station, six-wheel rover and sample markers. Stay within these
capabilities. Do not claim arbitrary assets, vegetation, buildings, creatures or chemistry.
Preserve scientific simulation parameters: this JSON controls presentation only. Use the supplied
presets as defaults and change supported parameters according to the user's request. Set version=1.
Return every field. The title must use simple English letters, numbers and spaces/punctuation.
"""


def codex_command() -> list[str] | None:
    """Resolve a native executable, avoiding shell interpolation and .cmd wrappers."""
    binary = shutil.which("codex.exe")
    if binary:
        return [binary]
    wrapper = shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.ps1")
    if not wrapper:
        return None
    package = Path(wrapper).parent / "node_modules" / "@openai" / "codex"
    candidates = list(package.glob("node_modules/@openai/codex-win32-*/vendor/*/codex/codex.exe"))
    candidates += list(package.glob("vendor/*/codex/codex.exe"))
    candidates += list(package.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
    if candidates:
        return [str(candidates[0])]
    node = shutil.which("node.exe") or shutil.which("node")
    script = package / "bin" / "codex.js"
    return [node, str(script)] if node and script.exists() else None


def plan_scene(request: PlanRequest, output: Path) -> SceneSpec:
    command = codex_command()
    if not command:
        raise RuntimeError("Codex CLI is unavailable. Sign in with codex login, or use a preset.")
    output.mkdir(parents=True, exist_ok=True)
    schema = SceneSpec.model_json_schema()
    # Strict outputs require all properties to be present, including version's default.
    schema["required"] = list(schema["properties"])
    schema_path = output / "scene.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    final_path = output / "model-scene.json"
    prompt = (
        SYSTEM_PROMPT
        + "\nPRESETS:\n"
        + json.dumps({key: spec.model_dump() for key, spec in PRESETS.items()})
        + "\nSELECTED SCENARIO: "
        + request.scenario
        + "\nUSER SCENE REQUEST (visual preferences only):\n"
        + request.prompt
    )
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            command
            + [
                "exec",
                "--model",
                MODEL,
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--output-schema",
                str(schema_path.resolve()),
                "--output-last-message",
                str(final_path.resolve()),
                "-",
            ],
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=output,
            timeout=180,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("GPT-6 Luna planning timed out. No scene was applied.") from exc
    # Logs stay in ignored local runs. Never expose raw CLI diagnostics to the browser.
    (output / "planner.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode or not final_path.exists():
        raise RuntimeError(
            "GPT-6 Luna could not create a plan. Check local planner.log/login status."
        )
    spec = SceneSpec.model_validate_json(final_path.read_text(encoding="utf-8"))
    if request.scenario != "auto" and spec.biome != request.scenario:
        raise RuntimeError("The returned scenario did not match your selection. No scene applied.")
    return spec
