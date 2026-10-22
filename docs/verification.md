# Initial verification — 22 October 2026

Environment: Windows, CPython 3.12.10, locked dependencies in `uv.lock`.
Model: `f0-maintenance-2`. These checks validate the implemented headless subset.

| Check | Observed result |
| --- | --- |
| `uv run pytest` | 36 passed in 51.40 s, including simultaneous duplicate requests and restart recovery |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `uv run xeno verify` | BDF analytic error 2.9997365702527645e-10; token drift 5.551115123125783e-16 |
| Headless adaptive episode | Completed; report abstained as inconclusive |
| Recorded replay | 9 ordered events; frozen conclusion recovered |
| Development comparison | All 32 episodes completed: 4 families × 2 seeds × 4 policies |
| Maximum comparison inventory residual | 3.0791341698588326e-17 token |
| Live HTTP | `/health` and `/docs` returned 200; fixed-policy mineral episode reached conclusion |
| Live WebSocket | Ordered events 0, 1 received; resynchronization after 0 returned event 1 |
| Wheel packaging | Built successfully; includes runtime registry and excludes private run files |

## Artifacts

- `runs/headless-demo-v2/`: completed adaptive episode, public event stream and private checkpoint.
- `runs/headless-development-check/summary.private.json`: aggregate and per-family diagnostics.
- `runs/live-http-smoke/`: complete episode using a real HTTP connection to port 8766.
- `runs/local/`: persistent service state, private credentials and service logs.

Earlier `first-headless-demo` artifacts used an in-progress numerical model. Use the v2 run
and development comparison for the current transport implementation.

## Development comparison

All policies receive the same budget caps and paired family/seed combinations. The score
threshold is a diagnostic fixed 0.5; it was not selected on a validation set. Score metrics
include abstentions; coverage reports categorical decisions separately.

| Policy | Episodes | Score TPR | Score FPR | Coverage | Mean lab actions | Mean mission s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Passive | 8 | 1.00 | 1.00 | 0.00 | 0 | 121 |
| Random | 8 | 1.00 | 0.25 | 0.25 | 2 | 127 |
| Fixed | 8 | 1.00 | 0.50 | 0.25 | 2 | 127 |
| Adaptive | 8 | 1.00 | 0.25 | 0.25 | 2 | 127 |

This tiny comparison does not demonstrate a research improvement. Random and adaptive happened
to choose the same interventions with the single policy seed used. Positive cases often
remain inconclusive; the abiotic catalyst control is still difficult. Scores are uncalibrated.
More stochastic policy repetitions, mechanism families, equal-cost passive measurements,
validation-selected thresholds and frozen holdouts are needed before scientific comparison.

## Remaining acceptance gates

Individual protocell division/inheritance, physical element/charge/thermodynamic validation,
empirical chemistry, causal cross-feeding, comprehensive coupled-grid convergence, calibrated
unknown-model detection and OS-level evaluator isolation are pending. Packaged Unreal runtime
execution was subsequently verified as described below.
SQLite restart and recorded replay are tested; portable restoration of exported private JSON
and reproducibility across different Unreal physics implementations are not claimed.

## Unreal integration verification

Unreal 5.8.3 (58210709) was discovered locally and used to compile both the Editor and Win64
Development game targets. BuildCookRun completed build, cook, stage and archive successfully.
The test uses runtime C++ HTTP and WebSockets; Python is used only for creating editor assets.

Both editor game mode and the standalone cooked executable completed this sequence against
the live service: move, observe, collect, repeat the identical collection request, split,
paired temperature intervention and conclusion. Each completed at revision 6 with all seven
stream events, one charged collection of 2e-7 m3 and one lab action. Inventory residual was
1.431146867680866e-17 token in the fixed default fixture. The scientific outcome is deliberately
inconclusive: this is a connection check rather than an inference-performance claim.

Initial successful records:

- `runs/unreal-EditorGame-20261022T1300349878785Z/runtime-check.json`
- `runs/unreal-Packaged-20261022T1306171865291Z/runtime-check.json`
- `runs/unreal-Packaged-20261022T1306250640139Z/preview.png` (first rendered check)

The package is local at `runs/unreal-package/Windows/`. Its size was about 897.9 MiB.
Package inspection found no runtime credential/session files or Python interpreter binaries.
Private evaluations, source/binary hashes and copied build logs are in
`runs/unreal-verification/`. Those files remain outside normal source commits.

The first integration run exposed a client test comparing raw JSON text across retries.
The client now uses Unreal's semantic JSON equality so field order cannot cause a false
idempotency failure. Requests also begin after initial map loading to avoid startup stalls.
Final verification after the HUD/camera rebuild:

- Editor game mode: `runs/unreal-EditorGame-20261022T1313085952642Z/runtime-check.json`.
- Packaged NullRHI: `runs/unreal-Packaged-20261022T1313061041883Z/runtime-check.json`.
- Rendered packaged run: `runs/unreal-Packaged-20261022T1313280809577Z/runtime-check.json`.
- Visually inspected preview: `runs/unreal-Packaged-20261022T1313280809577Z/preview.png`.
- Consolidated proof and hashes: `runs/unreal-verification/verification-final.private.json`.

All three final runs passed with seven events and revision 6. The final camera-only native
change rebuilt both targets and updated the executable in the existing cooked archive;
no content assets changed. Both runtime checks and the rendered check were repeated afterward.
Visual inspection confirmed readable panels/axes and a rover/terrain view clear of the HUD.

## Aurelia Basin visual upgrade

The scene was subsequently rebuilt with procedural basin terrain, rock outcrops, a six-wheel
rover, field station, shaded materials, sky/fog, orbit controls and a compact HUD. The full
Windows BuildCookRun completed successfully, including cooking the new materials and the
ProceduralMeshComponent runtime plugin.

Final packaged checks:

- NullRHI smoke: `runs/unreal-Packaged-20261022T1340130819171Z/runtime-check.json`.
- Overview: `runs/unreal-Packaged-20261022T1340162426031Z/runtime-check.json`.
- Rover view: `runs/unreal-Packaged-20261022T1340518215679Z/runtime-check.json`.
- Consolidated evaluation and source/binary hashes:
  `runs/environment-verification/verification.private.json`.

All three passed with cooked data, verified service health, a live WebSocket, idempotent
collection, seven stream events and final revision 6. Each charged one collection of
2e-7 m3 and one lab action, with inventory residual below 1e-15 token. The two views had
identical cost ledgers. The numerical core, laboratory experiment and sensor source hashes
still match the headless v2 baseline.

Both corresponding `preview.png` captures were inspected at 1280 by 800. A normal-buffer
diagnostic exposed inward procedural face winding during development; the final terrain
and rock triangles were corrected and the lit packaged renders checked afterward.

## Prompt-driven scenarios and The Well reference

The final Windows package was rebuilt and cooked after adding the scene contract, runtime
rebuilds, three geology grammars and The Well reference actor. The final material rebuild
completed BuildCookRun successfully in 113.55 seconds. All 42 Python checks passed; Ruff lint,
format checks, served JavaScript syntax and PowerShell parsing passed.

Final visible packaged runs, each with seven stream events, revision 6, idempotent collection,
one charged lab action, 2e-7 m3 collected and inventory residual below 1e-15:

- Canyon: `runs/unreal-Packaged-20261022T1419551538033Z/`.
- Glacier: `runs/unreal-Packaged-20261022T1420127453136Z/`.
- Caldera: `runs/unreal-Packaged-20261022T1420284749232Z/`.

Each run verified cooked data and loaded `turbulent_radiative_layer_2D`. The corresponding
1280 by 800 captures were visually inspected and copied to
`runs/scenario-studio/previews/{hydrothermal_canyon,brine_glacier,basalt_caldera}.png`.
An initial field material ignored vertex colors; a dedicated vertex-color reference material
was added and all three final captures repeated with the field visible.

A real `gpt-6-luna` request through the signed-in local Codex CLI returned a validated caldera
plan. The already-running packaged client acknowledged the exact active file CRC, 3229926296,
after rebuilding. Trusted evaluation before/after confirmed unchanged mission costs. The
numerical core, lab experiment and sensor source hashes still match the headless v2 baseline.

`runs/scenario-verification/verification.private.json` records the cases, private evaluations,
model request/result, runtime acknowledgement, source/binary hashes and inspected captures.
The original HDF5 source and display-export checksums are in `runs/well/`.

An attempted automatic screenshot after live switching exposed a D3D11 render-target size
assertion. Automatic captures during scene switching were removed; successive switches and
the final model-driven rebuild were repeated without the assertion. Preset captures above
come from completed visible runs. Browser automation had no available browser surfaces, so
the studio was checked through HTTP endpoints and served JavaScript syntax, not a browser UI run.

These checks establish bounded recorded-field playback and three procedural presentation
grammars. They do not establish new PDE solves, a trained surrogate, cryogenic or magma physics,
photorealism, or a coupled scientific planetary model. See `scenario_studio.md` and
`well_physics.md` for controls, provenance and boundaries.
# Canyon modernization verification — 22 October 2026

- 48 Python tests pass; Ruff check and format pass for 56 Python files.
- Newton 1.7/Warp 1.18 fixtures ran on CPU and RTX 4050 CUDA. Static force balance,
  driven motion, zero traction and tire-force bounds passed.
- Live thermal checks include analytic diffusion, scalar mean conservation,
  projected divergence and a 60-second stability regression. SSPRK3 and adaptive
  CFL substeps replaced the initially unstable integrator.
- A 70-second real worker run kept publishing fresh frames despite an intentionally
  stale game heartbeat while its owner stayed alive. A separate owner-exit run
  stopped cleanly. Worker lifetime now follows the game process, and publication
  handles frame batches without skipping updates indefinitely.
- A real GPT-6 Luna Studio job received a native MCP acknowledgment. Wrong-CRC
  rejection, automatic editor startup and the final scanned-scene authoring path
  were also checked. The editor toolset exposes only the two XENO-specific tools.
- Visible packaged glacier, caldera and canyon missions passed revision 6 / seven
  events, one laboratory action, 2e-7 m3 collected and inventory residual below
  1e-15. The final canyon was recaptured after scan material/facing corrections;
  all three current preview images were inspected.
- Cosmetic scene rebuilding was acknowledged by Unreal and the terrain worker,
  with unchanged scientific costs. Core kinetics, laboratory and sensor hashes
  still match the earlier headless metadata.
- Final package build: `runs/canyon-facing-package.log`. Fresh launcher smoke:
  `runs/canyon-final-smoke.log`. Consolidated private evidence and package hashes:
  `runs/canyon-final-verification/verification.private.json`.

The measured preview is approximately 24–25 game FPS at 1280×800 on this RTX 4050
laptop under the current desktop load; it is not a general hardware benchmark.
Browser UI visual QA remains unavailable. The thermal system is a synthetic,
dimensionless 2D model, and the Newton presentation rover does not gate F0 sampling.
