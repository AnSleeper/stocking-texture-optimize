# stocking-texture-optimize

> An AI **Skill** for adding/refining stocking (pantyhose) fabric texture in illustrations. Send an image to your AI agent; it segments the stocking areas, shows you a mask preview for confirmation, then renders 6 texture styles in one go.

This repo is a `SKILL.md` + automation scripts package for AI agents such as Trae or Claude Code.
The actual renderer is the open-source [stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool).
Everything runs locally — no network, no uploads.

---

## ⭐ Meet the renderer: stocking-texture-tool

This skill is just the "autopilot" — the real work is done by the open-source **Stocking Texture Tool**
([stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool)), created by Bilibili creator
**纯银碎月** (GitHub: [@silvermoong](https://github.com/silvermoong)). MIT licensed, free.

- Project: https://github.com/silvermoong/stocking-texture-tool
- Author's video introduction (Chinese): [《轻松提升丝袜的绘画质感：丝袜纹理工具（开源免费）》](https://www.bilibili.com/video/BV1tkpW63EC6)

It adds **computed** fabric texture to stockings in illustrations — the texture is geometrically calculated, not painted by generative AI. Select the stocking regions, draw a few direction lines across the weave, and the tool computes how the texture wraps around the legs and body, then renders it in the chosen style.

Highlights (from the author's introduction):

- Click to segment a leg with three size tiers; brush and eraser for edge touch-up
- 1–3 direction lines fill the weave in a second; mirror them to the other side
- Divider lines and knee arcs for bent legs; tops can be split and auto-separated left/right
- Styles: fine lines, knit, coil, diagonal lines, Kase-style grain, oily (experimental)
- Density / strength / tilt / sparkle parameters; auto strength for black & white stockings; live preview
- No moiré in exported pixels
- Exports: final image, transparent stocking layer PNG, re-editable guide PSD; originals never modified
- Fully local after install — nothing is uploaded

Install (Windows 10 / 11; NVIDIA GPU faster, CPU works too): download the repo, double-click `install.bat` (a desktop shortcut appears); run it again to update. Offline install packages: [releases/deps-1](https://github.com/silvermoong/stocking-texture-tool/releases/tag/deps-1).

> **Install it first — this skill can do nothing without it.** Consider starring the author's repo.

---

## Features

- **Automatic segmentation** — reuses the already-loaded Segment Anything model, scoring candidates by "vertical, elongated, moderately sized, dark"
- **Confirm before render** — only a mask preview (numbered regions + click crosses) is produced first
- **6 styles at once** — fine lines, knit, coil, diagonal lines, Kase-style grain, oily
- **Black or white stockings** — strength is auto-tuned to the stocking's brightness
- **Per-task output folders** — original, finals, and intermediates kept separate
- **Manual fallback** — generates a coordinate grid image when image viewing is blocked

## Requirements

| Item | Requirement |
|---|---|
| OS | Windows 10 / 11 |
| Renderer | [stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool) installed |
| Python | Use the tool's bundled `.venv` |
| GPU | NVIDIA recommended, CPU also works |

## Install

1. **Install the renderer** — download the upstream repo, run `install.bat`, wait for dependencies and models.
2. **Place this skill** — copy this repo into your AI's skills directory, e.g.
   `<project>/.trae/skills/stocking-texture-optimize/`, then restart the AI session.
   Or grab the packaged zip (includes a Chinese quick-start for recipients) from
   [Releases](https://github.com/AnSleeper/stocking-texture-optimize/releases).
3. **Patch the read-only probe endpoint** (once):

   ```powershell
   & "<tool dir>\.venv\Scripts\python.exe" "<skills dir>\stocking-texture-optimize\scripts\patch_probe.py" "<tool dir>"
   ```

   Idempotent, backs up `server.py`, reuses the loaded SAM (no extra VRAM). Restart the tool service afterwards.

4. **Tell the scripts where the tool lives** — one of:
   - env var `STOCKING_TOOL_DIR`
   - `--tool-dir "<tool dir>"`
   - `scripts/tool_dir.txt` (first line = tool dir)

## Usage

Send an image to your AI and say: *"refine the stocking texture on this image"*.
It will show a mask preview first, then render all 6 styles after you confirm.

CLI:

```powershell
$py = "<tool dir>\.venv\Scripts\python.exe"
$s  = "<skills dir>\stocking-texture-optimize\scripts\auto_stocking.py"

# Step 1 — mask preview only
& $py $s "image.png" --points "400,800,0;1200,600,0" --preview

# Step 2 — render all 6 styles with the same points
& $py $s "image.png" --points "400,800,0;1200,600,0"
```

Point syntax: `x,y[,k][+x,y[,k]]*[;...]`
- `;` separates regions; `+` merges multiple points into the same region
- `k` = SAM tier: `0` small / `1` medium / `2` large

Output layout:

```
<tool dir>/工作目录/产物/<input filename>/
├── 原图.png
├── 丝袜质感优化_细线.png ... (6 styles)
└── temp/  (grid, masks, previews)
```

## Parameters

`--style`, `--density`, `--strength`, `--no-auto-strength`, `--grow`, `--out`, `--name`, `--preview`, `--port`.
See [references/api-and-params.md](references/api-and-params.md) for the full list and REST API.

## FAQ

- **Inaccurate auto-detection** → confirm via mask, or use `grid_image.py` and report coordinates.
- **A leg not fully covered** → lower the tier and merge extra points with `+`; avoid max tier on adjacent regions.
- **"SAM probe unavailable"** → re-run `patch_probe.py` and restart the service.
- **Out of VRAM** → never load a second SAM instance; the probe reuses the loaded one.

## Upstream & License

Renderer: [silvermoong/stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool) (MIT), created by Bilibili creator **纯银碎月** ([@silvermoong](https://github.com/silvermoong)) —
[video introduction](https://www.bilibili.com/video/BV1tkpW63EC6). All rendering capability is theirs; this repo is workflow automation on top.
SAM: Meta (Apache-2.0). Depth Anything V2 Small: Apache-2.0.

This repo contains only workflow scripts and docs. Licensed under [MIT](LICENSE).
