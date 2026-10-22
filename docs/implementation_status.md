# Implementation status

Build date: 22 October 2026. Scope: F0 prototype, prompt-driven Unreal scenes and physics reference replay.

| Area | State |
| --- | --- |
| Numerical fixtures | Implemented: conservative tokens, positive transfers, no-flux transport, analytic BDF fixture |
| Mission/lab loop | Implemented: deterministic navigation, finite sampling, matched aliquots, two interventions |
| Runtime service | Implemented: authenticated API, transactions, revisions, retries, WebSocket events |
| Investigation | Implemented: passive, random, fixed, uncertainty-adaptive heuristics; evidence-linked reports |
| Persistence/replay | Implemented: SQLite restart, raw observations, private JSON checkpoints, NPZ fields |
| Research benchmark | Development smoke comparison only; frozen family holdouts and calibrated policies pending |
| Scene generation | GPT-6 Luna through signed-in Codex CLI, validated plans, local prompt studio and three runtime scene grammars |
| Physics reference | Bounded, checksum-verified The Well density/velocity import and Unreal replay; new interactive PDE solves pending |
| Molecular chemistry | Pending: measured/computed kinetics, physical stoichiometry, silicon modules |
| Protocell lifecycle | Pending: individual inventories, maintenance budgets, division, inheritance, evolution |
| Ecology | Pending: explicit exchange, cross-feeding interventions and rescue studies |
| Unreal | Implemented: UE 5.8.3 C++ HTTP/WebSocket bridge, procedural basin, detailed rover/station, shaded materials, orbit camera and HUD; editor and packaged runtime checks passed; camera sensing and rover physics pending |

Validation: 42 tests passed; Ruff lint and formatting passed. A 32-episode development
comparison, saved-observation replay, analytic BDF check and real local HTTP episode completed.
The service was started on loopback port 8766 because an existing process occupied 8765.
See `verification.md` for artifacts and measured limits.
Unreal integration was subsequently authorized and verified through a packaged Windows
Development executable. Its live mission completed movement, observation, collection,
duplicate-request verification, aliquot splitting, a paired temperature experiment and
conclusion submission. See `unreal_handoff.md` for reproducible launch/build commands.
The subsequent visual upgrade passed packaged smoke and both camera-view checks, with
inspected captures and unchanged scientific costs. See `visual_environment.md` for details.
The subsequent Scenario Studio passed a real GPT-6 Luna prompt through to a live packaged scene
rebuild. All three scenario captures and the recorded The Well field were inspected. Full
mission costs stayed unchanged. See `scenario_studio.md` and `well_physics.md`.

The original blueprint remains unchanged. This status describes the built subset rather than
claiming completion of the proposed multi-phase research platform.

## Canyon modernization, 22 October 2026

The first canyon vertical slice now includes Nanite cliff scans and textured rock
assets, a DX12/SM6 software-Lumen profile, native editor MCP authoring from validated
Luna plans, a Newton rigid chassis with six ray suspension contacts, and a live 2D
thermal solver. All 48 Python tests and lint/format checks pass. CPU/CUDA Newton
fixtures, native authoring, owner-process cleanup, live streaming under load and
packaged mission/capture checks were performed. The three F0 numerical source
files remain unchanged. See [the canyon handoff](canyon_vertical_slice.md) for
commands, evidence and the remaining scientific and physics boundaries.
