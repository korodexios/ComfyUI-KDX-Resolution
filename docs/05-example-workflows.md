# 05 Example workflows

The pack ships four small workflows in [`example_workflows/`](../example_workflows). In ComfyUI open
**Templates** → custom nodes → **ComfyUI-KDX-Resolution**, or drag a `.json` file onto the canvas.
They use only KDX Resolution and core nodes and need no model: queue them and read the Preview nodes.
To make images, connect the latent output to your own sampler.

## 1 Preset picker to latent

*KDX Resolution - 1 preset picker to latent.json*

📑 Preset Picker (SDXL, `SDXL | ~16:9 | 1344x768`) → `width` / `height` → Empty Latent Image;
`label` → Preview.

Shows: the simplest way to a model's native size. Try `orientation` = *portrait* (768 × 1344) or
`scale` = 1.5. Node details: [Preset Picker](02-nodes.md#-preset-picker).

## 2 LLM JSON aspect ratio to latent

*KDX Resolution - 2 LLM JSON aspect ratio to latent.json*

🔎 AR Extractor (`json`, key `aspect_ratio`, input `{"prompt": "a lighthouse in a storm", "aspect_ratio": "21:9"}`)
→ `extracted_ar` → 🎯 AutoRes Core (Flux (dev/schnell), 1 MP) → Empty Latent Image; `info` → Preview.

Result: 1568 × 672, `info` = `lattice solve @ 1 MP (exact 21:9)`. Flux has no native 21:9 size, so
AutoRes Core computes one on Flux's /16 grid.

Shows: the hand-off from an LLM. Replace the text widget with a wire from KDX LLM Chat's `response`
to make it live; for the full Wildcard Studio → LLM chain with the 🧾 Prompt Extractor see
[04 With KDX Wildcard Studio and KDX LLM](04-kdx-packs.md).

## 3 Megapixels, size steps and hires scale

*KDX Resolution - 3 megapixels, size steps and hires scale.json*

🧮 Megapixel Selector (16:9, 1 MP, grid 16) → 1280 × 720, then two branches:

- 📶 Resolution Step (jump, 2, up, SDXL) → 1792 × 1008 → 🔗 Resolution → String → Preview;
- 📏 Resolution Scaler (× 1.5, grid 16) → 1920 × 1088 → 🔗 Resolution → String → Preview.

Shows: a size from megapixels without a model table, a bigger size with the same ratio, and the size
for a hires-fix pass.

## 4 Test several aspect ratios

*KDX Resolution - 4 test several aspect ratios.json*

🎲 AR Batch Tester (`1:1, 3:2, 2:3, 16:9, 9:16`, Sequential, seed *increment*) → 🎯 AutoRes Core
(SDXL) → Empty Latent Image, and the size as text → Preview.

Queue five times: 1024 × 1024, 1216 × 832, 832 × 1216, 1344 × 768, 768 × 1344.

Shows: one prompt in several formats; put your sampler after the latent to compare them.
