# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A texture conversion pipeline that transfers Skyrim body skin textures from the **3BA** body mesh's UV layout to the **BHUNP** body mesh's UV layout. It is not an application — it is three coupled artifacts (a Blender scene, a headless Blender Python script, and a PowerShell batch driver) plus external CLI tools.

## Running a conversion

```powershell
# Current driver (relative paths, BC7-compressed .dds output)
.\batch_bake.ps1 -InputDir <dir of 3BA .dds> -OutputDir <dir>

# Single file, no batching — drive Blender directly
blender --background --factory-startup .\conversion.blend --python .\Conversion_Script.py -- <src.png> <diff_out.png> <alpha_out.png>
```

External tools that must be on PATH: `blender`, `magick` (ImageMagick), `texconv` (DirectXTex). `-Blender`, `-Texconv`, `-BlendFile`, `-Script` params override each.

To test one texture without touching the batch script, convert the `.dds` to `.png` with `magick` yourself and run the Blender line above — `Conversion_Script.py` only ever handles a single input.

## Pipeline stages

Per source `.dds`, `batch_bake.ps1` runs:

1. `magick` — source `.dds` → `_src.png` (Blender cannot load all Skyrim DDS variants reliably)
2. Blender headless bake → `_diff.png` + `_alpha.png` (two separate files; the bake path cannot carry alpha through)
3. `magick ... -compose CopyOpacity -composite` — recombine alpha into `_merged.png`
4. `texconv -f BC7_UNORM -bc x -m 1` — `_merged.png` → final `.dds`, moved over `$outFile`

Directory structure under `-InputDir` is mirrored into `-OutputDir`; the temp dir (`$OutputDir\temp`) is deleted wholesale at the end.

## The .blend file is the interface

`Conversion_Script.py` contains **no scene construction** — it looks up datablocks by hardcoded name inside `conversion.blend`. Renaming anything in the scene silently breaks the script with a `KeyError`. The contract is:

| Kind | Name | Role |
|---|---|---|
| Object | `3BA_full` | source mesh (selected) |
| Object | `BHUNP_full` | destination mesh (active) |
| Material | `Source` | on `3BA_full`; its Material Output is rewired per pass |
| Material | `Destination` | on `BHUNP_full`; holds the bake targets |
| Node (in `Source`) | `Source Image`, `Material Output` | image texture; output 0 = Color, 1 = Alpha |
| Node (in `Destination`) | `Diffuse Bake Image`, `Alpha Bake Image` | Image Texture nodes selected as active bake target |
| Image | `Source Image Data`, `Bake Diff`, `Bake Alpha` | datablocks whose pixels/filepaths the script drives |

The transfer works by `bpy.ops.object.bake(type='EMIT', use_selected_to_active=True)` — the source's emission is projected onto the destination's UVs by proximity, so the two meshes must remain spatially aligned in the .blend.

Each `bake_pass` rewires `Source Image.outputs[socket_index]` straight into `Material Output.Surface`, so the pass index (0 diffuse, 1 alpha) *is* the socket index. Any change to the node's socket ordering changes the meaning of those arguments.

## Bake settings and hardware

`select_bake_device()` probes OPTIX → CUDA → HIP → ONEAPI → METAL and takes the first backend that exists in the build *and* reports a device, printing a `Device:` line either way. `BAKE_DEVICE=<backend>|CPU` overrides it.

Two Cycles API quirks the probe works around — both verified against Blender 5.1, don't "simplify" them back:

- `compute_device_type`'s enum is filled by a dynamic callback, so `bl_rna.properties[...].enum_items` is **empty**. The only reliable support test is attempting the assignment and catching `TypeError`.
- `prefs.devices` lists every detected device regardless of the selected backend (an AMD card shows up while `compute_device_type == 'OPTIX'`). Use `get_devices_for_type(backend)`, then still filter by `d.type == backend` — it includes the CPU too.

`samples = 1` and denoising off are deliberate — this is a straight texel transfer, not a lighting bake.

## `BATCH_CONVERSION.ps1` vs `batch_bake.ps1`

`BATCH_CONVERSION.ps1` is the earlier driver and is superseded: it hardcodes absolute paths into `E:\Tools\Skin Texture Resources\`, uses `$env:TEMP\bake_temp`, and — notably — writes **PNG data under a `.dds` filename** with no compression step. Prefer `batch_bake.ps1`; only touch the old one if asked specifically.

## Repo notes

- `.gitignore` excludes `textures/` and `TestBake/` (working data dirs, currently empty) and `__pycache__/`.
- `__pycache__/xNormal.cpython-311.pyc` is left over from a removed xNormal-based approach; no source for it remains.
- `conversion.blend1` is Blender's automatic backup of the previous save, not a variant scene.
