"""Preset registry for the Preset Picker: model tables + custom JSON lists."""

import json
import logging
import math
import os
import re

from . import my_profiles
from .profiles import all_profiles

# Custom lists live in the node pack root (next to the top-level __init__.py).
_KDX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CUSTOM_PRESETS_PATH = os.path.join(_KDX_DIR, "kdx_custom_presets.json")
_LOCAL_PRESETS_PATH = os.path.join(_KDX_DIR, "kdx_custom_presets.local.json")
CUSTOM_PRESET_PATHS = [_CUSTOM_PRESETS_PATH, _LOCAL_PRESETS_PATH]
log = logging.getLogger(__name__)
_WH_RE = re.compile(r"(\d+)\s*[xX,]\s*(\d+)\s*$")
_KDX_CACHE = {"mtime": None, "data": None}


def _ar_label(w, h):
    """Human-readable AR label: '16:9', '~16:9' (within 3%), or decimal."""
    if w <= 0 or h <= 0:
        return "?"
    g = math.gcd(w, h)
    a, b = w // g, h // g
    _known = [(1, 1), (5, 4), (4, 3), (3, 2), (16, 10), (16, 9),
              (2, 1), (21, 9), (32, 9)]
    _known_all = sorted(set(_known + [(b, a) for a, b in _known]))
    if (a, b) in _known_all:
        return f"{a}:{b}"
    r = w / h
    best = min(_known_all, key=lambda k: abs(math.log(r / (k[0] / k[1]))))
    if abs(r / (best[0] / best[1]) - 1) < 0.03:
        return f"~{best[0]}:{best[1]}"
    if max(a, b) <= 24:
        return f"{a}:{b}"
    return f"{r:.2f}:1"


def _parse_pair(item):
    """Parse a preset entry: [1280, 720] or '1280x720' -> (1280, 720); None if invalid."""
    try:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            w, h = int(item[0]), int(item[1])
        else:
            m = _WH_RE.search(str(item))
            if not m:
                return None
            w, h = int(m.group(1)), int(m.group(2))
    except (TypeError, ValueError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def _dedupe(pairs):
    seen, out = set(), []
    for w, h in pairs:
        if (w, h) not in seen and w > 0 and h > 0:
            seen.add((w, h))
            out.append((w, h))
    return out


def _read_custom(path):
    """Read one custom-presets JSON file; a missing/broken file gives {} (logged)."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        log.warning("[KDX-Resolution] ignoring %s: %s", os.path.basename(path), e)
        return {}
    if not isinstance(data, dict):
        log.warning("[KDX-Resolution] ignoring %s: top level must be an object", os.path.basename(path))
        return {}
    return data


def _build_registry():
    """Build the preset registry from MODEL_PROFILES + custom JSON files.

    Later files win: kdx_custom_presets.json (shipped examples), then
    kdx_custom_presets.local.json (your own lists, not tracked by git).
    """
    reg, grid = {}, {}
    for name, p in all_profiles().items():
        if p.get("hidden"):
            continue
        pairs = list(p.get("native_resolutions", {}).values())
        pairs += [tuple(b) for b in p.get("concrete_buckets", [])]
        pairs = _dedupe(pairs)
        if pairs:
            reg[name] = pairs
            grid[name] = p.get("multiple_of", 16)

    for path in CUSTOM_PRESET_PATHS:
        for name, d in _read_custom(path).items():
            if not isinstance(d, dict) or str(name).startswith("_"):
                continue
            name = str(name).replace(" | ", " / ")  # " | " separates the dropdown label parts
            base = d.get("based_on")
            pairs = list(reg.get(base, [])) if d.get("include_base") else []
            presets = d.get("presets", [])
            for item in presets if isinstance(presets, list) else []:
                pr = _parse_pair(item)
                if pr:
                    pairs.append(pr)
            pairs = _dedupe(pairs)
            if pairs:
                reg[name] = pairs
                mult = d.get("multiple_of", grid.get(base, 16))
                grid[name] = mult if isinstance(mult, int) and mult > 0 else 16
    return reg, grid


def _load_registry():
    """Cached registry, re-read when a custom file changes (press R in ComfyUI)."""
    stamp = []
    for path in CUSTOM_PRESET_PATHS:
        try:
            stamp.append(os.path.getmtime(path))
        except OSError:
            stamp.append(None)
    stamp.append(my_profiles._stamp(my_profiles.store_path()))
    stamp = tuple(stamp)
    if _KDX_CACHE["data"] is None or _KDX_CACHE["mtime"] != stamp:
        _KDX_CACHE["data"], _KDX_CACHE["mtime"] = _build_registry(), stamp
    return _KDX_CACHE["data"]
