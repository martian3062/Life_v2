# Canyon vertical slice — 22 October 2026

The canyon now combines reusable textured static meshes, native Unreal editor
authoring, an external Newton chassis simulation and a live thermal field.
Glacier and caldera keep their existing scene contracts; the live fluid is shown
in the canyon's first pool.

## Start and rebuild

```powershell
uv sync --locked
.\scripts\Install-XenoPhysics.ps1
.\scripts\Build-XenoUnreal.ps1 -Target Editor
.\scripts\Build-XenoUnreal.ps1 -Target Package
.\scripts\Start-XenoStudio.ps1
.\scripts\Start-XenoAuthoring.ps1
```

The local studio is at <http://127.0.0.1:8770>. Select Mineral canyon, load its
preset and open Unreal. A game launch starts its own hidden physics worker and
stops it when the game closes. Process-lifetime checks keep rendering pauses
from shutting down the worker and also clean up workers when their owner exits.
`-NoLivePhysics` on the Unreal launcher uses the existing animated fallback.
Use `Start-XenoAuthoring.ps1 -Visible` to inspect the editor viewport; the default
editor runs with NullRHI for local authoring without a second GPU viewport.
Studio starts that editor automatically when a prompt or Build in editor needs it.

## Rendering

- UE 5.8.3, DX12/SM6, TSR at 70% internal resolution, software Lumen and virtual
  shadow maps. Hardware ray tracing is disabled. Streaming pool: 1800 MB.
- Two Poly Haven Namaqualand cliff scans form the canyon walls and outcrops.
  Four generated rock variants provide smaller boulders and instanced stones.
  Nanite is enabled during editor import; placement is deterministic from the
  scene seed. Four generated cliff variants remain in the asset library.
- 2K base color, DirectX normal and roughness maps. Downloaded bytes are pinned
  by SHA-256 in `configs/assets/canyon-sources.json` and `canyon-scans.json`.
  The source meshes and textures regenerate through `scripts/prepare_canyon_assets.py`.
  Scan materials render both sides of the captured surfaces.
- The static assets support Nanite and distance fields. The remaining runtime
  procedural terrain, pools and other biomes do not become Nanite meshes merely
  because the renderer enables Nanite.

These settings are a measured preview configuration, not a guaranteed frame-rate
target or cinematic-quality certification. A 6 GB laptop GPU remains a constraint.

## Controlled Luna and native MCP authoring

GPT-6 Luna continues to emit only the strict SceneSpec JSON. The trusted studio
validates that JSON and atomically publishes the approved scene. It then calls
the editor's native MCP endpoint sequentially at `127.0.0.1:8000/mcp`.

The custom editor toolset has only two tools: read the approved scene and build
it. A build requires the exact approved CRC; it accepts no executable code,
paths or arbitrary editor operations. It replaces only XENO-authored environment
actors in the current editor world. The studio checks a fresh native
acknowledgment before reporting that the editor authored the scene. The package
independently watches the approved scene contract for runtime rebuilding.

The UE MCP plugin is experimental and editor-only. It is excluded from the
redistributable game. The workflow uses the existing signed-in local Codex CLI;
it does not require an OpenAI API key or a public tunnel.

## Live physics and authority

The isolated environment pins Newton 1.7.0, Warp 1.18.0, NumPy 2.4.3 and SciPy
1.17.1. Newton runs a 120 kg rigid chassis at 240 Hz. Six suspension rays apply
spring/damper forces and terrain-normal, Coulomb-limited tire forces. The Unreal
terrain is exported as a 129×129 height grid and sampled with bilinear
interpolation. Native Unreal consumes the simulated chassis pose and wheel
compression. The default uses CPU for this single chassis; CUDA is also checked.

The fluid worker evolves a dimensionless 64×64 periodic Boussinesq system in
vorticity/streamfunction form, using dealiased Fourier derivatives, SSPRK3 advection with CFL-limited substeps
and implicit diffusion. A localized heater and distributed cooling drive the
flow. The first pool displays its evolving temperature field. It is a periodic
2D patch mapped to a pool for presentation, not a free-surface pool solver.
The FFT solver runs on CPU; it is not advertised as GPU fluid simulation.

Each game has its own atomic file IPC directory, timestamps, terrain CRC, frame
counter, temperature/velocity fields and numerical diagnostics. No service
credentials are written into the physics IPC files. Live output must be fresh before the
native actor consumes it. The Well's original recorded gas-flow display remains
available with P and is initially hidden when live physics is enabled.

**Authority boundary:** F0 still owns scientific navigation, timing, finite
sampling and laboratory results. The Newton rover follows a presentation target
at the existing 100× artistic magnification. Arrival of this rover does not yet
gate scientific sampling. Rocks are visual obstacles, not Newton collision
geometry. There is no articulated wheel solver, deformable soil, calibrated
thermal chemistry, glacier mechanics, lava solver or trained surrogate.

## Validation

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
$env:PYTHONPATH = (Get-Location).Path
runs/physics/.venv/Scripts/python.exe scripts/verify_live_physics.py
.\scripts\Run-XenoUnreal.ps1 -Mode Packaged -Smoke
```

Use `uv run python scripts/verify_packaged_scenarios.py` to capture all three
scenarios, verify the private evaluator and leave the reviewed canyon open.

The physics script measures static force balance, driven motion, zero-friction
behavior and traction bounds on CPU and CUDA. Python tests compare heat diffusion
to analytic Fourier decay and check scalar mean conservation and projected
velocity divergence. A 70-second worker test uses an intentionally stale
heartbeat while its owner remains alive; a separate check confirms cleanup when
that owner exits. Reports are in ignored `runs/physics`; per-game logs and
snapshots are beside each runtime check.

## Asset licenses and upstream references

- [ambientCG Rock030](https://ambientcg.com/view?id=Rock030),
  [CC0 license](https://docs.ambientcg.com/license/).
- [Poly Haven Namaqualand Cliff 01](https://polyhaven.com/a/namaqualand_cliff_01)
  and [Cliff 02](https://polyhaven.com/a/namaqualand_cliff_02), CC0 models.
- [Poly Haven rock_boulder_dry](https://polyhaven.com/a/rock_boulder_dry),
  [CC0 asset license](https://polyhaven.com/license).
- [Newton stable installation and compatibility](https://newton-physics.github.io/newton/1.7.0/guide/installation.html).
- [UE 5.8 native MCP](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor?application_version=5.8).

The Namaqualand cliffs are CC0 photogrammetry assets; the smaller rock variants
and retained procedural cliffs are generated project assets. CC0 textures are
imported from the named providers. The Well retains its separate
dataset provenance and license described in `well_physics.md`.
