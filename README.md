# KDX Resolution

Resolution toolkit for ComfyUI: pick the right width × height for a model, turn an aspect ratio
(from a prompt, an LLM answer or a list) into a size on the model's grid, and step / scale / snap
sizes without breaking the aspect ratio.

- **12 nodes** in **KDX/Resolution**, all headless (numbers and text in, numbers and text out).
- **28 model profiles** (Qwen-Image, Flux, Flux-2, FLUX 3 Klein, Krea 2, MiniMax H3, SDXL, SD 1.5 / 3.5,
  Z-Image, Wan 2.2, LTX, HunyuanVideo, MOVA, Mochi, CogVideoX, SVD, AnimateDiff …) with native sizes,
  grid and size limits, most checked against the makers' official tables.
- **Exact-ratio solver**: computed sizes keep the exact ratio whenever the grid allows it.
- **Result box** in every node: which size you get and why, updated while you edit.
- Works with [KDX Wildcard Studio](https://github.com/korodexios/ComfyUI-KDX-Wildcard-Studio) and
  [KDX LLM](https://github.com/korodexios/ComfyUI-KDX-LLM): aspect ratio from a template or an LLM JSON
  answer straight into the model's size.
- **Standard library only**: no `pip install`, Python 3.10+.

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/korodexios/ComfyUI-KDX-Resolution.git
# restart ComfyUI
```

Update: `git pull` in that folder, restart ComfyUI, reload the browser tab (Ctrl+F5).

## Which node do I need?

| I want to… | Node |
|---|---|
| choose a size from the model's official list | 📑 Preset Picker |
| aspect ratio (+ optional megapixels) → W×H for a model | 🎯 AutoRes Core |
| W×H for a ratio and megapixels, no model | 🧮 Megapixel Selector |
| ratio from an LLM JSON answer, text or `--ar 16:9` | 🔎 AR Extractor / 🧾 Prompt Extractor |
| try a prompt in several ratios | 🎲 AR Batch Tester |
| check, label or snap a size | ✅ AR Validator, ↔️ Reverse AR Matcher, 🧲 Nearest Native Preset |
| bigger / smaller with the same ratio, hires-fix size | 📶 Resolution Step, 📏 Resolution Scaler |
| W×H as text | 🔗 Resolution → String |

## Documentation

| | |
|---|---|
| [Quick start](docs/01-quick-start.md) | install, first size, the result box |
| [Nodes](docs/02-nodes.md) | every node: inputs, outputs, examples |
| [Model profiles and presets](docs/03-model-profiles.md) | all profiles, your own preset lists, hiding models |
| [With KDX Wildcard Studio and KDX LLM](docs/04-kdx-packs.md) | aspect ratio from JSON, Prompt Extractor |
| [Example workflows](docs/05-example-workflows.md) | the four workflows in `example_workflows/` |
| [Development](docs/06-development.md) | tests, code layout, rules for changes |

## License

MIT — see [LICENSE](LICENSE).
