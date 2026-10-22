# Aurelia Basin presentation

The Unreal presentation now uses a continuous basin instead of a floating rectangular board.
The art direction uses warm rock, a cool rover accent, long shadows and a subdued sky/fog
gradient. Everything is generated locally from code and engine basic shapes; no downloaded
models or external texture licences are required for this scene.

## Scene structure

- A 129×129 finite surface mesh covers the visible basin and surrounding ridgelines.
- A deterministic appearance seed supplies rock variation independently of mechanism labels.
- Faceted boulders, geological sampling clusters, illuminated site rings and marker poles
  establish near/middle/far depth and show the four public sampling locations.
- A field station has a sample pod, solar array, antenna and beacon.
- The rover has a chassis, six wheels, suspension links, solar deck, camera mast, sensor lenses,
  antenna and sampling arm. Wheel motion and beacon animation are presentation only.
- Shaded, rough materials replace the original fully emissive surface. A world-space noise
  pattern and per-vertex colours break up the terrain. A sky dome and height fog close the horizon.
- A warm key light, cool fill and captured sky light make the geometry readable.

The HUD leaves the central viewport for the environment. Its lower cards contain the frozen
report, allocated samples/actual intervention temperatures, and control/treatment response
traces. Scientific numbers come from the existing public observation schema.

## Viewing

```powershell
.\scripts\Run-XenoUnreal.ps1 -Mode Packaged -View Overview
.\scripts\Run-XenoUnreal.ps1 -Mode Packaged -View Rover
```

Hold RMB and drag to orbit, scroll to zoom, A/D to turn, R to reset. Camera movement never
changes a sample, mission budget or scientific clock. The two presets support repeatable
visual checks without moving the rover outside the service protocol.

## Boundaries

This remains an F0 token-model demonstration. The terrain is an artistic setting; it is not a
geochemical or planetary model. Visual height placement is not vehicle physics, and the rover's
scientific movement still uses the common point-navigation controller. No camera image is yet
submitted as a budgeted instrument observation. The scene name is fictional.

Build checks, live mission checks and inspected captures are recorded in the local `runs/`
directory. Neither private sessions nor generated packages are intended for source commits.

## Verified build

The full Windows package was rebuilt with the terrain, rover, materials and HUD. Packaged
smoke, overview and rover-view runs each passed at revision 6 with seven stream events.
Both camera views retained the same scientific cost ledger; the numerical core is unchanged.

- Overview capture: `runs/unreal-Packaged-20261022T1340162426031Z/preview.png`.
- Rover capture: `runs/unreal-Packaged-20261022T1340518215679Z/preview.png`.
- Consolidated checks and hashes: `runs/environment-verification/verification.private.json`.

Both 1280 by 800 captures were visually inspected. They show shaded terrain and rocks,
readable instrument cards, sample markers and the detailed rover. This is a stylized
procedural environment; it does not represent a photorealistic planetary reconstruction.
