# 04 With KDX Wildcard Studio and KDX LLM

KDX Resolution works on its own, but it is made to sit at the end of a prompt chain built with the
other KDX packs:

- [KDX Wildcard Studio](https://github.com/korodexios/ComfyUI-KDX-Wildcard-Studio) (formerly
  *KDX Console*) writes the prompt from wildcard templates.
- [KDX LLM](https://github.com/korodexios/ComfyUI-KDX-LLM) can rewrite that prompt with a local or
  remote LLM and answer in JSON.
- KDX Resolution reads the aspect ratio out of the result and turns it into the model's size.

No pack depends on another: every connection below is a plain STRING / INT wire.

## The full chain

```
🎛️ Wildcard Studio ──prompt, system_prompt, llm_enabled──▶ 💬 LLM Chat
💬 LLM Chat ──response──▶ 🧾 Prompt Extractor
🧾 Prompt Extractor ──prompt──▶ CLIP Text Encode
🧾 Prompt Extractor ──ar──────▶ 🎯 AutoRes Core ──width, height──▶ Empty Latent Image
```

1. **Wildcard Studio** → LLM Chat: `prompt` → `prompt`, `system_prompt` → `system_prompt`,
   `llm_enabled` → `llm_enabled`.
2. **LLM Chat** is told to answer in JSON, for example with this system prompt:

   ```
   Answer ONLY with JSON: {"rewritten_prompt": "...", "aspect_ratio": "W:H"} where aspect_ratio is
   one of 1:1, 4:5, 2:3, 3:4, 16:9, 9:16, 3:2, chosen to suit the scene.
   ```

3. **🧾 Prompt Extractor**: Chat `response` → `input_text`, with
   - `extract_ar` on, `extract_resolution` off,
   - `remove_found` on,
   - `ar_key` = `aspect_ratio`, `prompt_key` = `rewritten_prompt`,
   - `fallback_ar` = the ratio you want when none is given (e.g. `1:1`).
4. Prompt Extractor `prompt` → CLIP Text Encode `text`; `ar` → AutoRes Core `ar_input`.
5. **🎯 AutoRes Core**: pick the model profile; `width` / `height` → the empty latent node.

The ready-made graph is in the KDX Wildcard Studio pack: *4 all KDX nodes* (SDXL) and
*5 Z-Image Turbo with LLM and Resolution* in its `example_workflows/`.

## Why the Prompt Extractor and not JSON parsing

The same Prompt Extractor settings work in all three cases the chain produces:

| Chat `response` | `prompt` | `ar` |
|---|---|---|
| `{"rewritten_prompt": "A woman reads by a tall window in soft morning light.", "aspect_ratio": "2:3"}` (LLM on) | `A woman reads by a tall window in soft morning light.` | `2:3` |
| `a woman reading by a window, a tall frame, 2:3` (LLM off: the Studio prompt unchanged) | `a woman reading by a window, a tall frame` | `2:3` |
| `a woman reading by a window` (LLM off, no ratio in the template) | unchanged | `1:1` (`fallback_ar`) |

- With the LLM switched off (Studio's LLM pill, or `llm=off` in its overrides), LLM Chat makes no call
  and passes the Studio prompt through unchanged. There is no JSON then, so the Extractor falls back to
  searching the plain text.
- Wildcard Studio templates usually write the framing with its ratio (the starter library's `shot`
  pools say things like `a tall frame, 2:3`). `remove_found` takes the ratio out of the prompt, so the
  text encoder never sees `2:3`.
- A cut-off LLM answer (missing closing quote or brace, e.g. when the token limit was hit) still gives
  the prompt and the ratio; real JSON parsing would fail.
- `found_ar` / `found_prompt` tell you which case happened, e.g. for a Preview node while you tune the
  system prompt.

## Other ways to connect

- **Only the ratio from JSON**: LLM Chat `response` (or `json`) → 🔎 **AR Extractor** (`mode` = json,
  `key` = `aspect_ratio`) → AutoRes Core. Shown in
  [example workflow 2](05-example-workflows.md#2-llm-json-aspect-ratio-to-latent).
- **KDX LLM's JSON Fields**: if you already read several fields with 🗂️ JSON Fields, connect its
  `aspect_ratio` field straight to AutoRes Core's `ar_input`. An empty or invalid value uses
  `fallback_ar`.
- **A size instead of a ratio**: ask the LLM for `"size": "1344x768"` and set the Prompt Extractor's
  `resolution_key` = `size` with `extract_resolution` on; `width` / `height` then come out as-is.
  Feed them to 🧲 Nearest Native Preset if the size must be one of the model's official ones.
- **Restricting what the LLM may choose**: put ✅ AR Validator after the extractor to check the ratio
  against your own list (`is_valid`), or list the allowed ratios in the system prompt as above.

## When the LLM is switched off: fixed ratio instead

If you want a fixed ratio whenever the LLM is off (and not the one written in the template), drive a
core Switch node with the same `llm_enabled` boolean: `on_true` = the Extractor's `ar`, `on_false` = a
fixed ratio such as `2:3`, output → AutoRes Core `ar_input`. Every value that comes from the LLM needs
its own switch driven by the same boolean.
