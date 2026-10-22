# XENO

The [canyon vertical slice](docs/canyon_vertical_slice.md) adds DX12/SM6 rendering,
Nanite cliff/rock assets with CC0 PBR textures, controlled native Unreal MCP
authoring, Newton rover dynamics and a live 2D thermal flow. Scientific F0 state
remains independent. Start the studio and select the Mineral canyon preset.

XENO now has a runnable headless investigation prototype based on
`XENO_Detailed_Project_Blueprint.md`. Python owns scientific state and the mission clock.
A native Unreal Engine 5.8 runtime client now connects to the service, with a procedural basin,
six-wheel rover and field station; see
[Unreal setup and verification](docs/unreal_handoff.md).

The [Scenario Studio](docs/scenario_studio.md) connects GPT-6 Luna prompts to three detailed
Unreal settings: mineral canyon, glacier fissure and basalt caldera. Start it with
`.\scripts\Start-XenoStudio.ps1` and open <http://127.0.0.1:8770>. Scene changes rebuild live.

[The Well integration](docs/well_physics.md) adds verified recorded density/velocity fields from
Polymathic AI. Run `uv run python -m xeno.cli well-prepare` to prepare the bounded reference;
the Unreal launcher attaches it automatically. Press **P** to toggle its playback patch.

With the API running, launch the checked Windows demo from this workspace:

```powershell
.\scripts\Run-XenoUnreal.ps1 -Mode Packaged
```

The implemented path is: create a world → observe → collect finite material → split matched
aliquots → run a controlled intervention → submit a frozen conclusion → score → replay.

## Run on Windows

Python 3.12 and `uv` are used. Exact dependency versions are recorded in `uv.lock`.

```powershell
Set-Location D:\Life_v2
uv sync --locked
uv run xeno verify
uv run xeno demo
uv run xeno benchmark --seeds 2
```

Each demo prints its output directory. Inspect a recorded episode with:

```powershell
uv run xeno replay runs/<run-name>/observations.jsonl
```

Start the external service, ready for a future runtime client:

```powershell
uv run xeno serve --port 8766
```

The API binds to `127.0.0.1`. Interactive API docs are at
<http://127.0.0.1:8766/docs>. The first launch generates an admin credential in
`runs/local/credentials.private.json`; its value is never printed. Alternatively, supply
`XENO_ADMIN_TOKEN` through the environment. Keep the data directory private.
The running process ID is saved in `runs/local/service.pid`. Use Ctrl+C for a foreground
server; a server started in the background can be stopped with
`Stop-Process -Id ([int](Get-Content runs/local/service.pid))`.

For an authenticated episode from PowerShell, in a second terminal:

```powershell
$xenoCredentials = Get-Content runs/local/credentials.private.json -Raw | ConvertFrom-Json
$xenoAdminHeaders = @{ Authorization = "Bearer $($xenoCredentials.admin_token)" }
$xenoConfig = Get-Content configs/demo.json -Raw
$xenoEpisode = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/v1/admin/episodes `
  -Headers $xenoAdminHeaders -ContentType application/json -Body $xenoConfig
$xenoHeaders = @{ Authorization = "Bearer $($xenoEpisode.investigator_token)" }
Invoke-RestMethod -Uri "http://127.0.0.1:8766/v1/episodes/$($xenoEpisode.episode_id)/observation" `
  -Headers $xenoHeaders
```

## Implemented

- Four explicitly hypothetical F0 mechanism fixtures, with a versioned parameter registry.
- Positive, conservative resource/structure/waste token kinetics; a separate analytic BDF fixture.
- A no-flux 2D compartment grid, variable-volume transport and deterministic rover movement.
- Synthetic concentration sensors with Gaussian noise, detection limits and censored values.
- Finite collection, sample lineage, equal splits, resource pulses and temperature interventions.
- SQLite transactions, restartable state, revisions, duplicate-request protection and result lookup.
- Separate evaluator and per-episode investigator credentials; explicit observation allowlists.
- HTTP actions, streamed WebSocket observations and event resynchronization.
- An Unreal C++ bridge, 3D basin environment, detailed rover, compact HUD and runtime checks.
- Passive, random, fixed and uncertainty-adaptive baseline policies with evidence-linked reports.
- Development comparisons, raw observation replay, private checkpoints, array exports and provenance.

Run the scientific and protocol checks with:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Scientific scope

This first build uses **abstract conserved tokens**, not calibrated molecular chemistry.
The target is `implemented_aggregate_maintenance_rule_present`. The two positive fixtures are
effective maintenance compartments. Individual protocells, division, inheritance, cross-feeding
and silicon-containing chemistry remain future work. The mineral and catalyst fixture names
describe phenomenological controls, not physical mineral or reaction predictions.

Policy scores are uncalibrated heuristics. The comparison uses four development families;
it does not establish performance on withheld mechanisms or real life detection. No trained
model, LLM account, GPU or Unreal installation is required for these commands.

See [scientific scope](docs/scientific_scope.md), [API protocol](docs/protocol.md),
[implementation status](docs/implementation_status.md) and the
[Unreal connection](docs/unreal_handoff.md).
See [the environment design and controls](docs/visual_environment.md) for the 3D presentation.

The initial verification passed 36 tests and a 32-episode development comparison.
See [the recorded checks and limitations](docs/verification.md).

## Run artifacts

| File | Contents |
| --- | --- |
| `observations.jsonl` | Investigator-visible events in committed order |
| `report.json` | Policy choice, score, outcome and selection rationales |
| `evaluation.private.json` | Target, family, costs and numerical diagnostics |
| `checkpoint.private.json` | Full private scientific state and configuration |
| `fields.private.npz` | Token amounts and compartment volumes |
| `metadata.json` | Dependency versions, platform, model version and source hashes |
| `xeno.private.sqlite3` | Transactional state, events and original action results |

`runs/`, credentials, caches and virtual environments are excluded by `.gitignore`.
The local API protects roles, but policies running under the same OS account could read private
files directly. A research evaluation needs process/filesystem isolation before making an
adversarial access-separation claim.

# Life_v2
