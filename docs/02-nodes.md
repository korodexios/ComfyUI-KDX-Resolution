# 02 Nodes

Twelve nodes, all in **KDX/Resolution**. They are headless: numbers and text in, numbers and text out,
no images or tensors. Every input and output has a tooltip in the editor.

- [📑 Preset Picker](#-preset-picker)
- [🎯 AutoRes Core](#-autores-core)
- [🧮 Megapixel Selector](#-megapixel-selector)
- [🔎 AR Extractor](#-ar-extractor)
- [🧾 Prompt Extractor](#-prompt-extractor)
- [✅ AR Validator](#-ar-validator)
- [🎲 AR Batch Tester](#-ar-batch-tester)
- [↔️ Reverse AR Matcher](#️-reverse-ar-matcher)
- [🧲 Nearest Native Preset](#-nearest-native-preset)
- [📶 Resolution Step](#-resolution-step)
- [📏 Resolution Scaler](#-resolution-scaler)
- [🔗 Resolution → String](#-resolution--string)

Aspect ratios are accepted as `16:9`, `16/9`, `16x9`, `1920x1080` or `32:18`; they are reduced before
use, so `32:18` and `1920x1080` both mean `16:9`.

---

## 📑 Preset Picker

`KDX_Preset_Picker` — pick a model, then one of its native sizes. The easiest way to get a correct
size for a model.

| Input | Meaning |
|---|---|
| `model_list` | *all models* / *image models* / *video models*: which models the `model` list offers |
| `model` | model profile (or one of your own lists); filters the `preset` list |
| `preset` | `Model \| AR \| WxH`, e.g. `SDXL \| ~16:9 \| 1344x768` |
| `orientation` | *as listed*, *landscape* or *portrait*: swaps W and H when needed |
| `scale` | `1.0` = the preset as listed; anything else scales it and rounds to the model grid |

| Output | Meaning |
|---|---|
| `width`, `height` | the size |
| `ar_string` | ratio label, e.g. `16:9` or `~16:9` (within 3 %) |
| `actual_mp` | W × H / 1024² |
| `label` | `Model \| WxH`, handy for notes or file names |

Example: *SDXL | ~16:9 | 1344x768*, orientation *portrait*, scale 1.5 → `1152 × 2016`, `~9:16`,
2.21 MP, label `SDXL | 1152x2016`.

A saved preset that no longer exists in the list (another machine, another version) still works as
long as it contains a `WxH` size. Your own lists: [03 Model profiles](03-model-profiles.md#your-own-preset-lists).

---

## 🎯 AutoRes Core

`KDX_AutoResolution_Core` — the main resolver: aspect ratio (+ optional target megapixels) → width
and height on the model's grid.

| Input | Meaning |
|---|---|
| `ar_input` | aspect ratio, usually from an extractor; empty = `fallback_ar` |
| `model_list` | which models the `model_profile` list offers |
| `model_profile` | model → native table, grid and size limits |
| `target_megapixels` | `0` = use the native table; `> 0` = compute a size of about this many MP |
| `custom_table` | extra entries `W:H = width, height`, one per line, `#` = comment; they win over the model table |
| `mp_grid` | manual sizes `X MP = WxH`, used when `target_megapixels > 0` |
| `fallback_ar` | used when `ar_input` is empty or not a valid ratio |
| `alignment` | `default` = the model's grid; `8` / `16` / `32` / `64` to force another grid |
| `direct_override` (optional) | `1920x1080` or `1920, 1080` → used as-is; empty = off |

| Output | Meaning |
|---|---|
| `width`, `height` | the size on the model grid |
| `matched_ar` | the ratio actually used (may be the nearest native one, or `override`) |
| `actual_mp` | W × H / 1024² |
| `is_fallback` | true when a fallback or approximation was used (fallback ratio, nearest native size, lattice solve) |
| `info` | which rule produced the size, plus notes and warnings |

**Decision chain**

1. `direct_override` set → used as-is (problems are reported in `info`).
2. `ar_input` empty or invalid → `fallback_ar` is used for the rest of the chain.
3. `target_megapixels = 0` and the ratio is in the custom or native table → that official size.
4. `target_megapixels > 0` → the closest `mp_grid` entry (re-solved for the ratio if it has another
   one), otherwise a lattice solve on the model grid.
5. otherwise → the native size with the closest ratio.

**Examples**

| `ar_input` | `model_profile` | `target_megapixels` | Result | Rule |
|---|---|---|---|---|
| `16:9` | SDXL | 0 | 1344 × 768 | native table |
| `1366x768` | SDXL | 0 | 1344 × 768 | nearest native ratio (`is_fallback` = true) |
| `21:9` | Z-Image (turbo/base) | 0 | 1344 × 576 | native table |
| `21:9` | Flux (dev/schnell) | 1 | 1568 × 672 | lattice solve @ 1 MP (exact 21:9) |
| `16:9` | Flux (dev/schnell) | 2 | 2048 × 1152 | lattice solve @ 2 MP |
| `wide` (invalid), fallback `3:2` | SDXL | 0 | 1216 × 832 | fallback ratio |
| `21:9`, custom table `21:9 = 1536, 640` | SDXL | 0 | 1536 × 640 | custom table |

**Exact ratio.** Computed sizes keep the exact ratio. Only when the exact sizes on the grid are far
from the requested area (ratios like 1366:768) or outside the limits, the nearest grid size with at
most 1.5 % ratio error is used; `info` then says "nearest grid point". When `target_megapixels` is
more than twice what the model was trained for, `info` adds a note; bigger images are better made
with an upscale pass.

---

## 🧮 Megapixel Selector

`KDX_Megapixel_Selector` — aspect ratio + megapixels → width and height on a grid, without any
model table.

| Input | Meaning |
|---|---|
| `aspect_ratio` | e.g. `16:9` |
| `target_megapixels` | e.g. `1.0` = 1024 × 1024 worth of pixels |
| `alignment` | both sides are multiples of this (8 / 16 / 32 / 64) |
| `mp_grid` | manual sizes `X MP = WxH`; the closest entry is used as-is when it has the ratio, otherwise re-solved; empty = lattice solve |

Outputs: `width`, `height`, `actual_mp`.

Examples: `16:9`, 1 MP, grid 16 → `1280 × 720`. `2:3`, 4 MP, grid 32 → `1664 × 2496`.
Sides are capped at 8192 px.

---

## 🔎 AR Extractor

`KDX_AR_Extractor` — find an aspect ratio in an LLM JSON answer, in free text, or in a `--ar` marker.
Feed `extracted_ar` into AutoRes Core.

| Input | Meaning |
|---|---|
| `mode` | `json` = read a JSON key; `text` = first `W:H` / `W/H` / `WxH` in the text; `marker` = `--ar 3:2`, `--ar3:2`, `--aspect 16:9`, `--aspect-ratio 9:16` |
| `input_text` | the text; empty = `fallback_value` |
| `key` | dotted JSON path (json mode), list indices allowed: `shots.0.ar` |
| `fallback_value` | returned when nothing usable is found |

| Output | Meaning |
|---|---|
| `extracted_ar` | e.g. `16:9` |
| `is_fallback` | true when `fallback_value` was returned |

JSON mode also finds JSON inside prose or a ```` ```json ```` fence, and reads values like
`"16:9 (wide)"`.

| `mode` | `input_text` | `key` | Result |
|---|---|---|---|
| json | ``Sure! ```json {"prompt":"a cat","aspect_ratio":"16:9 (wide)"} ``` `` | `aspect_ratio` | `16:9` |
| json | `{"shots":[{"ar":"2:3"}]}` | `shots.0.ar` | `2:3` |
| marker | `a cat --ar 3:2 --v 6` | | `3:2` |
| text | `portrait 4:5 framing` | | `4:5` |
| json | `no json here` | `aspect_ratio` | `1:1`, `is_fallback` = true |

---

## 🧾 Prompt Extractor

`KDX_Prompt_Extractor` — finds an aspect ratio, a resolution and/or the value of a custom key in any
text, and returns the prompt (optionally cleaned). Nothing is parsed as JSON, the text is only
searched, so a cut-off or broken LLM answer still works.

| Input | Meaning |
|---|---|
| `input_text` | the text to search (prompt, LLM answer …); empty = fallbacks |
| `extract_ar` | look for a ratio: `16:9`, `16/9`, `3x2`, `--ar 4:3`, `aspect_ratio: 16:9` |
| `extract_resolution` | look for a size: `1920x1080`, `1920*1080`, `1920 × 1080`, `--size 1024x768` (both sides ≥ 64) |
| `pick` | `first` / `last`: which match wins when there are several; a `--ar` / `--size` marker always wins |
| `remove_found` | delete the found items from the returned prompt (off = prompt unchanged) |
| `custom_key` | also return this key's value (`key: value`, `key=value`, `"key": "value"`, `--key value`); empty = off |
| `fallback_ar` | `ar` when no ratio is found |
| `fallback_width`, `fallback_height` | size when no resolution is found |
| `ar_key` | read the ratio from this key first (e.g. `aspect_ratio`) |
| `resolution_key` | read the size from this key first (e.g. `size`) |
| `prompt_key` | the key that holds the prompt (e.g. `rewritten_prompt`) |

| Output | Meaning |
|---|---|
| `prompt` | the prompt (see below) |
| `ar` | ratio, or `fallback_ar` |
| `width`, `height` | size, or the fallback size (a found size is returned as-is, no ratio is computed from it) |
| `custom_value` | value of `custom_key`, or empty |
| `found_ar`, `found_resolution`, `found_custom` | true when that item was found |
| `found_prompt` | true when the prompt was taken out of JSON-like text |

**Which text is the prompt.** With `prompt_key` set and found, `prompt` is just that value (escapes
like `\"` and `\n` undone, works on cut-off JSON). Otherwise, JSON-looking text gives its longest
text field; plain text gives the whole text. A ratio written inside the prompt field itself is used
only when there is none outside it.

**Examples**

| `input_text` | Settings | `prompt` | `ar` / size |
|---|---|---|---|
| `a castle at dusk, 21:9, cinematic` | `remove_found` on | `a castle at dusk, cinematic` | `21:9` |
| `{"rewritten_prompt": "a red fox in snow", "aspect_ratio": "2:3"}` | `ar_key` = `aspect_ratio`, `prompt_key` = `rewritten_prompt` | `a red fox in snow` | `2:3` |
| `{"rewritten_prompt": "a lighthouse, wide 16:9 view", "aspect_ratio": "9:16"` (cut off) | `remove_found` on | `a lighthouse, wide view` | `9:16` (the field outside the prompt wins) |
| `photo --ar 4:3, 1920x1080, seed: 42` | `custom_key` = `seed` | unchanged | `4:3`, 1920 × 1080, `custom_value` = `42` |

The older 🔎 AR Extractor stays for workflows that use it; for new LLM graphs the Prompt Extractor
does more in one node.

---

## ✅ AR Validator

`KDX_AR_Validator` — is the ratio in this text one of the allowed ones?

| Input | Meaning |
|---|---|
| `text_to_check` | text with a ratio; the first `W:H` / `W/H` / `WxH` is checked |
| `known_ratios` | comma-separated allowed ratios, e.g. `1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16` |

Outputs: `is_valid`, `extracted_ar` (the allowed ratio as written in `known_ratios`, or empty).
Ratios are compared reduced: `shot in 32:18` with `1:1, 16:9` → true, `16:9`.

---

## 🎲 AR Batch Tester

`KDX_AR_Batch_Tester` — step through a list of ratios with the seed, handy for testing one prompt in
several formats.

| Input | Meaning |
|---|---|
| `ratios_list` | comma-separated ratios, e.g. `1:1, 3:2, 16:9, 21:9` |
| `mode` | `Sequential` = item `seed % count`; `Random` = seeded random pick |
| `seed` | set *control after generate* to **increment** to move one step per queue |

Output: `test_ar_string`. Sequential with seeds 0, 1, 2, 3, 4 → `1:1`, `3:2`, `16:9`, `21:9`, `1:1`.
The same seed always gives the same ratio, so ComfyUI's cache works normally.

---

## ↔️ Reverse AR Matcher

`KDX_Reverse_AR_Matcher` — the ratio label of a size.

Inputs: `width`, `height`. Outputs: `closest_ar_string` (one of 1:1, 4:3, 3:4, 3:2, 2:3, 5:4, 4:5, 5:3,
3:5, 8:5, 5:8, 16:10, 10:16, 16:9, 9:16, 21:9, 9:21) and `exact_ratio_float` (W / H).

Examples: 1920 × 1080 → `16:9`, 1.7778. 1216 × 832 → `3:2`, 1.4615.

---

## 🧲 Nearest Native Preset

`KDX_Nearest_Native_Preset` — snap any size to the closest official size of a model (closest ratio
first, then area).

Inputs: `width`, `height`, `model_list`, `model_profile`. Outputs: `matched_ar`, `width`, `height`.

Example: 1920 × 1080, SDXL → `16:9`, 1344 × 768.

---

## 📶 Resolution Step

`KDX_Resolution_Step` — go N sizes up or down with the same ratio, or snap to a native size.

| Input | Meaning |
|---|---|
| `width`, `height` | the starting size |
| `mode` | `jump` = N steps on the ratio's grid; `snap` = the model's native size closest in width and height |
| `steps` | how many steps (jump) |
| `direction` | `up` / `down` (jump) |
| `model_list` | which models the `model_profile` list offers |
| `model_profile` | model (grid + size limits + native sizes), or `auto` = grid from the input size (largest power of two dividing W and H, 8–64) |

Outputs: `width`, `height`, `ar_string` (the ratio used for the steps), `bucket_index` (step number,
`0` in snap mode).

Jump keeps the ratio exact; at the model's limits it stops at the last size that still fits. A messy
input ratio (1366 × 768) uses the closest simple ratio so the steps stay a sensible size.

Examples with SDXL from 1280 × 720: jump 2 up → 1792 × 1008; jump 1 down → 1024 × 576; snap → 1344 × 768.

---

## 📏 Resolution Scaler

`KDX_Resolution_Scaler` — scale a size for a hires-fix pass and round it to a grid.

Inputs: `width`, `height`, `scale_factor` (0.1–4.0), `alignment` (8 / 16 / 32 / 64).
Outputs: `aligned_width`, `aligned_height`.

Example: 1280 × 720 × 1.5 on grid 16 → 1920 × 1088 (1080 is not a multiple of 16).

---

## 🔗 Resolution → String

`KDX_Resolution_To_String` — `width`, `height` → `resolution_string` such as `1920x1080`. Use it for
notes, file names, or AutoRes Core's `direct_override`.
