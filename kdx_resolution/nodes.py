"""ComfyUI node classes (V1 API) for KDX-Resolution.

Input names and order are part of the saved-workflow format (``widgets_values``
is positional): never rename, reorder or remove inputs; add new ones at the end.
"""

import json
import math
import random
import re
from fractions import Fraction

from .presets import _WH_RE, _ar_label, _load_registry
from .profiles import (
    MP_PIXELS,
    _mp_pixels,
    _profile,
    profile_names,
    resolve_profile_name,
    validate_profile_name,
)
from .solver import (
    FALLBACK_AR_TOL,
    _clamp_dim,
    _norm_ar,
    _parse_ar_to_fraction,
    _reduce_ar,
    ar_drift,
    lattice_solve_exact,
    lattice_step,
    nearest_native_preset,
    parse_mp_grid,
    round3,
    validate_resolution,
)
from .summary import summarize

CATEGORY = "KDX/Resolution"

#: Input right above every model dropdown: which models the dropdown lists
#: (filtering happens in the editor, web/kdx_resolution_settings.js).
#: It does not change the result.
MODEL_LISTS = ["all models", "image models", "video models"]
MODEL_LIST_INPUT = (MODEL_LISTS, {
    "default": "all models",
    "tooltip": "Which models the model dropdown below offers (image / video / all). Only filters the "
               "list; more options in Settings -> KDX Resolution.",
})

#: Official native tables use the model makers' rounded labels (SDXL 1152x896
#: is "4:3" with 3.6 % drift); only larger drifts are reported for them.
NATIVE_AR_TOL = 0.05


def _positive_wh(width, height, default=(1024, 1024)):
    """Coerce (width, height) to ints; a zero/negative/missing side (bypassed or
    unconnected input) falls back to ``default``."""
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return default
    return (w, h) if w > 0 and h > 0 else default


def _mp(w, h):
    return round(w * h / MP_PIXELS, 4)


# ============================================================================
# 1. AR EXTRACTOR: Unified JSON / free-text / marker AR extraction
# ============================================================================
class KDX_AR_Extractor:
    """Extract an aspect ratio from JSON, free text, or --ar markers.

    Modes:
      - json:  parse JSON, walk dotted key path (default 'aspect_ratio');
               list indices work too ('shots.0.ar'); JSON inside prose or a
               ```json fence is found
      - text:  regex-search free text for W:H / W/H / WxH patterns
      - marker: search for --ar3:2, --ar 3:2, --aspect 16:9 style markers
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["json", "text", "marker"],
                         {"default": "json",
                          "tooltip": "json = parse JSON key, text = free-text regex, marker = --arN:M tags"}),
                "input_text": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Input text. Empty = use fallback_value."}),
                "key": ("STRING", {"default": "aspect_ratio",
                                    "tooltip": "Dotted JSON key path (json mode only)"}),
                "fallback_value": ("STRING", {"default": "1:1",
                    "tooltip": "Returned (with is_fallback = true) when nothing usable is found."}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("extracted_ar", "is_fallback")
    FUNCTION = "extract"
    CATEGORY = CATEGORY

    # --ar3:2  /  --ar 3:2  /  --aspect 16:9  /  --aspect-ratio 9:16
    _MARKER_RE = re.compile(
        r"--(?:ar|aspect(?:-ratio)?)\s*[:=]?\s*(\d+\s*[:/x]\s*\d+)",
        re.IGNORECASE,
    )
    _AR_RE = re.compile(r"(?<!\d)(\d{1,4})\s*[:/xX]\s*(\d{1,4})(?!\d)")

    def extract(self, mode, input_text, key="aspect_ratio", fallback_value="1:1"):
        fallback = (str(fallback_value).strip(), True)
        # Bypass/unconnected: input_text may be empty
        if not input_text or not str(input_text).strip():
            return fallback
        text = str(input_text)
        try:
            if mode == "json":
                ar = self._extract_json(text, key)
            elif mode == "marker":
                ar = self._extract_marker(text)
            else:  # text
                ar = self._extract_text(text)
        except (ValueError, TypeError):  # invalid JSON, odd key types
            return fallback
        ar = _norm_ar(ar) if ar else ""
        if ar and _parse_ar_to_fraction(ar) is not None:
            return (ar, False)
        return fallback

    def _extract_json(self, text: str, key: str) -> str:
        clean = re.sub(r"```(?:json)?|```", "", text).strip()
        try:
            data = json.loads(clean)
        except ValueError:
            # JSON embedded in prose ("Sure! {...}"): take the outermost {...}
            start, end = clean.find("{"), clean.rfind("}")
            if start < 0 or end <= start:
                return ""
            data = json.loads(clean[start:end + 1])
        for k in str(key or "").split("."):
            if isinstance(data, dict):
                data = data.get(k)
            elif isinstance(data, list) and re.fullmatch(r"-?\d+", k) and -len(data) <= int(k) < len(data):
                data = data[int(k)]
            else:
                return ""
            if data is None:
                return ""
        if isinstance(data, (dict, list)):
            return ""
        # Values like "16:9", "3x2" or "16:9 (widescreen)"
        return self._extract_text(str(data))

    def _extract_marker(self, text: str) -> str:
        for m in self._MARKER_RE.finditer(text):
            ar = _norm_ar(m.group(1))
            if _parse_ar_to_fraction(ar) is not None:
                return ar
        return ""

    def _extract_text(self, text: str) -> str:
        # First W:H / W/H / WxH with both sides > 0.  Lookarounds avoid false
        # positives from adjacent digits ("model 2 16:9" must not match "216:9").
        for m in self._AR_RE.finditer(str(text)):
            if int(m.group(1)) > 0 and int(m.group(2)) > 0:
                return f"{m.group(1)}:{m.group(2)}"
        return ""


# ============================================================================
# 1b. PROMPT EXTRACTOR: AR / resolution / custom key out of free text
# ============================================================================
class KDX_Prompt_Extractor:
    """Pull an aspect ratio, a resolution and/or one custom value out of a prompt.

    - AR:         16:9, 16/9, 3x2           (small numbers with x, or any W:H / W/H)
    - resolution: 1920x1080, 1920*1080, 1920 × 1080   (both sides >= 64 with x * ×)
    - custom key: ``key: value``, ``key=value``, ``"key": "value"``, ``--key value``
      (works on broken JSON too: nothing is parsed, the text is only searched)

    A ``--ar 4:3`` style marker always wins over a plain match.  Otherwise
    ``pick`` chooses the first or the last match.  With ``remove_found`` every
    match of the searched kinds is deleted from the returned prompt.
    """

    _TOKEN_RE = re.compile(
        r"""
        (?:(?P<marker>--(?:ar|aspect(?:-ratio)?|size|res(?:olution)?)\s*[:=]?\s*)
          |(?P<label>["']?\b(?:aspect[_ -]?ratio|ar|resolution|size|res)["']?\s*[:=]\s*["']?))?
        (?<![\d.])(?P<a>\d{1,5})\s*(?P<sep>[:/xX×*])\s*(?P<b>\d{1,5})(?!\d)
        """,
        re.VERBOSE | re.IGNORECASE,
    )
    #: Both sides at least this big with an x / * / × separator = a resolution, not a ratio.
    RES_MIN_SIDE = 64

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Text (prompt, LLM answer ...) to search. Empty = fallbacks."}),
                "extract_ar": ("BOOLEAN", {"default": True,
                    "tooltip": "Look for an aspect ratio: 16:9, 16/9, 3x2, --ar 4:3, aspect_ratio: 16:9."}),
                "extract_resolution": ("BOOLEAN", {"default": True,
                    "tooltip": "Look for a resolution: 1920x1080, 1920*1080, 1920 × 1080, --size 1024x768."}),
                "pick": (["first", "last"], {"default": "first",
                    "tooltip": "Which match wins when there are several. A --ar / --size marker always wins."}),
                "remove_found": ("BOOLEAN", {"default": False,
                    "tooltip": "Delete every match of the searched kinds from the returned prompt "
                               "(off = prompt is returned unchanged)."}),
                "custom_key": ("STRING", {"default": "",
                    "tooltip": "Optional: also extract the value of this key (key: value, key=value, "
                               "\"key\": \"value\", --key value). Empty = off."}),
                "fallback_ar": ("STRING", {"default": "1:1",
                    "tooltip": "Returned as ar when no ratio is found (found_ar = false)."}),
                "fallback_width": ("INT", {"default": 1024, "min": 0, "max": 65536,
                    "tooltip": "Returned as width when no resolution is found (found_resolution = false)."}),
                "fallback_height": ("INT", {"default": 1024, "min": 0, "max": 65536,
                    "tooltip": "Returned as height when no resolution is found."}),
                "ar_key": ("STRING", {"default": "",
                    "tooltip": "Optional: read the aspect ratio from this key (e.g. aspect_ratio). Not found / empty = "
                               "search the text for a ratio (outside the prompt field first), then fallback_ar."}),
                "resolution_key": ("STRING", {"default": "",
                    "tooltip": "Optional: read the resolution from this key (e.g. size). Not found / empty = "
                               "search the text for a resolution, then the fallback size."}),
                "prompt_key": ("STRING", {"default": "",
                    "tooltip": "Optional: the key that holds the prompt (e.g. rewritten_prompt). "
                               "When found, prompt is just that value (escapes undone, works on cut-off JSON). "
                               "Not found / empty: JSON-looking text -> its longest text field; "
                               "plain text -> the whole text."}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "STRING", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = ("prompt", "ar", "width", "height", "custom_value",
                    "found_ar", "found_resolution", "found_custom", "found_prompt")
    FUNCTION = "extract"
    CATEGORY = CATEGORY

    @classmethod
    def _scan(cls, text, want_ar, want_res):
        items = []
        for m in cls._TOKEN_RE.finditer(text):
            a, b, sep = int(m.group("a")), int(m.group("b")), m.group("sep")
            if a <= 0 or b <= 0:
                continue
            is_res = sep not in ":/" and a >= cls.RES_MIN_SIDE and b >= cls.RES_MIN_SIDE
            if is_res and not want_res or not is_res and not want_ar:
                continue
            start, end = m.start(), m.end()
            label = m.group("label")
            if label and label.rstrip()[-1:] in "\"'" and text[end:end + 1] == label.rstrip()[-1]:
                end += 1  # closing quote of "ar": "16:9"
            items.append({"kind": "res" if is_res else "ar", "a": a, "b": b,
                          "marker": bool(m.group("marker")), "span": (start, end)})
        return items

    @staticmethod
    def _unescape(s):
        try:
            return json.loads('"' + s + '"', strict=False)
        except ValueError:
            return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")

    @classmethod
    def _scan_custom(cls, text, key):
        """Values of ``key`` anywhere in ``text`` (nothing is parsed, so broken JSON is fine).

        A "quoted" value may contain \\" and line breaks; a value whose closing quote
        is missing (cut-off answer) runs to the end of the text."""
        key = key.strip()
        if not key:
            return []
        k = re.escape(key)
        items = []
        pair = re.compile(
            r"""(?<!\w)["']?""" + k + r"""(?!\w)["']?\s*[:=]\s*"""
            r"""(?:"(?P<dq>(?:[^"\\]|\\.)*)"|"(?P<open>.*)\Z"""
            r"""|'(?P<sq>[^'\n]*)'|(?P<raw>[^,;\n}\]]*))""", re.IGNORECASE | re.DOTALL)
        for m in pair.finditer(text):
            if m.group("dq") is not None:
                val = cls._unescape(m.group("dq")).strip()
            elif m.group("open") is not None:   # cut off: drop trailing } and quotes
                val = cls._unescape(re.sub(r'[\s"}\]]+$', "", m.group("open"))).strip()
            else:
                val = (m.group("sq") if m.group("sq") is not None else m.group("raw") or "").strip()
            if val:
                items.append({"value": val, "marker": False, "span": m.span()})
        flag = re.compile(r"--" + k + r"(?!\w)[\s=:]+(?P<v>\S+)", re.IGNORECASE)
        for m in flag.finditer(text):
            items.append({"value": m.group("v"), "marker": True, "span": m.span()})
        items.sort(key=lambda i: i["span"][0])
        return items

    @staticmethod
    def _choose(items, pick):
        if not items:
            return None
        pool = [i for i in items if i["marker"]] or items
        return pool[0] if pick == "first" else pool[-1]

    @staticmethod
    def _remove(text, spans):
        merged = []
        for s, e in sorted(spans):
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        for s, e in reversed(merged):
            text = text[:s] + text[e:]
        text = re.sub(r"\(\s*\)|\[\s*\]", "", text)   # "(16:9)" left "()"
        text = re.sub(r"[ \t]+([,;])", r"\1", text)    # "cat , dog"
        text = re.sub(r"([,;])(?:\s*[,;])+", r"\1", text)  # "a, , b"
        text = re.sub(r",\s*([.!?])", r"\1", text)     # "waist up, 3:4." -> "waist up."
        text = re.sub(r"([.!?])\s*,\s*", r"\1 ", text)  # "up. 3:4, shot" -> "up. shot"
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip(" \t\n,;")

    _JSON_FIELD_RE = re.compile(
        r'"(?P<k>[^"\\\n]+)"\s*:\s*(?:"(?P<v>(?:[^"\\]|\\.)*)"|"(?P<open>.*)\Z)', re.DOTALL)

    def _auto_prompt(self, text):
        """No prompt key given / found: if the text looks like JSON, the prompt is its longest
        text field (ratios and sizes are skipped).  Plain text returns None."""
        body = re.sub(r"```[A-Za-z]*", "", text).strip()
        if not body.startswith(("{", "[")):
            return None
        best = None
        for m in self._JSON_FIELD_RE.finditer(body):
            raw = m.group("v") if m.group("v") is not None else re.sub(r'[\s"}\]]+$', "", m.group("open"))
            val = self._unescape(raw).strip()
            if not val or self._TOKEN_RE.fullmatch(val):
                continue
            if best is None or len(val) > len(best):
                best = val
        return best

    def _kind_items(self, text, key, kind, enabled, masked):
        """(matches, spans to delete, found by pattern) for one kind.

        Order: the named key (if any) -> pattern search outside the prompt field ->
        pattern search in the whole text.  Nothing found = empty (the caller uses its fallback)."""
        if not enabled:
            return [], [], False
        key = str(key or "").strip()
        if key:
            items, spans = [], []
            for k in self._scan_custom(text, key):
                sub = self._scan(k["value"], kind == "ar", kind == "res")
                hit = [dict(i, marker=False) for i in sub if i["kind"] == kind]
                if hit:
                    spans.append(k["span"])
                    items += hit
            if items:
                return items, spans, False
        for source in (masked, text):
            items = [i for i in self._scan(source, kind == "ar", kind == "res") if i["kind"] == kind]
            if items:
                return items, [i["span"] for i in items], True
        return [], [], True

    def extract(self, input_text, extract_ar=True, extract_resolution=True, pick="first",
                remove_found=False, custom_key="", fallback_ar="1:1",
                fallback_width=1024, fallback_height=1024,
                ar_key="", resolution_key="", prompt_key=""):
        text = "" if input_text is None else str(input_text)
        fb_w, fb_h = _positive_wh(fallback_width, fallback_height)
        ar, width, height, custom = str(fallback_ar).strip(), fb_w, fb_h, ""
        if not text.strip():
            return (text, ar, width, height, custom, False, False, False, False)
        pick = "last" if pick == "last" else "first"

        # prompt: its key, else (JSON-looking text) the longest text field, else the whole text
        best_prompt = self._choose(self._scan_custom(text, str(prompt_key or "")), pick)
        prompt_value, prompt_span = None, None
        if best_prompt:
            prompt_value, prompt_span = best_prompt["value"], best_prompt["span"]
        else:
            auto = self._auto_prompt(text)
            if auto:
                prompt_value = auto
                for m in self._JSON_FIELD_RE.finditer(text):
                    if self._unescape(m.group("v") if m.group("v") is not None else "").strip() == auto:
                        prompt_span = m.span()
                        break
        masked = text
        if prompt_span:  # ratios inside the prompt text are only a last resort
            masked = text[:prompt_span[0]] + " " * (prompt_span[1] - prompt_span[0]) + text[prompt_span[1]:]

        ar_items, ar_spans, ar_pat = self._kind_items(text, ar_key, "ar", extract_ar, masked)
        res_items, res_spans, res_pat = self._kind_items(text, resolution_key, "res", extract_resolution, masked)
        custom_items = self._scan_custom(text, str(custom_key or ""))
        best_ar = self._choose(ar_items, pick)
        best_res = self._choose(res_items, pick)
        best_custom = self._choose(custom_items, pick)
        if best_ar:
            ar = f"{best_ar['a']}:{best_ar['b']}"
        if best_res:
            width, height = best_res["a"], best_res["b"]
        if best_custom:
            custom = best_custom["value"]

        if prompt_value is not None:
            out = prompt_value
            if remove_found:  # ratios / sizes written inside the prompt itself
                spans = []
                if best_ar and ar_pat:
                    spans += [i["span"] for i in self._scan(out, True, False) if i["kind"] == "ar"]
                if best_res and res_pat:
                    spans += [i["span"] for i in self._scan(out, False, True) if i["kind"] == "res"]
                out = self._remove(out, spans) if spans else out
        else:
            out = text
            spans = ar_spans + res_spans + [i["span"] for i in custom_items]
            if remove_found and spans:
                out = self._remove(text, spans)
        return (out, ar, width, height, custom, bool(best_ar), bool(best_res),
                bool(best_custom), prompt_value is not None)


# ============================================================================
# 2. CORE NODE: AR + target MP -> (width, height)
# ============================================================================
class KDX_AutoResolution_Core:
    """Resolve an aspect ratio to concrete (width, height).

    Resolution chain:
      1. direct_override ("1920x1080")            -> as-is, validated
      2. unusable ar_input                        -> fallback_ar is used instead
      3. target_megapixels == 0 and AR in table   -> official native value
      4. target_megapixels > 0                    -> manual MP grid (snapped to
                                                     the AR), else lattice solve
      5. otherwise                                -> nearest native preset by AR
      6. no usable AR at all                      -> base resolution square

    ARs are reduced before lookup ("32:18" and "1920x1080" match "16:9").
    Every result is re-validated (divisibility, min/max, AR tolerance);
    violations are repaired when possible, otherwise reported in `info`.
    """

    # -- custom table parser --
    _TABLE_LINE = re.compile(
        r"^(\d+[:/x]\d+)\s*[:=]\s*(\d+)\s*[,xX\s]\s*(\d+)$"
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ar_input": ("STRING", {"default": "1:1",
                    "tooltip": "Aspect ratio (from Extractor or manual). Empty = fallback_ar."}),
                "model_list": MODEL_LIST_INPUT,
                "model_profile": (profile_names(), {
                    "tooltip": "Model family — selects native table, alignment and bounds."}),
                "target_megapixels": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 50.0, "step": 0.25,
                    "tooltip": "0 = use the model's native table. >0 = compute on the AR grid at this MP "
                               "(ComfyUI convention: 1 MP = 1024x1024).",
                }),
                "custom_table": ("STRING", {
                    "multiline": True,
                    "default": "# Custom AR table:  AR = W, H\n# 21:9 = 3072, 1312\n# 1:2 = 1024, 2048",
                    "tooltip": "Extra AR entries merged over the model table. Format: 'W:H = Wpx, Hpx' "
                               "(one per line, # = comment)",
                }),
                "mp_grid": ("STRING", {
                    "multiline": True,
                    "default": ("# Manual MP grid:  X MP = WxH\n# Used when target_megapixels > 0\n"
                                "# 1.0 MP = 1024x1024\n# 4.0 MP = 2048x2048"),
                    "tooltip": "Manual MP grid. Format: 'X MP = WxH' (one per line, # = comment). "
                               "When target_megapixels > 0, the closest entry is used: as-is if it already "
                               "has the requested AR, otherwise its size is re-solved for that AR. "
                               "Empty = lattice-solve from AR + MP.",
                }),
                "fallback_ar": ("STRING", {"default": "1:1",
                    "tooltip": "Used when ar_input is empty or not a valid W:H ratio."}),
                "alignment": (["default"] + [str(m) for m in (8, 16, 32, 64)], {
                    "default": "default",
                    "tooltip": "VAE alignment (divisor). 'default' = the selected model's multiple_of; "
                               "override only if you know why.",
                }),
            },
            "optional": {
                "direct_override": ("STRING", {
                    "default": "",
                    "tooltip": 'Bypass all logic. "1920x1080" or "1920, 1080". Empty = disabled.',
                }),
            },
        }

    RETURN_TYPES = ("INT", "INT", "STRING", "FLOAT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("width", "height", "matched_ar", "actual_mp", "is_fallback", "info")
    FUNCTION = "resolve"
    CATEGORY = CATEGORY

    @classmethod
    def VALIDATE_INPUTS(cls, model_profile=None):
        # Accept old profile names from saved workflows (e.g. a renamed profile).
        return validate_profile_name(model_profile)

    @classmethod
    def custom_table_report(cls, text: str):
        """Parse custom_table -> ({reduced AR: (w, h)}, [lines not understood], {reduced AR: label})."""
        table, bad, labels = {}, [], {}
        for line in str(text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = cls._TABLE_LINE.match(line.replace(" ", ""))
            if m and int(m.group(2)) > 0 and int(m.group(3)) > 0 and _parse_ar_to_fraction(_reduce_ar(m.group(1))):
                key = _reduce_ar(m.group(1))
                table[key] = (int(m.group(2)), int(m.group(3)))
                labels[key] = _norm_ar(m.group(1))  # keep the user's spelling ("21:9", not "7:3")
            else:
                bad.append(line[:60])
        return table, bad, labels

    def _parse_custom_table(self, text: str) -> dict:
        return self.custom_table_report(text)[0]

    @staticmethod
    def _nearest_native_by_ar(ar_frac: Fraction, prof: dict):
        """Nearest native preset by AR.

        Entries of the opposite orientation are skipped (square entries are
        always allowed).  Score: |log(ratio / preset_ratio)| — a symmetric AR
        distance — plus 0.05 x relative distance from the table's median area
        as a tie-break, so a 2:1 request lands on 16:9 even when the table's
        sizes differ a lot (video models).
        """
        table = prof.get("native_resolutions", {})
        if not table:
            return ("", 0, 0)
        actual = float(ar_frac)
        areas = sorted(w * h for w, h in table.values())
        median = areas[len(areas) // 2]
        cands = []
        for ar, (pw, ph) in table.items():
            if pw != ph and actual != 1.0 and (pw > ph) != (actual > 1.0):
                continue
            score = abs(math.log(actual / (pw / ph))) + 0.05 * abs(pw * ph - median) / median
            cands.append((score, ar, pw, ph))
        if not cands:
            return ("", 0, 0)
        _, ar, pw, ph = min(cands, key=lambda c: c[0])
        return (ar, pw, ph)

    @staticmethod
    def _size_notes(prof: dict, name: str, target_px: float) -> str:
        """Warnings for a target size the model was not made for (shown in `info`)."""
        target_mp = target_px / MP_PIXELS
        max_mp = prof.get("max_mp")
        rec_mp = prof.get("recommended_mp")
        if max_mp and target_mp > max_mp:
            return f" | NOTE: limited to {name}'s maximum of {max_mp:g} MP"
        if rec_mp and target_mp > 2 * rec_mp:
            return (f" | NOTE: {target_mp:.3g} MP is far above what {name} was trained for "
                    f"(~{rec_mp:g} MP) - expect repeated subjects/artifacts; consider an upscale pass")
        max_dim = prof.get("max_dim")
        if max_dim and target_px > max_dim * max_dim:
            return f" | NOTE: limited by {name}'s max side {max_dim} px"
        return ""

    def resolve(self, ar_input, model_profile, target_megapixels=0.0,
                custom_table="", mp_grid="", fallback_ar="1:1", alignment="default",
                direct_override="", model_list="all models"):

        prof = _profile(model_profile) or {}
        base = prof.get("base_resolution", 1024)
        min_dim = prof.get("min_dim", 1)
        max_dim = prof.get("max_dim", 8192)
        model_align = prof.get("multiple_of", 32)
        # Default alignment = the model's multiple_of; explicit option wins.
        align = model_align
        if str(alignment).strip().isdigit() and int(alignment) >= 1:
            align = int(alignment)
        try:
            target_mp = max(0.0, float(target_megapixels or 0.0))
        except (TypeError, ValueError):
            target_mp = 0.0

        custom, bad_lines, custom_labels = self.custom_table_report(custom_table)
        native = prof.get("native_resolutions", {})
        lookup = {_reduce_ar(k): v for k, v in native.items()}
        lookup.update(custom)
        # ARs are compared reduced ("32:18" == "16:9", "21:9" == "7:3") but shown
        # the way the table writes them.
        labels = {_reduce_ar(k): k for k in native}
        labels.update(custom_labels)
        notes = ""
        if bad_lines:
            shown = ", ".join(repr(b) for b in bad_lines[:3]) + (" ..." if len(bad_lines) > 3 else "")
            notes += f" | NOTE: custom_table line(s) not understood: {shown} (format 'W:H = width, height')"

        # 1. direct override (validated, reported if off-contract)
        if direct_override and str(direct_override).strip():
            m = re.search(r"(\d+)\s*[xX,]\s*(\d+)", str(direct_override))
            if m and int(m.group(1)) > 0 and int(m.group(2)) > 0:
                w, h = int(m.group(1)), int(m.group(2))
                ok, problems = validate_resolution(w, h, None, align, min_dim, max_dim)
                info = f"override {w}x{h}"
                if not ok:
                    info += f" | NOTE: {problems} (used as-is)"
                return (w, h, "override", _mp(w, h), False, info)
            notes = f" | ignored invalid direct_override {str(direct_override).strip()!r}"

        # 2. normalize + reduce the AR; an unusable AR switches to fallback_ar
        ar = _reduce_ar(ar_input) if str(ar_input or "").strip() else ""
        ar_frac = _parse_ar_to_fraction(ar)
        is_fallback = False
        prefix = ""
        if ar_frac is None:
            fb = _reduce_ar(fallback_ar) if str(fallback_ar or "").strip() else ""
            fb_frac = _parse_ar_to_fraction(fb)
            if fb_frac is not None:
                prefix = f"ar_input {str(ar_input or '').strip()!r} unusable -> fallback_ar {fb} | "
                ar, ar_frac, is_fallback = fb, fb_frac, True
        ar_shown = labels.get(ar, ar)
        if ar not in labels and not is_fallback:
            # keep a simple input spelling ("21:9" rather than the reduced "7:3")
            typed = _norm_ar(ar_input)
            parts = typed.split(":")
            if _reduce_ar(typed) == ar and all(x.isdigit() and int(x) <= 100 for x in parts):
                ar_shown = typed
        final_ar = ar_shown

        if ar_frac is None:
            # 6. last resort: base resolution square
            w = h = _clamp_dim(base, align, min_dim, max_dim)
            final_ar = "1:1"
            info = f"last resort: base {w}x{h} (no usable AR)"
            is_fallback = True

        elif target_mp <= 0 and ar in lookup:
            # 3. official value
            w, h = lookup[ar]
            source = "custom table" if ar in custom else "native table"
            tol = FALLBACK_AR_TOL if ar in custom else NATIVE_AR_TOL
            ok, problems = validate_resolution(w, h, ar_frac, align, min_dim, max_dim, ar_tol=tol)
            info = f"{source} {ar_shown}" + (f" | NOTE: {problems}" if not ok else "")

        elif target_mp > 0:
            # 4. manual MP grid or lattice solve
            grid = parse_mp_grid(mp_grid)
            target_px = _mp_pixels(target_mp)
            if grid:
                best_mp = min(grid, key=lambda mp: abs(mp - target_mp))
                gw, gh = grid[best_mp]
                if ar_drift(gw, gh, ar_frac) <= FALLBACK_AR_TOL:
                    # The entry already has the requested AR: explicit user intent, as-is.
                    ok, problems = validate_resolution(gw, gh, None, align, min_dim, max_dim)
                    info = f"manual MP grid @ {best_mp:g} MP"
                    if not ok:
                        info += f" | NOTE: {problems} (used as-is)"
                    return (gw, gh, ar_shown, _mp(gw, gh), is_fallback or ar not in lookup, prefix + info + notes)
                target_px = float(gw * gh)
                info = f"manual MP grid @ {best_mp:g} MP ({gw}x{gh}) re-solved for {ar_shown}"
            else:
                info = f"lattice solve @ {target_mp:g} MP (exact {ar_shown})"
            notes += self._size_notes(prof, resolve_profile_name(model_profile), target_px)
            max_mp = prof.get("max_mp")
            if max_mp and target_px > _mp_pixels(max_mp):
                target_px = _mp_pixels(max_mp)
            side = math.sqrt(target_px)  # float: keep the exact target area
            # The lattice uses the MODEL's grid (its native table is on that
            # grid); a user alignment override is checked and repaired below.
            w, h = lattice_solve_exact(ar_frac.numerator, ar_frac.denominator, side, side,
                                       model_align, min_dim, max_dim)
            if ar_drift(w, h, ar_frac):
                info = info.replace("(exact ", "(nearest grid point for ")
            is_fallback = is_fallback or ar not in lookup
            ok, problems = validate_resolution(w, h, ar_frac, align, min_dim, max_dim)
            if not ok:
                # repair: re-solve on the REQUIRED grid
                w, h = lattice_solve_exact(ar_frac.numerator, ar_frac.denominator, side, side,
                                           align, min_dim, max_dim)
                info += f" | repaired: {problems}"
                ok, problems = validate_resolution(w, h, ar_frac, align, min_dim, max_dim)
                if not ok:
                    info += f" | UNRESOLVED: {problems}"

        else:
            # 5. nearest native preset by AR
            ar_n, w, h = self._nearest_native_by_ar(ar_frac, prof)
            if ar_n and w:
                final_ar = ar_n
                info = f"nearest native preset ({ar_shown} -> {ar_n})"
                is_fallback = is_fallback or _reduce_ar(ar_n) != ar
            else:
                w, h = round3(ar_frac, float(base) * base, align)
                w, h = _clamp_dim(w, align, min_dim, max_dim), _clamp_dim(h, align, min_dim, max_dim)
                info = f"round3 @ base {base}^2 (no native table match for {ar_shown})"
                is_fallback = True

        return (int(w), int(h), final_ar, _mp(w, h), is_fallback, prefix + info + notes)


# ============================================================================
# 3. AR VALIDATOR
# ============================================================================
class KDX_AR_Validator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_to_check": ("STRING", {"default": "1:1",
                    "tooltip": "Text containing an AR (first W:H / W/H / WxH is checked)."}),
                "known_ratios": ("STRING", {
                    "default": "1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16",
                    "tooltip": "Comma-separated list of valid ARs (colon form)",
                }),
            }
        }
    RETURN_TYPES = ("BOOLEAN", "STRING")
    RETURN_NAMES = ("is_valid", "extracted_ar")
    FUNCTION = "validate"
    CATEGORY = CATEGORY

    def validate(self, text_to_check, known_ratios):
        # Compare reduced forms: "32:18" matches "16:9".  The allowed spelling is returned.
        allowed = {}
        for r in str(known_ratios).split(","):
            if r.strip():
                allowed.setdefault(_reduce_ar(r), _norm_ar(r))
        clean = str(text_to_check).replace(" ", "")
        m = re.search(r"(\d+[:/xX]\d+)", clean)
        if m:
            key = _reduce_ar(m.group(1))
            if key in allowed:
                return (True, allowed[key])
        return (False, "")


# ============================================================================
# 4. REVERSE MATCHER: INT W/H -> closest AR string
# ============================================================================
class KDX_Reverse_AR_Matcher:
    KNOWN_RATIOS = [
        "1:1", "4:3", "3:4", "3:2", "2:3",
        "5:4", "4:5", "5:3", "3:5",
        "8:5", "5:8",
        "16:10", "10:16",
        "16:9", "9:16", "21:9", "9:21",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                   "tooltip": "Width in px (0 / unconnected = 1024)."}),
                "height": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                    "tooltip": "Height in px (0 / unconnected = 1024)."}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("closest_ar_string", "exact_ratio_float")
    FUNCTION = "calculate"
    CATEGORY = CATEGORY

    def calculate(self, width, height):
        w, h = _positive_wh(width, height)
        actual = w / h
        # log distance: symmetric for landscape and portrait (2:1 vs 1:2)
        closest = min(
            self.KNOWN_RATIOS,
            key=lambda ar: abs(math.log(actual / float(_parse_ar_to_fraction(ar)))),
        )
        return (closest, round(actual, 4))


# ============================================================================
# 5. SCALER & ALIGNER
# ============================================================================
class KDX_Resolution_Scaler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                   "tooltip": "Width in px (0 / unconnected = 1024)."}),
                "height": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                    "tooltip": "Height in px (0 / unconnected = 1024)."}),
                "scale_factor": ("FLOAT", {"default": 1.5, "min": 0.1, "max": 4.0, "step": 0.05,
                    "tooltip": "Multiply both sides by this (e.g. 1.5 for a hires-fix pass)."}),
                "alignment": ([str(m) for m in (8, 16, 32, 64)], {"default": "32",
                    "tooltip": "Round both sides to a multiple of this (VAE grid)."}),
            }
        }
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("aligned_width", "aligned_height")
    FUNCTION = "scale"
    CATEGORY = CATEGORY

    def scale(self, width, height, scale_factor, alignment):
        w, h = _positive_wh(width, height)
        align = max(1, int(alignment))
        fw = max(align, int(round(w * scale_factor / align)) * align)
        fh = max(align, int(round(h * scale_factor / align)) * align)
        return (fw, fh)


# ============================================================================
# 6. BATCH TESTER (local RNG — no global random state)
# ============================================================================
class KDX_AR_Batch_Tester:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ratios_list": ("STRING", {"default": "1:1, 3:2, 16:9, 21:9",
                    "tooltip": "Comma-separated ARs to cycle through."}),
                "mode": (["Sequential", "Random"], {
                    "tooltip": "Sequential = item seed % count; Random = seeded random pick."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff,
                    "tooltip": "Set control_after_generate to increment to step through the list."}),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("test_ar_string",)
    FUNCTION = "generate"
    CATEGORY = CATEGORY

    # No IS_CHANGED: the output depends only on the inputs, so ComfyUI's cache
    # is correct.  (It used to return NaN, which re-ran every downstream node
    # — e.g. the whole sampler — on each queue even with the same seed.)
    # Use the seed widget's "control after generate" to step through the list.

    def generate(self, ratios_list, mode, seed):
        ratios = [_norm_ar(r) for r in str(ratios_list).split(",") if r.strip()]
        if not ratios:
            return ("1:1",)
        if mode == "Random":
            rng = random.Random(seed)
            return (rng.choice(ratios),)
        return (ratios[seed % len(ratios)],)


# ============================================================================
# 7. MEGAPIXEL SELECTOR: AR + MP -> (W, H)  (standalone, no model table)
# ============================================================================
class KDX_Megapixel_Selector:
    """Standalone MP -> resolution. No model table, no fallback chain.
    Connect AR (STRING) + target MP (FLOAT) -> (W, H).
    MP = ComfyUI convention (1 MP = 1024x1024)."""

    MAX_DIM = 8192

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "aspect_ratio": ("STRING", {
                    "default": "1:1", "tooltip": "e.g. '16:9' (colon form)"}),
                "target_megapixels": ("FLOAT", {
                    "default": 4.0, "min": 0.06, "max": 50.0, "step": 0.25,
                    "tooltip": "ComfyUI convention: 1 MP = 1024x1024, 4 MP = 2048x2048.",
                }),
                "alignment": ([str(m) for m in (8, 16, 32, 64)], {"default": "32",
                    "tooltip": "Both sides are multiples of this (VAE grid)."}),
                "mp_grid": ("STRING", {
                    "multiline": True,
                    "default": "# Manual MP grid:  X MP = WxH\n# 1.0 MP = 1024x1024\n# 4.0 MP = 2048x2048",
                    "tooltip": "Manual MP grid. Format: 'X MP = WxH'. The closest entry is used as-is if it "
                               "has the requested AR, otherwise its size is re-solved for that AR. "
                               "Empty = lattice-solve.",
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT", "FLOAT")
    RETURN_NAMES = ("width", "height", "actual_mp")
    FUNCTION = "compute"
    CATEGORY = CATEGORY

    def compute(self, aspect_ratio, target_megapixels, alignment="32", mp_grid=""):
        align = max(1, int(alignment))
        target_mp = max(0.01, float(target_megapixels or 0.0))
        target_px = _mp_pixels(target_mp)
        frac = _parse_ar_to_fraction(_reduce_ar(aspect_ratio))
        grid = parse_mp_grid(mp_grid)
        if grid:
            best_mp = min(grid, key=lambda mp: abs(mp - target_mp))
            gw, gh = grid[best_mp]
            if frac is None or ar_drift(gw, gh, frac) <= FALLBACK_AR_TOL:
                return (gw, gh, _mp(gw, gh))  # entry already has the AR: as-is
            target_px = float(gw * gh)
        if frac is None:
            frac = Fraction(1, 1)
        side = math.sqrt(target_px)  # float: keep the exact target area
        # Lattice solve: exact AR (or within 1.5 % for very fine ratios), stdlib only
        w, h = lattice_solve_exact(frac.numerator, frac.denominator, side, side, align, align, self.MAX_DIM)
        return (w, h, _mp(w, h))


# ============================================================================
# 8. NEAREST NATIVE PRESET: (W, H) -> closest native resolution of a model
# ============================================================================
class KDX_Nearest_Native_Preset:
    """Map any (W, H) to the closest native resolution of the selected model.

    The winner scores 2*angle_error + 0.1*area_error.  Headless (INT in /
    INT out) — no torch or image tensors involved.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                   "tooltip": "Width in px (0 / unconnected = 1024)."}),
                "height": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                    "tooltip": "Height in px (0 / unconnected = 1024)."}),
                "model_list": MODEL_LIST_INPUT,
                "model_profile": (profile_names(), {
                    "tooltip": "Model whose native table to match against.",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "INT")
    RETURN_NAMES = ("matched_ar", "width", "height")
    FUNCTION = "nearest"
    CATEGORY = CATEGORY

    @classmethod
    def VALIDATE_INPUTS(cls, model_profile=None):
        return validate_profile_name(model_profile)

    def nearest(self, width, height, model_profile, model_list="all models"):
        w, h = _positive_wh(width, height)
        prof = _profile(model_profile)
        if not prof:
            raise ValueError(f"KDX Nearest Native Preset: unknown model_profile '{model_profile}'")
        return nearest_native_preset(w, h, prof)


# ============================================================================
# 9. RESOLUTION TO STRING: INT W/H -> "WxH"  (for direct_override input)
# ============================================================================
class KDX_Resolution_To_String:
    """Convert INT width + height to a 'WxH' string for KDX_AutoResolution_Core
    direct_override input."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                   "tooltip": "Width in px (0 / unconnected = 1024)."}),
                "height": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                    "tooltip": "Height in px (0 / unconnected = 1024)."}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("resolution_string",)
    FUNCTION = "to_string"
    CATEGORY = CATEGORY

    def to_string(self, width, height):
        w, h = _positive_wh(width, height)
        return (f"{w}x{h}",)


# ============================================================================
# 10. RESOLUTION STEP: step up/down on the AR lattice (next/prev bucket)
# ============================================================================
class KDX_Resolution_Step:
    """Jump N buckets on the AR lattice, or snap to the nearest native preset.

    Two modes:
    - **jump**: move N lattice steps up or down. N=1 = one bucket, N=5 = five.
      AR is preserved exactly (zero drift); at the model's min/max bounds the
      jump stops at the last bucket that still fits.  Inputs with a "messy"
      ratio (1366x768) use the closest simple ratio (16:9) so the buckets
      stay a sensible size.
    - **snap**: find the nearest native resolution from the model's
      bucket table and return it. The "click the preset" equivalent.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                   "tooltip": "Width in px (0 / unconnected = 1024)."}),
                "height": ("INT", {"default": 1024, "min": 0, "max": 16384,
                                    "tooltip": "Height in px (0 / unconnected = 1024)."}),
                "mode": (["jump", "snap"], {
                    "default": "jump",
                    "tooltip": "jump = N lattice steps, snap = nearest native preset.",
                }),
                "steps": ("INT", {
                    "default": 1, "min": 1, "max": 100,
                    "tooltip": "How many buckets to jump (mode=jump).",
                }),
                "direction": (["up", "down"], {
                    "default": "up",
                    "tooltip": "Direction (mode=jump).",
                }),
                "model_list": MODEL_LIST_INPUT,
                "model_profile": (profile_names(include_hidden=False) + ["auto"], {
                    "default": "auto",
                    "tooltip": "Model family (grid + native presets). auto = grid from the input size "
                               "(largest power of two dividing W and H, 8-64).",
                }),
            },
        }

    RETURN_TYPES = ("INT", "INT", "STRING", "INT")
    RETURN_NAMES = ("width", "height", "ar_string", "bucket_index")
    FUNCTION = "step"
    CATEGORY = CATEGORY

    @classmethod
    def VALIDATE_INPUTS(cls, model_profile=None):
        return validate_profile_name(model_profile, allow=("auto",))

    @staticmethod
    def _simple_ratio(w, h, align, max_dim):
        """Reduced ratio of (w, h); if its lattice step is too coarse to give a
        few buckets below max_dim, the closest ratio with a small denominator."""
        frac = Fraction(w, h)
        for limit in (None, 64, 32, 16, 10):
            f = frac if limit is None else frac.limit_denominator(limit)
            dw, dh = lattice_step(f.numerator, f.denominator, align)
            if 4 * max(dw, dh) <= max_dim:
                return f
        return f

    def step(self, width, height, mode, steps, direction, model_profile, model_list="all models"):
        w, h = _positive_wh(width, height)
        prof = _profile(model_profile) if resolve_profile_name(model_profile) != "auto" else None
        if prof:
            align = prof.get("multiple_of", 32)
            min_dim = prof.get("min_dim", align)
            max_dim = prof.get("max_dim", 8192)
        else:
            g = math.gcd(w, h)
            align = min(64, max(8, g & -g))  # largest power of two dividing both sides
            min_dim, max_dim = 256, 8192

        if mode == "snap":
            return self._snap(w, h, prof, align, min_dim, max_dim)

        # --- jump mode ---
        frac = self._simple_ratio(w, h, align, max_dim)
        w0, h0 = frac.numerator, frac.denominator
        dw, dh = lattice_step(w0, h0, align)
        # bucket closest to the input size
        j = max(1, min(range(max(1, w // dw - 2), w // dw + 4),
                       key=lambda k: abs(dw * k - w) + abs(dh * k - h)))
        j_next = j + int(steps) if direction == "up" else j - int(steps)
        # keep inside the feasible range so the AR stays exact at the bounds
        j_lo = max(1, math.ceil(min_dim / dw), math.ceil(min_dim / dh))
        j_hi = min(max_dim // dw, max_dim // dh)
        if j_hi >= j_lo:
            j_next = min(max(j_next, j_lo), j_hi)
            new_w, new_h = dw * j_next, dh * j_next
        else:
            j_next = max(1, j_next)
            new_w = _clamp_dim(dw * j_next, align, min_dim, max_dim)
            new_h = _clamp_dim(dh * j_next, align, min_dim, max_dim)
        return (new_w, new_h, f"{w0}:{h0}", j_next)

    def _snap(self, w, h, prof, align, min_dim, max_dim):
        if not prof:
            g = math.gcd(w, h)
            return (w, h, f"{w // g}:{h // g}", 0)

        candidates = []
        seen = set()
        for ar, (bw, bh) in prof.get("native_resolutions", {}).items():
            candidates.append((bw, bh, ar))
            seen.add((bw, bh))
        for bw, bh in prof.get("concrete_buckets", []):
            if (bw, bh) not in seen:
                g = math.gcd(bw, bh)
                candidates.append((bw, bh, f"{bw // g}:{bh // g}"))
                seen.add((bw, bh))

        if not candidates:
            g = math.gcd(w, h)
            return (w, h, f"{w // g}:{h // g}", 0)

        best, best_dist = None, float("inf")
        for bw, bh, ar in candidates:
            dist = abs(bw - w) / w + abs(bh - h) / h
            if dist < best_dist:
                best_dist, best = dist, (bw, bh, ar)

        bw, bh, ar = best
        bw = _clamp_dim(bw, align, min_dim, max_dim)
        bh = _clamp_dim(bh, align, min_dim, max_dim)
        return (bw, bh, ar, 0)


# ============================================================================
# 11. PRESET PICKER: model -> resolution preset (with JSON custom lists)
# ============================================================================
class KDX_Preset_Picker:
    """Pick a model, then a resolution preset from that model's list.

    The preset dropdown shows "Model | AR | WxH" entries. A small JS
    extension (web/kdx_preset_filter.js) filters the list when the model
    changes. Custom lists: kdx_custom_presets.json /
    kdx_custom_presets.local.json, then press R in ComfyUI.
    """

    @classmethod
    def INPUT_TYPES(cls):
        reg, _ = _load_registry()
        models = list(reg.keys())
        entries = [f"{m} | {_ar_label(w, h)} | {w}x{h}"
                   for m in models for (w, h) in reg[m]]
        return {
            "required": {
                "model_list": MODEL_LIST_INPUT,
                "model": (models, {"tooltip": "Filters the preset list."}),
                "preset": (entries, {"tooltip": "Model | AR | WxH"}),
                "orientation": (["as listed", "landscape", "portrait"], {
                    "tooltip": "Swap W/H if needed to force landscape or portrait."}),
                "scale": ("FLOAT", {
                    "default": 1.0, "min": 0.25, "max": 4.0,
                    "step": 0.05,
                    "tooltip": "1.0 = preset verbatim; otherwise rounded to grid.",
                }),
            },
        }

    RETURN_TYPES = ("INT", "INT", "STRING", "FLOAT", "STRING")
    RETURN_NAMES = ("width", "height", "ar_string", "actual_mp", "label")
    FUNCTION = "pick"
    CATEGORY = CATEGORY

    @classmethod
    def VALIDATE_INPUTS(cls, model=None, preset=None):
        # The lists come from model tables + custom JSON and differ between
        # machines/versions.  Any "... WxH" preset still works, so a saved
        # workflow must not fail with "Value not in list".
        if preset is not None and not _WH_RE.search(str(preset)):
            return f"Preset '{preset}' has no 'WxH' size (expected e.g. 'SDXL | 16:9 | 1344x768')"
        return True

    def pick(self, model, preset, orientation="as listed", scale=1.0, model_list="all models"):
        m = _WH_RE.search(str(preset))
        if not m:
            raise ValueError(f"KDX_Preset_Picker: cannot parse '{preset}'")
        w, h = int(m.group(1)), int(m.group(2))
        if w <= 0 or h <= 0:
            raise ValueError(f"KDX_Preset_Picker: invalid size in '{preset}'")
        entry_model = str(preset).split(" | ")[0] if " | " in str(preset) else str(model)

        if (orientation == "landscape" and h > w) or \
           (orientation == "portrait" and w > h):
            w, h = h, w

        if abs(scale - 1.0) > 1e-9:
            _, grids = _load_registry()
            a = grids.get(entry_model, 16)
            w = max(a, int(round(w * scale / a)) * a)
            h = max(a, int(round(h * scale / a)) * a)

        return (w, h, _ar_label(w, h), _mp(w, h), f"{entry_model} | {w}x{h}")


# ============================================================================
# REGISTRATION
# ============================================================================
NODE_CLASS_MAPPINGS = {
    "KDX_AR_Extractor": KDX_AR_Extractor,
    "KDX_Prompt_Extractor": KDX_Prompt_Extractor,
    "KDX_AutoResolution_Core": KDX_AutoResolution_Core,
    "KDX_AR_Validator": KDX_AR_Validator,
    "KDX_Reverse_AR_Matcher": KDX_Reverse_AR_Matcher,
    "KDX_Resolution_Scaler": KDX_Resolution_Scaler,
    "KDX_AR_Batch_Tester": KDX_AR_Batch_Tester,
    "KDX_Megapixel_Selector": KDX_Megapixel_Selector,
    "KDX_Nearest_Native_Preset": KDX_Nearest_Native_Preset,
    "KDX_Resolution_To_String": KDX_Resolution_To_String,
    "KDX_Resolution_Step": KDX_Resolution_Step,
    "KDX_Preset_Picker": KDX_Preset_Picker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KDX_Preset_Picker": "📑 KDX • Preset Picker",
    "KDX_AutoResolution_Core": "🎯 KDX • AutoRes Core (AR → W×H)",
    "KDX_Megapixel_Selector": "🧮 KDX • Megapixel Selector (AR + MP → W×H)",
    "KDX_AR_Extractor": "🔎 KDX • AR Extractor",
    "KDX_Prompt_Extractor": "🧾 KDX • Prompt Extractor (AR / size / key)",
    "KDX_AR_Validator": "✅ KDX • AR Validator",
    "KDX_AR_Batch_Tester": "🎲 KDX • AR Batch Tester",
    "KDX_Reverse_AR_Matcher": "↔️ KDX • Reverse AR Matcher (W×H → AR)",
    "KDX_Nearest_Native_Preset": "🧲 KDX • Nearest Native Preset",
    "KDX_Resolution_Step": "📶 KDX • Resolution Step",
    "KDX_Resolution_Scaler": "📏 KDX • Resolution Scaler",
    "KDX_Resolution_To_String": "🔗 KDX • Resolution → String",
}

# Node info panel text (DESCRIPTION), output hover tooltips and extra search
# words, kept together so the node classes above stay about behaviour.
_META = {
    "KDX_Preset_Picker": (
        "Pick a model, then one of its native resolutions (or your own list from "
        "kdx_custom_presets.local.json). Easiest way to get a correct W×H for a model.",
        ("Preset width", "Preset height", "AR label, e.g. 16:9", "W×H / 1024² (ComfyUI MP)",
         "'Model | WxH' text for notes or filenames"),
        ["resolution preset", "native resolution", "bucket", "size"],
    ),
    "KDX_AutoResolution_Core": (
        "Main resolver: aspect ratio (+ optional target megapixels) → width/height on the "
        "model's grid. Uses the model's official table when possible, otherwise an exact-AR "
        "lattice solve. The info output explains which path was taken.",
        ("Width (on the model grid)", "Height (on the model grid)",
         "AR actually used (may differ from the input, e.g. nearest native)",
         "W×H / 1024² (ComfyUI MP)", "True when a fallback/approximation was used",
         "Which rule produced the size, plus any notes"),
        ["aspect ratio", "resolution", "width height", "megapixel", "latent size"],
    ),
    "KDX_Megapixel_Selector": (
        "Aspect ratio + megapixels → width/height on a chosen grid, without any model table. "
        "1 MP = 1024×1024 (ComfyUI convention).",
        ("Width", "Height", "W×H / 1024²"),
        ["megapixel", "resolution", "aspect ratio", "size"],
    ),
    "KDX_AR_Extractor": (
        "Find an aspect ratio in an LLM JSON answer, in free text, or in a --ar 16:9 marker. "
        "Feed extracted_ar into AutoRes Core.",
        ("AR string, e.g. 16:9", "True when fallback_value was returned"),
        ["aspect ratio", "parse", "json", "--ar"],
    ),
    "KDX_Prompt_Extractor": (
        "Find an aspect ratio (16:9), a resolution (1920x1080) and/or a custom key's value in any "
        "text; works on broken JSON too. A --ar / --size marker wins, otherwise first or last match. "
        "Optionally removes the found items from the prompt.",
        ("Prompt (cleaned when remove_found is on, otherwise unchanged)",
         "AR string, e.g. 16:9 (fallback_ar when none found)",
         "Width (fallback_width when no resolution found)",
         "Height (fallback_height when no resolution found)",
         "Value of custom_key, or empty",
         "True when an aspect ratio was found", "True when a resolution was found",
         "True when custom_key was found",
         "True when the prompt was taken out of JSON-like text (by prompt_key or automatically)"),
        ["extract", "aspect ratio", "resolution", "--ar", "prompt", "parse", "key value"],
    ),
    "KDX_AR_Validator": (
        "Is the AR in this text one of the allowed ratios? (32:18 counts as 16:9.)",
        ("True if allowed", "The allowed AR that matched, or empty"),
        ["aspect ratio", "check", "allowed"],
    ),
    "KDX_AR_Batch_Tester": (
        "Step through a list of aspect ratios with the seed — handy for testing a prompt "
        "in several formats.",
        ("Current AR from the list",),
        ["aspect ratio", "batch", "test", "cycle"],
    ),
    "KDX_Reverse_AR_Matcher": (
        "Width/height → the closest common aspect ratio label.",
        ("Closest common AR, e.g. 16:9", "Exact width / height"),
        ["aspect ratio", "detect", "ratio"],
    ),
    "KDX_Nearest_Native_Preset": (
        "Any width/height → the closest official resolution of the chosen model.",
        ("AR label of the matched preset", "Native width", "Native height"),
        ["native resolution", "snap", "preset"],
    ),
    "KDX_Resolution_Step": (
        "Go N size steps up or down while keeping the aspect ratio exact (jump), or snap to "
        "the nearest native size of a model (snap).",
        ("New width", "New height", "Ratio used, e.g. 16:9", "Lattice step number (0 in snap mode)"),
        ["bucket", "upscale", "downscale", "step"],
    ),
    "KDX_Resolution_Scaler": (
        "Scale width/height by a factor and round both to the VAE grid (e.g. ×1.5 for hires fix).",
        ("Scaled width", "Scaled height"),
        ["scale", "upscale", "hires", "align"],
    ),
    "KDX_Resolution_To_String": (
        "Width/height → \"WxH\" text (e.g. for AutoRes Core's direct_override).",
        ("\"WxH\" text",),
        ["string", "text", "WxH"],
    ),
}

for _name, (_desc, _out_tips, _aliases) in _META.items():
    _cls = NODE_CLASS_MAPPINGS[_name]
    assert len(_out_tips) == len(_cls.RETURN_TYPES), _name
    _cls.DESCRIPTION = _desc
    _cls.OUTPUT_TOOLTIPS = _out_tips
    _cls.SEARCH_ALIASES = ["kdx"] + _aliases


# ----------------------------------------------------------------------------
# Result text inside the node
#
# Every node runs through ``kdx_execute``: it calls the node's own function
# (kept as ``KDX_IMPL``) and also returns {"ui": {"kdx_summary": [text]}}, which
# the editor shows in the node (web/kdx_resolution_summary.js).  The same text
# is produced on demand by ``preview_node`` for the live preview before a run.
# ----------------------------------------------------------------------------

def _summary_text(name, cls, kwargs, out):
    try:
        return summarize(name, cls, kwargs, out)
    except Exception as e:  # the summary must never break a run
        return f"(summary unavailable: {e})"


def _install_summary(name, cls):
    impl_name = cls.FUNCTION

    def kdx_execute(self, **kwargs):
        out = getattr(self, impl_name)(**kwargs)
        return {"ui": {"kdx_summary": [_summary_text(name, cls, kwargs, out)]}, "result": out}

    cls.KDX_IMPL = impl_name
    cls.kdx_execute = kdx_execute
    cls.FUNCTION = "kdx_execute"


for _name, _cls in NODE_CLASS_MAPPINGS.items():
    _install_summary(_name, _cls)


#: Longest string accepted by the preview route (custom tables, JSON text ...).
PREVIEW_MAX_CHARS = 20000


def preview_node(name, inputs):
    """Run node ``name`` with ``inputs`` (missing ones = defaults) for the live preview.

    Returns {"summary": text} or {"error": message}.  Only KDX-Resolution nodes,
    only their declared inputs; values are plain JSON scalars.
    """
    cls = NODE_CLASS_MAPPINGS.get(str(name))
    if cls is None:
        return {"error": f"unknown node {name!r}"}
    spec = cls.INPUT_TYPES()
    declared = {**spec.get("required", {}), **spec.get("optional", {})}
    kwargs = {}
    for inp, cfg in declared.items():
        opts = cfg[1] if len(cfg) > 1 else {}
        value = (inputs or {}).get(inp, opts.get("default", cfg[0][0] if isinstance(cfg[0], list) else None))
        if isinstance(value, str) and len(value) > PREVIEW_MAX_CHARS:
            return {"error": f"{inp} is too long for a preview"}
        if value is not None and not isinstance(value, (str, int, float, bool)):
            return {"error": f"{inp}: unsupported value"}
        kwargs[inp] = value
    validate = getattr(cls, "VALIDATE_INPUTS", None)
    if validate:
        args = {k: kwargs.get(k) for k in validate.__code__.co_varnames[1:validate.__code__.co_argcount]}
        ok = validate(**args)
        if ok is not True:
            return {"error": str(ok)}
    try:
        out = getattr(cls(), cls.KDX_IMPL)(**kwargs)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {"summary": _summary_text(name, cls, kwargs, out)}
