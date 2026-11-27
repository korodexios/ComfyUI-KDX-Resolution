"""Human-readable result text shown inside each node (after a run and as a live preview).

``summarize(node_cls, kwargs, outputs)`` turns a node's inputs and outputs into a
few short lines: the final size first, then where it came from and any warnings.
"""

from .presets import _ar_label
from .profiles import MP_PIXELS, _profile, resolve_profile_name

SIZE_KEYS = (("width", "height"), ("aligned_width", "aligned_height"))


def size_line(w, h) -> str:
    return f"📐 {w} × {h} px   ·   {_ar_label(w, h)}   ·   {w * h / MP_PIXELS:.2f} MP"


def profile_line(name) -> str:
    prof = _profile(name)
    if not prof:
        return ""
    name = resolve_profile_name(name)
    parts = [f"{name}: grid /{prof['multiple_of']}", f"sides {prof['min_dim']}–{prof['max_dim']} px"]
    if prof.get("recommended_mp"):
        parts.append(f"trained ~{prof['recommended_mp']:g} MP")
    if prof.get("custom"):
        parts.append(f"your sizes (based on {prof.get('based_on')})")
    elif not prof.get("verified"):
        parts.append("community sizes")
    return "ℹ " + ", ".join(parts)


def _info_lines(info: str, is_fallback: bool):
    lines = []
    for i, part in enumerate(p.strip() for p in str(info).split(" | ") if p.strip()):
        if part.startswith(("NOTE:", "UNRESOLVED:")):
            lines.append("⚠ " + part.replace("NOTE: ", "", 1))
        elif part.startswith("repaired:"):
            lines.append("🔧 " + part)
        elif i == 0:
            lines.append(("↪ " if is_fallback else "✔ ") + part)
        else:
            lines.append("• " + part)
    return lines


def _core_lines(node_cls, kwargs, vals):
    lines = _info_lines(vals.get("info", ""), bool(vals.get("is_fallback")))
    table, bad, labels = node_cls.custom_table_report(kwargs.get("custom_table", ""))
    if table:
        used = vals.get("matched_ar")
        from_table = str(vals.get("info", "")).startswith(("custom table", "ar_input"))
        entries = [("▶ " if labels[ar] == used and from_table and "custom table" in vals.get("info", "") else "")
                   + f"{labels[ar]} = {w}×{h}" for ar, (w, h) in table.items()]
        lines.append("🗂 custom table: " + ", ".join(entries))
    elif bad:
        lines.append("🗂 custom table: no valid entries")
    line = profile_line(kwargs.get("model_profile"))
    if line:
        lines.append(line)
    return lines


def _picker_lines(node_cls, kwargs, vals):
    lines = [f"✔ preset {kwargs.get('preset', '')}"]
    if str(kwargs.get("orientation", "as listed")) != "as listed":
        lines.append(f"• orientation: {kwargs['orientation']}")
    try:
        scale = float(kwargs.get("scale", 1.0))
    except (TypeError, ValueError):
        scale = 1.0
    if abs(scale - 1.0) > 1e-9:
        lines.append(f"• scaled ×{scale:g} and rounded to the model grid")
    line = profile_line(str(vals.get("label", "")).split(" | ")[0])
    if line:
        lines.append(line)
    return lines


def _megapixel_lines(node_cls, kwargs, vals):
    try:
        asked = float(kwargs.get("target_megapixels", 0))
    except (TypeError, ValueError):
        asked = 0.0
    return [f"• asked {asked:g} MP for {kwargs.get('aspect_ratio', '')}, grid /{kwargs.get('alignment', '')}"]


def _nearest_lines(node_cls, kwargs, vals):
    lines = [f"✔ nearest native size: {vals.get('matched_ar', '')}"]
    line = profile_line(kwargs.get("model_profile"))
    return lines + ([line] if line else [])


def _step_lines(node_cls, kwargs, vals):
    if kwargs.get("mode") == "snap":
        lines = [f"✔ snapped to native size ({vals.get('ar_string', '')})"]
    else:
        lines = [f"✔ {kwargs.get('direction', 'up')} {kwargs.get('steps', 1)} step(s) on the "
                 f"{vals.get('ar_string', '')} lattice → step #{vals.get('bucket_index', '')}"]
    line = profile_line(kwargs.get("model_profile"))
    return lines + ([line] if line else [])


def _prompt_extractor_lines(node_cls, kwargs, vals):
    lines = []
    if kwargs.get("extract_ar", True):
        lines.append(f"✔ ar {vals.get('ar')}" if vals.get("found_ar") else f"↪ no ratio found, using {vals.get('ar')}")
    if kwargs.get("extract_resolution", True):
        lines.append("✔ resolution found" if vals.get("found_resolution") else "↪ no resolution found")
    if str(kwargs.get("custom_key", "")).strip():
        key = str(kwargs["custom_key"]).strip()
        lines.append(f"✔ {key} = {vals.get('custom_value')}" if vals.get("found_custom") else f"↪ {key} not found")
    if vals.get("found_prompt"):
        lines.append("✔ prompt taken out of the JSON text")
    elif str(kwargs.get("prompt_key", "")).strip():
        lines.append("↪ prompt key not found, whole text returned")
    if kwargs.get("remove_found"):
        lines.append("• found items removed from the prompt")
    return lines


SPECIAL = {
    "KDX_Prompt_Extractor": _prompt_extractor_lines,
    "KDX_AutoResolution_Core": _core_lines,
    "KDX_Preset_Picker": _picker_lines,
    "KDX_Megapixel_Selector": _megapixel_lines,
    "KDX_Nearest_Native_Preset": _nearest_lines,
    "KDX_Resolution_Step": _step_lines,
}


def summarize(node_name, node_cls, kwargs, outputs) -> str:
    vals = dict(zip(node_cls.RETURN_NAMES, outputs, strict=False))
    lines, used = [], set()
    for wk, hk in SIZE_KEYS:
        w, h = vals.get(wk), vals.get(hk)
        if vals.get("found_resolution") is False:  # width/height are only fallbacks
            break
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            lines.append(size_line(w, h))
            used |= {wk, hk}
            break
    special = SPECIAL.get(node_name)
    if special:
        lines += special(node_cls, kwargs, vals)
    else:
        for k, v in vals.items():
            if k not in used:
                lines.append(f"{k}: {v}")
    return "\n".join(lines)
