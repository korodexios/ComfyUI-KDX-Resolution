# 03 Model profiles and presets

A **model profile** is what the pack knows about one model family:

| Field | Meaning |
|---|---|
| kind | `image` or `video` (used by `model_list` and the settings) |
| grid (`multiple_of`) | both sides must be a multiple of this (VAE / patch size) |
| size limits (`min_dim` / `max_dim`) | every computed side stays within them |
| ~MP (`recommended_mp`) | the size the model was trained for (1 MP = 1024 × 1024) |
| native sizes | the official size per aspect ratio, used verbatim by AutoRes Core when `target_megapixels = 0` |
| extra buckets | further official or common sizes (Preset Picker, Resolution Step snap) |
| frames (video) | frame-count rule, maximum frames and default fps, for reference |

"official" in the table = the native sizes were checked against the maker's repository or
documentation (link); "community" = no official table is published, the sizes are common choices.
Official tables are used verbatim, even where the makers rounded the label (SDXL 1152 × 896 is listed
as 4:3).

AutoRes Core adds a note to `info` when `target_megapixels` is more than twice the model's ~MP, and
Flux-2 / Z-Image are capped at their 4 MP maximum. Bigger images are better made with an upscale pass
(e.g. 📏 Resolution Scaler + img2img) than generated directly.

## The profiles

<!-- models:start -->
| Profile | Kind | Grid | ~MP | Native sizes | Frames | Sizes |
|---|---|---|---|---|---|---|
| Qwen-Image-2.1 | image | /32 | 4 | 2048×2048, 2400×1792, 1792×2400, 2528×1696, 1696×2528, 2752×1536, 1536×2752 |  | [official](https://github.com/QwenLM/Qwen-Image-2.1) |
| Qwen-Image (2512/edit) | image | /16 | 1.68 | 1328×1328, 1664×928, 928×1664, 1472×1104, 1104×1472, 1584×1056, 1056×1584 |  | [official](https://github.com/QwenLM/Qwen-Image) |
| Flux (dev/schnell) | image | /16 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344 |  | [official](https://github.com/black-forest-labs/flux) |
| Flux-2 (dev/pro/flash/krea) | image | /16 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344 |  | [official](https://help.bfl.ai/articles/4029171097-flux-2-technical-specifications) |
| SDXL | image | /16 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344, 1536×640, 640×1536 |  | [official](https://arxiv.org/abs/2307.01952) |
| SD 1.5 | image | /8 | 0.25 | 512×512, 576×448, 448×576, 608×400, 400×608, 672×384, 384×672 |  | community |
| Z-Image (turbo/base) | image | /16 | 1 | 1024×1024, 1152×864, 864×1152, 1248×832, 832×1248, 1280×720, 720×1280, 1344×576, 576×1344, 1152×896, 896×1152 |  | [official](https://www.alibabacloud.com/help/en/model-studio/z-image-api-reference) |
| Krea 2 (turbo/raw) | image | /16 | 1 | 1024×1024, 1184×896, 1248×832, 1376×768, 1568×672, 928×1152, 832×1248, 768×1376 |  | [official](https://docs.krea.ai/user-guide/features/krea-2-turbo) |
| FLUX 3 Image Klein | image | /16 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344 |  | community ([info](https://docs.bfl.ai/flux_3/flux3_image_klein)) |
| MiniMax H3 Image | image | /32 | 16 | 4096×4096, 4736×3552, 3552×4736, 5024×3360, 3360×5024, 5472×3072, 3072×5472, 6272×2688 |  | [official](https://github.com/MiniMax-AI/MiniMax-H3-Image) |
| SD 3.5 Large | image | /64 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344 |  | community ([info](https://huggingface.co/stabilityai/stable-diffusion-3.5-large)) |
| Kolors | image | /16 | 1 | 1024×1024, 1152×896, 896×1152, 1216×832, 832×1216, 1344×768, 768×1344 |  | community ([info](https://huggingface.co/Kwai-Kolors/Kolors)) |
| PixArt Sigma | image | /8 | 1 | 1024×1024, 1152×896, 896×1152, 1344×768, 768×1344 |  | community ([info](https://huggingface.co/spaces/PixArt-alpha/PixArt-Sigma)) |
| Lumina-T2X | image | /16 | 1 | 1024×1024, 1280×720, 720×1280 |  | community |
| Wan 2.2 | video | /16 | 0.88 | 1280×720, 720×1280 | 4n+1 ≤81 @16 fps | [official](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/__init__.py) |
| Wan 2.2 TI2V-5B | video | /32 | 0.86 | 1280×704, 704×1280 | 4n+1 ≤121 @24 fps | [official](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/__init__.py) |
| LTX 2.3 | video | /32 | 0.86 | 1280×704, 704×1280, 768×768, 768×512 | 8n+1 ≤257 @24 fps | [official](https://github.com/Lightricks/LTX-2) |
| LTX 2.5 | video | /32 | 1.99 | 1920×1088, 1088×1920 | 8n+1 ≤505 @24 fps | community ([info](https://comfyui-wiki.com/en/models/ltx-video/ltx-2-5)) |
| HunyuanVideo 1.5 | video | /16 | 0.88 | 1280×720, 720×1280, 960×960, 1104×832, 832×1104 | 4n+1 ≤121 @24 fps | community ([info](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)) |
| MOVA (OpenMOSS, video+audio) | video | /16 | 0.88 | 1280×720, 720×1280 | 4n+1 ≤193 @24 fps | [official](https://arxiv.org/abs/2602.08794) |
| MiniMax H3 | video | /32 | 1 | 1344×768, 768×1344, 768×768, 1024×768, 768×1024 | 4n+1 ≤361 @24 fps | community ([info](https://www.minimax.io/news/minimax-h3-open-source)) |
| Hunyuan Video | video | /16 | 0.88 | 1280×720, 720×1280, 1104×832, 832×1104, 960×960 | 4n+1 ≤129 @24 fps | [official](https://github.com/Tencent/HunyuanVideo) |
| Mochi 1 | video | /16 | 0.39 | 848×480 | 6n+1 ≤163 @30 fps | [official](https://huggingface.co/docs/diffusers/api/pipelines/mochi) |
| CogVideoX 5B | video | /16 | 0.33 | 720×480 | 8n+1 ≤49 @8 fps | [official](https://huggingface.co/THUDM/CogVideoX-5b) |
| CogVideoX 1.5 5B | video | /16 | 1 | 1360×768 | 16n+1 ≤161 @16 fps | [official](https://huggingface.co/zai-org/CogVideoX1.5-5B) |
| SVD / SVD-XT | video | /64 | 0.56 | 1024×576 | fixed ≤25 @6 fps | [official](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt) |
| AnimateDiff | video | /8 | 0.25 | 512×512, 768×512, 512×768 | 4n ≤64 @8 fps | community |
| Hotshot-XL | video | /8 | 0.25 | 512×512, 672×384, 384×672 | fixed ≤8 @8 fps | community ([info](https://github.com/hotshotco/Hotshot-XL)) |
<!-- models:end -->

Older profile names keep working in saved workflows (`Z-Image (turbop/base)` → `Z-Image (turbo/base)`,
`Qwen-Image (2.0/edit)` → `Qwen-Image (2512/edit)`).

## My model profiles

A **my profile** is a built-in profile with your own size table: it keeps the model's grid, size
limits and ~MP, and uses only the sizes you list. It shows up in **every** model dropdown (AutoRes
Core, Preset Picker, Nearest Native Preset, Resolution Step) as `★ <name>`, after the built-in ones.

1. Right-click any KDX Resolution node → **KDX: ★ my model profiles…** (or top menu
   **Extensions → KDX Resolution**).
2. **New profile**: give it a name and pick the model it is **based on**. The box fills with that
   model's sizes; edit them, one per line:

   ```text
   1:1  = 1024x1024
   16:9 = 1376x768
   2.35:1 = 1568x672     # decimal ratio: the ratio comes from the size (7:3)
   1184x896              # no ratio: the nearest common one is used (4:3)
   ```

3. The table next to the box shows what was understood; errors name the line and the fix (a size
   off the model's grid suggests the nearest size on it). **Save** (Ctrl+S) puts the profile into the
   dropdowns of all open nodes right away; no restart and no R needed.

How the nodes use it: AutoRes Core with `target_megapixels = 0` returns your size for that ratio; a
ratio you did not list gets the nearest of **your** sizes; with `target_megapixels > 0` the size is
computed on the base model's grid as usual.

- Stored in `<ComfyUI user dir>/kdx_resolution/my_profiles.json` (default `ComfyUI/user/`), outside
  the node pack, so `git pull` never touches it. Copy that file to use the profiles on another machine.
- **Renaming** keeps the old name working in saved workflows. **Deleting** does not: such a workflow
  says the profile does not exist on this machine and asks you to pick another model.
- A workflow stores only the profile's name. Someone without your file has to create the profile too.

## Your own preset lists

The 📑 Preset Picker lists every model's native sizes and extra buckets, plus your own lists.

1. Create `kdx_custom_presets.local.json` in the pack folder, next to `kdx_custom_presets.json`.
   The `.local` file is not tracked by git, so `git pull` never conflicts with it.
2. Press **R** in ComfyUI to reload the node definitions; no restart needed.

```json
{
  "My SDXL": { "based_on": "SDXL", "include_base": true, "multiple_of": 16,
               "presets": ["1920x1080", "1080x1920", [1024, 1536]] },
  "My video": { "multiple_of": 32, "presets": ["1280x736", "1920x1088"] }
}
```

| Key | Meaning |
|---|---|
| list name | shown in the `model` dropdown (`" \| "` in a name becomes `" / "`); names starting with `_` are ignored |
| `presets` | sizes as `"1920x1080"` or `[1920, 1080]` |
| `based_on` | a profile name: its grid is used when `multiple_of` is missing |
| `include_base` | `true` = the base profile's sizes come first, yours are added after them |
| `multiple_of` | grid used when the Picker's `scale` is not 1.0 (default: the base profile's, else 16) |

`kdx_custom_presets.json` holds commented examples (keys starting with `_`). A broken file is
skipped with a warning in the ComfyUI log; the other lists keep working.

Custom lists are for the Preset Picker only. For AutoRes Core use its `custom_table` input
(`21:9 = 1536, 640`, one per line), which wins over the model's native table.

## Choosing which models are listed

- **In the node**: AutoRes Core, Preset Picker, Nearest Native Preset and Resolution Step have
  `model_list` (*all models*, *image models*, *video models*) right above the model dropdown, which
  then offers only that kind. It never changes the result.
- **For all nodes**: ComfyUI → ⚙ **Settings** → **KDX Resolution** (or type "KDX" in the settings
  search). Switch off models you never use, or show only image / only video models everywhere.
  Shortcut: right-click a KDX Resolution node → **KDX: choose visible models…**.
- Hidden models are only hidden in the lists: a node that already uses one keeps it, and saved
  workflows are not affected.
