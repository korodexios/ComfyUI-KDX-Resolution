# 01 Quick start

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/korodexios/ComfyUI-KDX-Resolution.git
# restart ComfyUI
```

No `pip install`: the pack uses the Python standard library only (Python 3.10+).

Update: `git pull` in that folder, restart ComfyUI, then reload the browser tab (Ctrl+F5) so the
editor loads the new frontend files.

All nodes are in the node menu under **KDX/Resolution** (or search for "KDX").

## Your first size in 30 seconds

1. Add **📑 KDX • Preset Picker**.
2. `model` → e.g. *SDXL*; `preset` → *SDXL | ~16:9 | 1344x768*.
3. Connect `width` and `height` to **Empty Latent Image** (right-click the latent node → convert
   width/height to inputs if your ComfyUI version needs it).

That is the official 16:9 size SDXL was trained on. The same graph ships as
[example workflow 1](05-example-workflows.md#1-preset-picker-to-latent).

When the aspect ratio comes from somewhere else (a prompt, an LLM answer, a list), use
**🎯 KDX • AutoRes Core** instead: it turns `16:9` into the model's size for that ratio.

## Which node do I need?

| I want to… | Node |
|---|---|
| choose a size from the model's official list | 📑 **Preset Picker** |
| turn an aspect ratio (+ optional megapixels) into W×H for a model | 🎯 **AutoRes Core** |
| W×H for an aspect ratio and megapixels, no model | 🧮 **Megapixel Selector** |
| read the aspect ratio from an LLM JSON answer, text or `--ar 16:9` | 🔎 **AR Extractor** → 🎯 AutoRes Core |
| pull ratio, size, a key's value and the clean prompt out of any text | 🧾 **Prompt Extractor** → 🎯 AutoRes Core |
| try a prompt in several aspect ratios | 🎲 **AR Batch Tester** → 🎯 AutoRes Core |
| check that an aspect ratio is allowed | ✅ **AR Validator** |
| get the ratio label of a size (1920×1080 → 16:9) | ↔️ **Reverse AR Matcher** |
| snap any size to the model's closest official size | 🧲 **Nearest Native Preset** |
| go 1–N sizes up/down with the same ratio | 📶 **Resolution Step** |
| scale for a hires-fix pass (×1.5, rounded to the grid) | 📏 **Resolution Scaler** |
| W×H as `"1920x1080"` text | 🔗 **Resolution → String** |

Details for each node: [02 Nodes](02-nodes.md).

Node colours: green = produces a size, purple = works with aspect-ratio text, blue = changes a size.

## What size will I get? — the result box

Every node has a read-only box at the bottom that tells you the result and why:

```
📐 1600 × 688 px   ·   ~21:9   ·   1.05 MP
✔ custom table 21:9
⚠ custom_table line(s) not understood: '16:9 1920' (format 'W:H = width, height')
🗂 custom table: ▶ 21:9 = 1600×688, 1:2 = 1024×2048
ℹ Flux (dev/schnell): grid /16, sides 256–4096 px, trained ~1 MP
— preview (updates as you edit)
```

- It updates **while you edit**, no need to run. Values that come from another node are only known
  during a run: the box then says so and shows the last run's result.
- ✔ = the rule that produced the size (native table, custom table, lattice solve …), ↪ = a fallback
  was used, ⚠ = something to check (unreadable custom-table lines, a size far above what the model was
  trained for, limits), ▶ marks the custom-table entry that was used.
- The left edge shows the state: green = size found, amber = ⚠ note or ↪ fallback, red = error,
  grey = waiting for an input from another node.
- AutoRes Core's `info` output carries the same explanation as text.

Hover an input or output for its tooltip; the node info panel shows a short description.

## Bypassed or unconnected inputs

A `width` / `height` of `0` (a bypassed or unconnected input) counts as 1024. An empty aspect-ratio
text uses the node's fallback ratio. A workflow therefore never stops just because an upstream node
is muted.
