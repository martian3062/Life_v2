# Prompt-to-Unreal scenario studio

The local studio uses **GPT-6 Luna** (`gpt-6-luna`) to turn a scene prompt into a validated
presentation specification. Unreal reads it and builds geometry, materials, lighting and camera
at runtime. Subsequent specifications rebuild the open environment without recompiling the game
or restarting the scientific mission.

## Start

```powershell
.\scripts\Start-XenoStudio.ps1
```

Open <http://127.0.0.1:8770>. Choose a setting, write a prompt and select **Generate & build**.
**Load preset** builds the selected authored setting without calling the model. Sliders change
the current plan; **Apply adjustments** sends those settings to the running renderer.

The planner uses the installed Codex CLI and its existing local sign-in. No account tokens are
copied into this repository, browser or Unreal package. Model calls consume the signed-in account's
Codex allowance. If sign-in/model access fails, the job reports failure and preserves the previous
scene. It does not silently substitute another model or label a preset as generated output.

## Three scenarios

| Setting | Built scene grammar |
| --- | --- |
| Saffron Veil | Eroded ochre canyon walls, layered mineral terraces, turquoise pools, slabs and talus |
| Cobalt Divide | Blue glacier walls, fractured ice shelves, crevasse, pressure ridges and brine-like pools |
| Ember Crown | Dark caldera terrain, hexagonal basalt columns, cooled rock and orange fissure accents |

GPT-6 Luna drafted the initial art-direction prompts. Each setting uses dense near-field terrain,
a coarser outer field, multi-scale procedural PBR grain/normal detail, deformed rock meshes and
instanced pebbles. The scene keeps the rover, public sample markers and optional mission station.
RMB orbits; the wheel zooms; R resets the plan's camera; H toggles the scientific HUD. Studio
launches start with the HUD hidden so the environment fills the window.

The launcher also attaches the prepared [The Well physics reference](well_physics.md). P toggles
its labelled density/velocity playback patch. It is recorded gas dynamics, independent of the
three artistic biomes and the mission's F0 scientific state.

Example prompt:

> A wide blue glacier fissure at low sun. Tall pressure ridges, dense fine frost detail and
> larger reflective pools. Keep the station. Pull the camera back for an expansive view.

Supported prompt controls: biome, appearance seed, relief, rock density, surface detail,
pool/fissure scale, haze, sun elevation/azimuth, camera yaw/pitch/distance and station visibility.
The direction text is a caption; supported numeric fields drive the renderer. Requests outside
this scene grammar do not produce arbitrary downloaded models, buildings or creatures.

## Reproduce from the command line

```powershell
uv run xeno scene-plan "A low sun glacier with dense fine ice detail" --scenario brine_glacier --output runs/my-scene
.\scripts\Run-XenoUnreal.ps1 -Mode Packaged -SceneFile runs/my-scene/model-scene.json -CleanView
```

Build native code/assets with `Build-XenoUnreal.ps1 -Target Editor`, then cook/archive the
standalone Windows game with `-Target Package`. Subsequent scene changes require no build.
Private sessions, model logs, active plans, acknowledgements and previews remain under ignored
`runs/`. The planner requests structured output in a read-only, ephemeral Codex run. The app
validates it again before atomic replacement of the active scene. Unreal independently validates
the fields and acknowledges the exact file CRC after building.

## Scientific boundary

These are artistic environments around the existing F0 mission. Pools, ice and glowing fissures
do not change the token chemistry, inventory, budgets or time. The rover's visual grounding
remains separate from vehicle physics. This is a procedural scene generator, not unrestricted
text-to-3D asset generation or a claim of photorealism.

## Model integration references

- [GPT-6 Luna model](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Codex non-interactive mode and schema output](https://developers.openai.com/codex/noninteractive).
# Native editor authoring

The current studio can start the project's hidden authoring editor automatically.
After validating a Luna plan, it requests a build through UE 5.8 native MCP. The
editor accepts only the approved scene and its matching CRC; prompts cannot
supply code, paths or arbitrary editor operations. **Build in editor** performs
the same bounded action. The packaged game also consumes the approved scene file.
See [the canyon vertical slice](canyon_vertical_slice.md) for setup and limits.
