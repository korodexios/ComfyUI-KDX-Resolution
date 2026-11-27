# Changelog

## 0.6.7 - 2026-11-27

### Added
- **My model profiles**: a built-in profile with your own size table (grid, size limits and ~MP stay
  the model's). Make them in a small editor (right-click a KDX Resolution node → *KDX: ★ my model
  profiles…*, or Extensions → KDX Resolution): one size per line (`16:9 = 1376x768` or `1376x768`),
  checked live with errors per line. They appear in every model dropdown as `★ <name>` right after
  saving. Stored in `<user dir>/kdx_resolution/my_profiles.json`; a rename keeps old workflows working.

### Fixed
- Model and preset dropdowns lost new entries after a node-definition refresh (R) when the model
  filter had run on them before.

## 0.6.6 - 2026-11-27

### Changed
- **Krea 2 (turbo/raw)** now uses Krea's official Krea 2 Turbo size table (~1 MP): 1:1 1024×1024,
  4:3 1184×896, 3:2 1248×832, 16:9 1376×768, 7:3 ("2.35:1") 1568×672, 4:5 928×1152, 2:3 832×1248,
  9:16 768×1376. The profile is marked official, ~MP is 1. The earlier computed 2K sizes and the
  unlisted mirrors (3:4, 5:4, 3:7) stay available as extra buckets.

## 0.6.5 - 2026-11-26

### Added
- `docs/`: user guide in English (quick start, every node with inputs, outputs and examples, model
  profiles and preset lists, working with KDX Wildcard Studio and KDX LLM, example workflows,
  development).
- GitHub workflow to publish to the Comfy Registry when a release is published.

### Changed
- README is short and links to the docs; the generated model table moved to
  `docs/03-model-profiles.md` (`tools_dev/build_model_table.py`).
- Registry display name is "KDX Resolution".

### Fixed
- CI lint: two tooltip lines were longer than 120 characters.

## 0.6.4 - 2026-11-24

### Changed
- `model_list` now sits right above the model dropdown (AutoRes Core, Preset Picker, Nearest Native
  Preset, Resolution Step) instead of at the bottom, and is a required input. **Breaking:** workflows
  saved before 0.6.4 load these four nodes with shifted widget values; re-pick the settings once.

## 0.6.3 - 2026-11-24

### Added
- **MiniMax H3 Image** profile (image, /32): the official ~16 MP table (1:1 4096×4096 … 21:9 6272×2688),
  up to ~19 MP (API limit 20 M px), 5:4 / 4:5 and the ~4 MP "2K" tier as extra buckets.

## 0.6.2 - 2026-11-23

### Changed
- Accent colour is now the KDX blue shared by every KDX pack (dark #6f8dff, light #2f4fd1); green stays
  the colour of a finished / OK state.
- The result box keeps its green left edge for a found size (now its own OK colour, not the accent).

## 0.6.1 - 2026-11-23

### Changed
- Node icons unique across the KDX packs: 📑 Preset Picker, 🧮 Megapixel Selector, 🧾 Prompt Extractor,
  ↔️ Reverse AR Matcher. Only the display names changed; workflows keep working.

## 0.6.0 - 2026-11-19

### Changed
- The result box uses the KDX Console / KDX LLM look: green accent, light/dark tokens that follow the
  ComfyUI palette. Its left edge shows the state: green = size found, amber = ⚠ note or ↪ fallback,
  red = error, grey = waiting for an input from another node. Node role colours are unchanged.

### Added
- **Prompt Extractor** node: finds an aspect ratio, a resolution (`1920x1080`, `1920*1080`) and/or the
  value of a custom key in any text, including broken JSON. `--ar` / `--size` markers win, otherwise
  `pick` first/last. Optional `remove_found` (off by default) deletes the found items from the prompt.
  The AR Extractor is unchanged.

## 0.5.0 - 2026-11-15

### Added
- New model profiles: **Krea 2 (turbo/raw)**, **FLUX 3 Image Klein**, **LTX 2.5**, **HunyuanVideo 1.5** and
  **MOVA (OpenMOSS, video+audio)** — 27 profiles in total. Krea 2: 1024–2048 px on a /16 grid, 2K sizes
  computed for Krea's ratios (Krea publishes no size table).
- **`model_list`** (all / image / video models) on AutoRes Core, Preset Picker, Nearest Native Preset and
  Resolution Step: the model dropdown offers only that kind. It is the node's last setting so older
  workflows keep their values; it does not change results.
- Right-click a KDX-Resolution node → **KDX: choose visible models…** opens Settings → KDX Resolution.
- README model table is generated from the profiles (`tools_dev/build_readme_models.py`).

## 0.4.0 - 2026-11-15

### Added
- **Result box in every node**: a read-only box at the bottom says which size you get
  (W × H, ratio, MP), which rule produced it (✔ native table, custom table, lattice …, ↪ fallback),
  ⚠ warnings and the model's limits.
  - Updates **while you edit** — no need to run the workflow.
  - After a run it shows the run's result; values coming from another node are shown after the run.
  - Not saved in the workflow, so existing workflows are unchanged.
- AutoRes Core: `custom_table` lines that cannot be read are reported (box and `info`), and the box
  lists all custom entries with ▶ on the one that was used.

### Fixed
- `matched_ar` keeps the ratio as written ("21:9") instead of the reduced form ("7:3").

## 0.3.0 - 2026-11-14

### Changed
- **Model sizes checked against the makers' official tables** (each profile now shows whether its sizes
  are official, with a source link — see the README model table):
  - Wan 2.2 (A14B): 1280×720, 720×1280, 832×480, 480×832 (768×768 and 960×736 were not official sizes).
  - Hunyuan Video: official 720p sizes (1280×720, 1104×832, 960×960 …) plus the 540p sizes.
  - CogVideoX 5B: 720×480 only, up to 49 frames. Mochi 1: 848×480, frames 6n+1 (now listed everywhere).
  - Z-Image: official 1 MP table (e.g. 3:2 = 1248×832, 16:9 = 1280×720, 21:9 = 1344×576).
  - Flux-2: default 1024×1024 (~1 MP table, as BFL recommends), 2–4 MP sizes as extra presets.
  - LTX 2.3: sizes divisible by 32 (1280×704, 1920×1088), up to 257 frames. SVD: 1024×576.
  - These change what AutoRes Core returns with `target_megapixels = 0` for those models.
- `Qwen-Image (2.0/edit)` is now called `Qwen-Image (2512/edit)`; the old name keeps working.

### Added
- **Settings → KDX Resolution**: switch off models you don't use, or show only image / only video
  models, in all KDX-Resolution model dropdowns. Saved workflows are not affected.
- New profiles **Wan 2.2 TI2V-5B** (1280×704) and **CogVideoX 1.5 5B** (1360×768).
- AutoRes Core warns in `info` when `target_megapixels` is far above what the model was trained for
  (e.g. SDXL at 50 MP) and caps Flux-2 / Z-Image at their 4 MP maximum.
- README model table: grid, recommended megapixels, native sizes, frame rules and sources.

## 0.2.0 - 2026-11-14

First tagged release. Saved workflows keep working: no input was renamed, reordered or removed.

### Fixed
- **AutoRes Core / Megapixel Selector**: a target above the model's maximum size returned the *smallest*
  size (SDXL @ 50 MP → 256×256); now the largest size that fits.
- **AutoRes Core / Megapixel Selector**: ratios such as 1366×768 (683:384) returned 8192×8192 or
  4096×4096 "UNRESOLVED"; now the nearest grid size with ≤ 1.5 % ratio error.
- **AutoRes Core**: `32:18`, `1920x1080`, `16/9` now match the model's native 16:9 entry.
- **AutoRes Core**: the nearest native size is chosen by aspect ratio (Wan 2.2: 2:1 gave 4:3, now 16:9).
- **AutoRes Core**: no false "AR drift" note on official native sizes.
- **AutoRes Core**: the default `custom_table` no longer adds `21:9 = 3072, 1312` to every model
  (new nodes only; saved workflows keep their text — delete those two lines there if you never meant them).
- **AutoRes Core**: `0x0` / invalid `direct_override` is ignored instead of output.
- **AutoRes Core**: an invalid `ar_input` uses `fallback_ar` through the whole chain and honours
  `target_megapixels` (it used to give a base-size square labelled with the fallback ratio).
- **AutoRes Core / Megapixel Selector**: `mp_grid` entries are re-solved for the requested ratio, as the tooltip said.
- **AR Batch Tester**: removed `IS_CHANGED = NaN`, which re-ran every downstream node (e.g. the sampler)
  on each queue even with the same seed.
- **Resolution Step**: messy ratios use the closest simple ratio (1366×768 → 16:9 steps instead of 4096×4096);
  jumps stop at the last size that fits instead of breaking the ratio; `auto` grid divides the input size.
- **AR Extractor**: finds JSON inside prose, supports list indices in `key` (`shots.0.ar`) and values like
  `16:9 (widescreen)`; `0:5` is not accepted as a ratio.
- **AR Validator** compares reduced ratios (`32:18` = `16:9`); **Reverse AR Matcher** treats portrait and
  landscape symmetrically.
- **Preset Picker**: a saved preset that is no longer in the list (custom list removed, other machine)
  no longer fails with "Value not in list"; a broken custom JSON file no longer breaks the node.
- Profile `Z-Image (turbop/base)` renamed to `Z-Image (turbo/base)`; the old name still works.

### Added
- Own preset lists in `kdx_custom_presets.local.json` (not tracked by git, so `git pull` never conflicts).
- Node descriptions (node info panel), tooltips on every input and output, search aliases.
- Node colours by role: green = produces a size, purple = aspect-ratio text, blue = changes a size.
- Four example workflows under Templates → ComfyUI-KDX-Resolution.
- Test suite (67 tests, stdlib `unittest`) and GitHub Actions CI (ruff + Python 3.10–3.13).

### Changed
- Menu category `KDX_Resolution` → `KDX/Resolution`; shorter node titles with one icon each.
- Code split from one 1600-line `__init__.py` into the `kdx_resolution/` package.
- README rewritten to match the actual nodes.
