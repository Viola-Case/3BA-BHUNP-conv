# 3BA → BHUNP Texture Converter

Converts Skyrim body skin textures authored for the **3BA (3BBB Amazing)** body so they line up
with the **BHUNP** body's UV layout. Point it at a folder of `.dds` textures and it writes a
matching folder of BC7-compressed `.dds` textures, preserving subfolder structure.

The transfer is done by baking: the 3BA mesh is rendered with the source texture as pure emission,
and Cycles projects that onto the BHUNP mesh's UVs. This means the result is correct wherever the
two bodies occupy the same space, rather than being a naive UV remap.

## Requirements

| Tool | Purpose | Notes |
|---|---|---|
| [Blender](https://www.blender.org/) | runs the bake | 2.9x or newer; developed against 5.1 |
| [ImageMagick](https://imagemagick.org/) (`magick`) | DDS↔PNG, alpha merge | v7 (the `magick` command, not `convert`) |
| [texconv](https://github.com/microsoft/DirectXTex/releases) | final BC7 compression | from DirectXTex |

All three must be on `PATH`, or passed explicitly via `-Blender`, `-Texconv`, and `-BlendFile`.

A GPU is strongly recommended. The bake is a single-sample texel transfer, but at 4K texture sizes
CPU baking is slow.

## Usage

```powershell
.\batch_bake.ps1 -InputDir "C:\path\to\3BA textures" -OutputDir "C:\path\to\output"
```

Every `.dds` found recursively under `-InputDir` is converted, and the relative path is mirrored
into `-OutputDir`. Existing output files are overwritten.

### Parameters

| Parameter | Default | |
|---|---|---|
| `-InputDir` | *(required)* | folder to scan recursively for `.dds` |
| `-OutputDir` | *(required)* | destination; also holds the scratch `temp\` folder during the run |
| `-BlendFile` | `.\conversion.blend` | scene holding both bodies and the bake materials |
| `-Script` | `.\Conversion_Script.py` | the bake script Blender runs |
| `-Blender` | `blender` | path to the Blender executable |
| `-Texconv` | `texconv` | path to texconv |

### Converting a single texture

Skip the batch script and drive Blender directly. It takes a PNG in and writes the colour and
alpha passes as two separate PNGs:

```powershell
magick input.dds src.png
blender --background --factory-startup .\conversion.blend --python .\Conversion_Script.py -- src.png diff.png alpha.png
magick diff.png ( alpha.png -colorspace gray ) -compose CopyOpacity -composite merged.png
```

## How it works

For each texture:

1. **`magick`** converts the source `.dds` to PNG. Blender cannot load every Skyrim DDS variant
   reliably, so this normalises the input.
2. **Blender** bakes twice — once with the source image's Colour output wired to the emission
   surface, once with its Alpha output. Two passes are needed because the bake path cannot carry
   an alpha channel through in one go, so the passes land in separate files.
3. **`magick`** recombines them, using the alpha bake as the merged image's alpha channel.
4. **`texconv`** compresses to `BC7_UNORM` with no mipmaps (`-m 1`) and writes the final `.dds`.

The scratch `temp\` folder inside `-OutputDir` is deleted when the run finishes.

## GPU selection

`Conversion_Script.py` probes for a working Cycles backend at startup, trying **OPTIX → CUDA →
HIP → ONEAPI → METAL** and taking the first one that both exists in the Blender build and reports
an actual device. It prints what it picked:

```
Device: OPTIX available but no devices found, skipping
Device: CUDA available but no devices found, skipping
Device: HIP -> AMD Radeon RX 7900 XT
```

If nothing usable is found it falls back to CPU and says so. To override the probe, set
`BAKE_DEVICE` to one of the backend names, or to `CPU`:

```powershell
$env:BAKE_DEVICE = "CPU"; .\batch_bake.ps1 -InputDir ... -OutputDir ...
```

Only the chosen backend's GPUs are enabled for the bake; the CPU is not mixed in.

## The .blend file

`conversion.blend` is not a scratch scene — it *is* the configuration. `Conversion_Script.py`
builds nothing and instead looks up objects, materials, nodes, and images by hardcoded name, so
renaming anything inside the scene breaks the script with a `KeyError`. The expected names are
listed in [CLAUDE.md](CLAUDE.md).

The two bodies must also stay spatially aligned, since the bake projects from the source surface
onto the destination surface by proximity.

## Troubleshooting

**`KeyError: 'bpy_prop_collection[key]: key "..." not found'`** — a datablock in `conversion.blend`
was renamed or deleted. Compare against the name table in CLAUDE.md.

**Output is fully transparent** — the alpha pass baked black. Check that the `Source Image` node's
second output really is Alpha; the pass index in the script is the socket index.

**`magick` not recognised** — ImageMagick v6 installs as `convert`, not `magick`. Install v7.

**Bake is extremely slow** — check the `Device:` line in the output. If it says it fell back to
CPU, the GPU driver isn't visible to Blender.

## Repository contents

- `batch_bake.ps1` — the driver you want
- `Conversion_Script.py` — headless Blender bake script
- `conversion.blend` — scene with both bodies, materials, and bake targets
- `BATCH_CONVERSION.ps1` — earlier driver, superseded. Hardcodes absolute paths and writes PNG
  data under a `.dds` filename with no compression step. Kept for reference only.

## License

MIT — see [LICENSE](LICENSE). Use it, modify it, ship it, sell it; the only requirement is that
the copyright notice and licence text travel with any substantial portion of the code.

This covers the scripts and the `.blend` file in this repository only. Textures you run through
it stay under whatever terms their original author set — converting a texture does not change
who owns it, so check the source mod's permissions before redistributing output.
