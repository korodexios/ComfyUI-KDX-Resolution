"""Model profiles: native resolutions, grid alignment and size bounds.

``MODEL_PROFILES`` is the single source of truth used by every node.
"""

# ============================================================================
# CONVENTIONS
# ============================================================================

#: ComfyUI megapixel convention: 1 MP = 1024 x 1024 pixels.
MP_PIXELS = 1024 * 1024


def _mp_pixels(target_mp: float) -> float:
    """Convert a target MP value (ComfyUI convention) to pixel count."""
    return float(target_mp) * MP_PIXELS

# ============================================================================
# CENTRAL MODEL PROFILES (single source of truth)
#
# kind:               image | video
# verified:           True = native sizes checked against the maker's repo/docs
#                     (see "source"); False = community values, use with care
# multiple_of:        VAE/patch grid (dims must be multiples of this)
# base_resolution:    native 1:1 size
# min_dim / max_dim:  hard bounds applied to every computed resolution
# recommended_mp:     the size (MP, 1 MP = 1024^2) the model was trained for;
#                     AutoRes Core warns when target_megapixels is far above it
# native_resolutions: official sizes per aspect ratio (AR -> (W, H))
# concrete_buckets:   further official / commonly used sizes (Preset Picker, Step snap)
# frame_formula / max_frames / default_fps: video frame rules
# note:               short caveat shown in the README table
#
# Names are stored in saved workflows: never rename without adding the old
# name to PROFILE_ALIASES.
# ============================================================================

# SDXL-style ~1 MP bucket table (used by several SDXL-derived models)
_SDXL_1MP = {
    "1:1": (1024, 1024),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}

MODEL_PROFILES = {
    "Qwen-Image-2.1": {
        "kind": "image",
        "family": "qwen-image",
        "verified": True,
        "source": "https://github.com/QwenLM/Qwen-Image-2.1",
        "base_resolution": 2048,
        "multiple_of": 32,
        "min_dim": 512,
        "max_dim": 8192,
        "recommended_mp": 4.0,
        # Official README "Supported Aspect Ratios" (2K level, all /32)
        "native_resolutions": {
            "1:1": (2048, 2048),
            "4:3": (2400, 1792),
            "3:4": (1792, 2400),
            "3:2": (2528, 1696),
            "2:3": (1696, 2528),
            "16:9": (2752, 1536),
            "9:16": (1536, 2752),
        },
    },
    "Qwen-Image (2512/edit)": {
        "kind": "image",
        "family": "qwen-image",
        "verified": True,
        "source": "https://github.com/QwenLM/Qwen-Image",
        "base_resolution": 1328,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 2048,
        "recommended_mp": 1.68,
        # Qwen-Image / Qwen-Image-2512 / Qwen-Image-Edit official 7 (~1.7 MP, all /16)
        "native_resolutions": {
            "1:1": (1328, 1328),
            "16:9": (1664, 928),
            "9:16": (928, 1664),
            "4:3": (1472, 1104),
            "3:4": (1104, 1472),
            "3:2": (1584, 1056),
            "2:3": (1056, 1584),
        },
    },
    "Flux (dev/schnell)": {
        "kind": "image",
        "family": "flux",
        "verified": True,
        "source": "https://github.com/black-forest-labs/flux",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "note": "any AR in steps of 16; ~0.1-2 MP works well, 1 MP is native",
        "native_resolutions": dict(_SDXL_1MP),
    },
    "Flux-2 (dev/pro/flash/krea)": {
        "kind": "image",
        "family": "flux",
        "verified": True,
        "source": "https://help.bfl.ai/articles/4029171097-flux-2-technical-specifications",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "max_mp": 4.0,
        "note": "BFL: any AR in steps of 16, default 1024x1024, max 4 MP, best quality/speed <= 2 MP",
        "native_resolutions": dict(_SDXL_1MP),
        "concrete_buckets": [
            [1440, 1440], [1664, 1248], [1248, 1664], [1920, 1088], [1088, 1920],
            [2048, 2048], [2560, 1440], [1440, 2560],
        ],
    },
    "SDXL": {
        "kind": "image",
        "family": "sd",
        "verified": True,
        "source": "https://arxiv.org/abs/2307.01952",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        # SDXL training buckets (paper, appendix I): ~1 MP, all /64
        "native_resolutions": {
            **_SDXL_1MP,
            "21:9": (1536, 640),
            "9:21": (640, 1536),
        },
    },
    "SD 1.5": {
        "kind": "image",
        "family": "sd",
        "verified": False,
        "base_resolution": 512,
        "multiple_of": 8,
        "min_dim": 64,
        "max_dim": 2048,
        "recommended_mp": 0.25,
        "note": "trained at 512x512; the other sizes are common community choices",
        "native_resolutions": {
            "1:1": (512, 512),
            "4:3": (576, 448),
            "3:4": (448, 576),
            "3:2": (608, 400),
            "2:3": (400, 608),
            "16:9": (672, 384),
            "9:16": (384, 672),
        },
        "concrete_buckets": [[768, 512], [512, 768]],
    },
    "Z-Image (turbo/base)": {
        "kind": "image",
        "family": "z-image",
        "verified": True,
        "source": "https://www.alibabacloud.com/help/en/model-studio/z-image-api-reference",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "max_mp": 4.0,
        "note": "official sizes at 1 MP; 1024-1536 px class recommended, 512-2048 supported",
        "native_resolutions": {
            "1:1": (1024, 1024),
            "4:3": (1152, 864),
            "3:4": (864, 1152),
            "3:2": (1248, 832),
            "2:3": (832, 1248),
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "21:9": (1344, 576),
            "9:21": (576, 1344),
            "9:7": (1152, 896),
            "7:9": (896, 1152),
        },
        "concrete_buckets": [[1280, 1280], [1536, 1536]],
    },
    "Krea 2 (turbo/raw)": {
        "kind": "image",
        "family": "krea",
        "verified": True,
        "source": "https://docs.krea.ai/user-guide/features/krea-2-turbo",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 512,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "max_mp": 4.0,
        "note": ("official Krea 2 Turbo table (~1 MP, Krea calls 7:3 '2.35:1'); "
                 "1024-2048 px on a /16 grid, 2K sizes kept as extra buckets"),
        "native_resolutions": {
            "1:1": (1024, 1024),
            "4:3": (1184, 896),
            "3:2": (1248, 832),
            "16:9": (1376, 768),
            "7:3": (1568, 672),
            "4:5": (928, 1152),
            "2:3": (832, 1248),
            "9:16": (768, 1376),
        },
        "concrete_buckets": [
            # mirrors Krea does not list (3:4, 5:4, 3:7)
            [896, 1184], [1152, 928], [672, 1568],
            # 2K tier (Turbo also works at 2048x2048)
            [2048, 2048], [2368, 1776], [1776, 2368], [2496, 1664], [1664, 2496],
            [2816, 1584], [1584, 2816], [1856, 2320],
        ],
    },
    "FLUX 3 Image Klein": {
        "kind": "image",
        "family": "flux",
        "verified": False,
        "source": "https://docs.bfl.ai/flux_3/flux3_image_klein",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "max_mp": 16.0,
        "note": "BFL: up to 4K; multiples of 16; no size table published (1 MP table + 2K/4K squares)",
        "native_resolutions": dict(_SDXL_1MP),
        "concrete_buckets": [[2048, 2048], [2560, 1440], [1440, 2560], [3840, 2160], [2160, 3840], [4096, 4096]],
    },
    "MiniMax H3 Image": {
        "kind": "image",
        "family": "minimax",
        "verified": True,
        "source": "https://github.com/MiniMax-AI/MiniMax-H3-Image",
        "base_resolution": 4096,
        # 16x VAE + 2x2 patch -> one token = 32x32 px
        "multiple_of": 32,
        "min_dim": 480,
        "max_dim": 8192,
        "recommended_mp": 16.0,
        # custom width x height: 655,360 .. 20,000,000 px
        "max_mp": 19.0,
        "note": "native ~16 MP in one pass (no upscaler); works ~4-20 MP; AR 1:3..3:1; 2K tier ~4 MP",
        # Official ~16 MP table (GitHub README / ComfyUI tutorial, all /32)
        "native_resolutions": {
            "1:1": (4096, 4096),
            "4:3": (4736, 3552),
            "3:4": (3552, 4736),
            "3:2": (5024, 3360),
            "2:3": (3360, 5024),
            "16:9": (5472, 3072),
            "9:16": (3072, 5472),
            "21:9": (6272, 2688),
        },
        "concrete_buckets": [
            [4576, 3648], [3648, 4576],              # 5:4 / 4:5 from the official size_for('5:4')
            [2048, 2048], [2720, 1536], [1536, 2720],  # 2K area tier (~4 MP)
        ],
    },
    # -- video ------------------------------------------------------------
    "Wan 2.2": {
        "kind": "video",
        "family": "wan",
        "verified": True,
        "source": "https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/__init__.py",
        "base_resolution": 720,
        "multiple_of": 16,
        "min_dim": 480,
        "max_dim": 1280,
        "recommended_mp": 0.88,
        "note": "T2V/I2V A14B: SUPPORTED_SIZES 1280x720, 720x1280, 832x480, 480x832",
        "native_resolutions": {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
        },
        "concrete_buckets": [[832, 480], [480, 832]],
        "frame_formula": "4n+1",
        "max_frames": 81,
        "default_fps": 16,
    },
    "Wan 2.2 TI2V-5B": {
        "kind": "video",
        "family": "wan",
        "verified": True,
        "source": "https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/__init__.py",
        "base_resolution": 704,
        "multiple_of": 32,
        "min_dim": 480,
        "max_dim": 1280,
        "recommended_mp": 0.86,
        "note": "720P is 1280x704 / 704x1280 for the 5B model (VAE stride 16 x patch 2 = /32)",
        "native_resolutions": {
            "16:9": (1280, 704),
            "9:16": (704, 1280),
        },
        "frame_formula": "4n+1",
        "max_frames": 121,
        "default_fps": 24,
    },
    "LTX 2.3": {
        "kind": "video",
        "family": "ltx",
        "verified": True,
        "source": "https://github.com/Lightricks/LTX-2",
        "base_resolution": 704,
        "multiple_of": 32,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 0.86,
        "note": "width and height divisible by 32, frames 8n+1 (65-257)",
        "native_resolutions": {
            "16:9": (1280, 704),
            "9:16": (704, 1280),
            "1:1": (768, 768),
            "3:2": (768, 512),
        },
        "concrete_buckets": [
            [1920, 1088], [1088, 1920], [640, 640], [512, 768],
        ],
        "frame_formula": "8n+1",
        "max_frames": 257,
        "default_fps": 24,
        "upscaler": ["x1.5", "x2"],
    },
    "LTX 2.5": {
        "kind": "video",
        "family": "ltx",
        "verified": False,
        "source": "https://comfyui-wiki.com/en/models/ltx-video/ltx-2-5",
        "base_resolution": 1088,
        "multiple_of": 32,
        "min_dim": 256,
        "max_dim": 3840,
        "recommended_mp": 1.99,
        "note": "default 1920x1088 @ 24 fps, up to 4K; frames 8n+1 (25-505); sizes divisible by 32",
        "native_resolutions": {
            "16:9": (1920, 1088),
            "9:16": (1088, 1920),
        },
        "concrete_buckets": [[1280, 704], [704, 1280], [2560, 1440], [3840, 2176]],
        "frame_formula": "8n+1",
        "max_frames": 505,
        "default_fps": 24,
    },
    "HunyuanVideo 1.5": {
        "kind": "video",
        "family": "hunyuan",
        "verified": False,
        "source": "https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5",
        "base_resolution": 720,
        "multiple_of": 16,
        "min_dim": 480,
        "max_dim": 1280,
        "recommended_mp": 0.88,
        "note": "official: 480p / 720p, default 16:9, 121 frames; other ratios are community sizes",
        "native_resolutions": {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1": (960, 960),
            "4:3": (1104, 832),
            "3:4": (832, 1104),
        },
        "concrete_buckets": [[848, 480], [480, 848], [640, 640]],
        "frame_formula": "4n+1",
        "max_frames": 121,
        "default_fps": 24,
    },
    "MOVA (OpenMOSS, video+audio)": {
        "kind": "video",
        "family": "mova",
        "verified": True,
        "source": "https://arxiv.org/abs/2602.08794",
        "base_resolution": 720,
        "multiple_of": 16,
        "min_dim": 352,
        "max_dim": 1280,
        "recommended_mp": 0.88,
        "note": "MOVA-720p: 1280x720; MOVA-360p: 640x352; 193 frames @ 24 fps (~8 s)",
        "native_resolutions": {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
        },
        "concrete_buckets": [[640, 352], [352, 640]],
        "frame_formula": "4n+1",
        "max_frames": 193,
        "default_fps": 24,
    },
    "MiniMax H3": {
        "kind": "video",
        "family": "minimax",
        "verified": False,
        "source": "https://www.minimax.io/news/minimax-h3-open-source",
        "base_resolution": 768,
        "multiple_of": 32,
        "min_dim": 480,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "note": "no official size table published; open weights reportedly 768p, 2K via upscaler",
        "native_resolutions": {
            "16:9": (1344, 768),
            "9:16": (768, 1344),
            "1:1": (768, 768),
            "4:3": (1024, 768),
            "3:4": (768, 1024),
        },
        "concrete_buckets": [
            [1344, 768], [768, 1344], [768, 768],
            [1024, 768], [768, 1024], [1920, 768],
            [832, 480], [480, 832],
        ],
        "ar_priority": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "ar_tolerance": 0.05,
        "frame_formula": "4n+1",
        "max_frames": 361,
        "default_fps": 24,
        "upscaler": "H3-Regenerate-2K",
    },
    "Hunyuan Video": {
        "kind": "video",
        "family": "hunyuan",
        "verified": True,
        "source": "https://github.com/Tencent/HunyuanVideo",
        "base_resolution": 960,
        "multiple_of": 16,
        "min_dim": 544,
        "max_dim": 1280,
        "recommended_mp": 0.88,
        "note": "720p tier (recommended); 540p tier in buckets; 129 frames",
        "native_resolutions": {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1104, 832),
            "3:4": (832, 1104),
            "1:1": (960, 960),
        },
        "concrete_buckets": [
            [960, 544], [544, 960], [832, 624], [624, 832], [720, 720],
        ],
        "frame_formula": "4n+1",
        "max_frames": 129,
        "default_fps": 24,
    },
    "Mochi 1": {
        "kind": "video",
        "family": "mochi",
        "verified": True,
        "source": "https://huggingface.co/docs/diffusers/api/pipelines/mochi",
        "base_resolution": 480,
        "multiple_of": 16,
        "min_dim": 480,
        "max_dim": 848,
        "recommended_mp": 0.39,
        "note": "trained at 848x480 only; frames 6n+1 (up to 163)",
        "native_resolutions": {
            "16:9": (848, 480),
        },
        "concrete_buckets": [[480, 848]],
        "frame_formula": "6n+1",
        "max_frames": 163,
        "default_fps": 30,
    },
    "CogVideoX 5B": {
        "kind": "video",
        "family": "cogvideox",
        "verified": True,
        "source": "https://huggingface.co/THUDM/CogVideoX-5b",
        "base_resolution": 480,
        "multiple_of": 16,
        "min_dim": 480,
        "max_dim": 720,
        "recommended_mp": 0.33,
        "note": "fixed 720x480, frames 8n+1 (max 49), 8 fps",
        "native_resolutions": {
            "3:2": (720, 480),
        },
        "frame_formula": "8n+1",
        "max_frames": 49,
        "default_fps": 8,
    },
    "CogVideoX 1.5 5B": {
        "kind": "video",
        "family": "cogvideox",
        "verified": True,
        "source": "https://huggingface.co/zai-org/CogVideoX1.5-5B",
        "base_resolution": 768,
        "multiple_of": 16,
        "min_dim": 480,
        "max_dim": 1360,
        "recommended_mp": 1.0,
        "note": "1360x768, frames 16n+1 (max 161), 16 fps",
        "native_resolutions": {
            "16:9": (1360, 768),
        },
        "concrete_buckets": [[768, 1360]],
        "frame_formula": "16n+1",
        "max_frames": 161,
        "default_fps": 16,
    },
    "SVD / SVD-XT": {
        "kind": "video",
        "family": "svd",
        "verified": True,
        "source": "https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt",
        "base_resolution": 576,
        "multiple_of": 64,
        "min_dim": 576,
        "max_dim": 1024,
        "recommended_mp": 0.56,
        "note": "trained at 1024x576; 14 frames (SVD) / 25 frames (XT)",
        "native_resolutions": {
            "16:9": (1024, 576),
        },
        "concrete_buckets": [[576, 1024], [768, 768]],
        "frame_formula": "fixed",
        "max_frames": 25,
        "default_fps": 6,
    },
    "AnimateDiff": {
        "kind": "video",
        "family": "animatediff",
        "verified": False,
        "base_resolution": 512,
        "multiple_of": 8,
        "min_dim": 512,
        "max_dim": 2048,
        "recommended_mp": 0.25,
        "note": "SD 1.5 motion module, 16-frame context; sizes are community choices",
        "frame_formula": "4n",
        "max_frames": 64,
        "default_fps": 8,
        "native_resolutions": {
            "1:1": (512, 512),
            "3:2": (768, 512),
            "2:3": (512, 768),
        },
    },
    "Hotshot-XL": {
        "kind": "video",
        "family": "hotshot",
        "verified": False,
        "source": "https://github.com/hotshotco/Hotshot-XL",
        "base_resolution": 512,
        "multiple_of": 8,
        "min_dim": 320,
        "max_dim": 1024,
        "recommended_mp": 0.25,
        "note": "1-second GIFs: 8 frames at 8 fps, aspect ratios around 512x512",
        "frame_formula": "fixed",
        "max_frames": 8,
        "default_fps": 8,
        "native_resolutions": {
            "1:1": (512, 512),
            "7:4": (672, 384),
            "4:7": (384, 672),
        },
    },
    # -- additional image models -----------------------------------------
    "SD 3.5 Large": {
        "kind": "image",
        "family": "sd3",
        "verified": False,
        "source": "https://huggingface.co/stabilityai/stable-diffusion-3.5-large",
        "base_resolution": 1024,
        "multiple_of": 64,
        "min_dim": 512,
        "max_dim": 2048,
        "recommended_mp": 1.0,
        "note": "~1 MP, multiples of 64",
        "native_resolutions": dict(_SDXL_1MP),
    },
    "Kolors": {
        "kind": "image",
        "family": "kolors",
        "verified": False,
        "source": "https://huggingface.co/Kwai-Kolors/Kolors",
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "note": "SDXL architecture, 1024 px; SDXL buckets used",
        "native_resolutions": dict(_SDXL_1MP),
    },
    "PixArt Sigma": {
        "kind": "image",
        "family": "pixart",
        "verified": False,
        "source": "https://huggingface.co/spaces/PixArt-alpha/PixArt-Sigma",
        "base_resolution": 1024,
        "multiple_of": 8,
        "min_dim": 256,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "note": "1024 model uses ASPECT_RATIO_1024_BIN (~1 MP); 2K/4K checkpoints exist",
        "native_resolutions": {
            "1:1": (1024, 1024),
            "4:3": (1152, 896),
            "3:4": (896, 1152),
            "16:9": (1344, 768),
            "9:16": (768, 1344),
        },
        "concrete_buckets": [
            [1024, 1024], [2048, 2048],
            [1152, 896], [896, 1152],
        ],
    },
    "Lumina-T2X": {
        "kind": "image",
        "family": "lumina",
        "verified": False,
        "base_resolution": 1024,
        "multiple_of": 16,
        "min_dim": 512,
        "max_dim": 4096,
        "recommended_mp": 1.0,
        "native_resolutions": {
            "1:1": (1024, 1024),
            "16:9": (1280, 720),
            "9:16": (720, 1280),
        },
        "concrete_buckets": [
            [1024, 1024], [1280, 720], [720, 1280],
            [2048, 2048],
        ],
    },
}


#: Old profile names kept working in saved workflows (old name -> current name).
PROFILE_ALIASES = {
    "Z-Image (turbop/base)": "Z-Image (turbo/base)",
    "Qwen-Image (2.0/edit)": "Qwen-Image (2512/edit)",
}


def resolve_profile_name(model_profile) -> str:
    """Map an old (aliased) profile name to its current name; unknown names pass through."""
    name = str(model_profile or "")
    return PROFILE_ALIASES.get(name, name)


def profile_names(include_hidden: bool = True) -> list:
    """Profile names for a dropdown, in table order."""
    return [k for k, v in MODEL_PROFILES.items() if include_hidden or not v.get("hidden", False)]


def validate_profile_name(model_profile, allow=()):
    """ComfyUI ``VALIDATE_INPUTS`` helper: True, or an error message for an unknown profile.

    Accepts current names, old aliases and the extra values in ``allow`` (e.g. "auto").
    A linked input (value not known at validation time) is accepted.
    """
    if model_profile is None or model_profile in allow or resolve_profile_name(model_profile) in MODEL_PROFILES:
        return True
    return f"Unknown model_profile '{model_profile}'. Valid: {', '.join(list(MODEL_PROFILES) + list(allow))}"


def _profile(model_profile: str) -> dict:
    """Return the profile dict for a model name (old aliases accepted), or None if unknown."""
    return MODEL_PROFILES.get(resolve_profile_name(model_profile))


def profile_summary() -> list:
    """Public, JSON-safe profile overview for the web UI (Settings -> KDX Resolution)."""
    out = []
    for name, p in MODEL_PROFILES.items():
        out.append({
            "name": name,
            "kind": p.get("kind", "image"),
            "verified": bool(p.get("verified")),
            "recommended_mp": p.get("recommended_mp"),
            "multiple_of": p.get("multiple_of"),
            "note": p.get("note", ""),
            "source": p.get("source", ""),
        })
    return out
