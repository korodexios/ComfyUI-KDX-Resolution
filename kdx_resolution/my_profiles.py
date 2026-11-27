"""My profiles: user-made model profiles with their own size table.

A "my profile" copies a built-in profile (grid, size limits, ~MP, kind) and replaces its size
table with the user's own sizes. It shows up in every model dropdown as ``★ <name>``.

Stored in ``<ComfyUI user dir>/kdx_resolution/my_profiles.json``, written atomically under a
lock, so ``git pull`` of the node pack never touches it::

    {"version": 1, "profiles": [
        {"name": "Krea 2 mine", "based_on": "Krea 2 (turbo/raw)",
         "sizes": [["16:9", 1376, 768], ["4:3", 1184, 896]],
         "aliases": ["Krea old name"]}
    ]}

A rename keeps the old name in ``aliases``, so saved workflows keep working.
"""

import copy
import json
import math
import os
import re
import tempfile
import threading
from fractions import Fraction

from .profiles import MODEL_PROFILES, PROFILE_ALIASES

#: Prefix of every my-profile name in the dropdowns.
STAR = "★ "
MAX_NAME = 60
MAX_SIZES = 64
#: A size whose AR differs more than this from the AR written next to it gets a warning.
AR_WARN_TOL = 0.05

_LOCK = threading.Lock()
_CACHE = {"stamp": None, "data": None}
#: Tests set this to a temporary file; None = the ComfyUI user directory.
PATH_OVERRIDE = None

_KNOWN = [(1, 1), (5, 4), (4, 3), (3, 2), (16, 10), (16, 9), (2, 1), (7, 3), (21, 9), (12, 5), (32, 9)]
_KNOWN = sorted(set(_KNOWN + [(b, a) for a, b in _KNOWN]))
_LINE_RE = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)\s*(?:=|->|→|\s)\s*)?"
    r"(\d+)\s*[xX×*,]\s*(\d+)\s*(?:px)?$"
)


def store_path():
    """Path of my_profiles.json, or None when not running inside ComfyUI (and no override)."""
    if PATH_OVERRIDE:
        return PATH_OVERRIDE
    try:
        import folder_paths  # ComfyUI
        base = folder_paths.get_user_directory()
    except Exception:
        return None
    return os.path.join(base, "kdx_resolution", "my_profiles.json")


# ----------------------------------------------------------------------------
# reading / writing
# ----------------------------------------------------------------------------
def _read_file(path):
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    items = data.get("profiles", []) if isinstance(data, dict) else []
    return [p for p in items if isinstance(p, dict) and p.get("name")]


def _stamp(path):
    try:
        return (path, os.path.getmtime(path), os.path.getsize(path))
    except (OSError, TypeError):
        return (path, None, None)


def load():
    """The stored my-profile entries (list of dicts), cached until the file changes."""
    path = store_path()
    stamp = _stamp(path)
    if _CACHE["stamp"] != stamp:
        _CACHE["data"], _CACHE["stamp"] = _read_file(path), stamp
    return _CACHE["data"]


def _write(items):
    path = store_path()
    if not path:
        raise ValueError("KDX Resolution: my profiles can only be saved inside ComfyUI")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".my_profiles.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "profiles": items}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    _CACHE["stamp"] = None


# ----------------------------------------------------------------------------
# profiles for the nodes
# ----------------------------------------------------------------------------
def display_name(name):
    return STAR + str(name)


def _build_profile(entry):
    base = MODEL_PROFILES.get(PROFILE_ALIASES.get(entry.get("based_on"), entry.get("based_on")))
    if not base:
        return None
    native = {}
    for item in entry.get("sizes", []):
        try:
            ar, w, h = str(item[0]), int(item[1]), int(item[2])
        except (TypeError, ValueError, IndexError):
            continue
        if w > 0 and h > 0:
            native[ar or _auto_ar(w, h, native)] = (w, h)
    if not native:
        return None
    prof = copy.deepcopy({k: v for k, v in base.items() if k not in ("native_resolutions", "concrete_buckets")})
    prof.update({
        "native_resolutions": native,
        "concrete_buckets": [],
        "verified": False,
        "custom": True,
        "based_on": entry.get("based_on"),
        "source": "",
        "note": f"my profile, based on {entry.get('based_on')}",
    })
    return prof


def profiles():
    """{dropdown name: profile dict} for every usable my profile, in file order."""
    out = {}
    for entry in load():
        prof = _build_profile(entry)
        if prof:
            out[display_name(entry["name"])] = prof
    return out


def aliases():
    """{old dropdown name: current dropdown name} from renames."""
    out = {}
    for entry in load():
        for old in entry.get("aliases", []) or []:
            out[display_name(old)] = display_name(entry["name"])
    return out


# ----------------------------------------------------------------------------
# parsing the editor text
# ----------------------------------------------------------------------------
def _auto_ar(w, h, taken=()):
    """AR key for a size written without one: '16:9', or a known AR within 3 %, else exact."""
    g = math.gcd(w, h)
    exact = f"{w // g}:{h // g}"
    r = w / h
    a, b = min(_KNOWN, key=lambda k: abs(math.log(r / (k[0] / k[1]))))
    near = f"{a}:{b}"
    if abs(r / (a / b) - 1) < 0.03 and near not in taken:
        return near
    return exact


def _norm_ar(a, b):
    """'16', '9' -> '16:9'; '2.35', '1' -> None (decimal: the key comes from the size)."""
    try:
        fa, fb = Fraction(a), Fraction(b)
    except (ValueError, ZeroDivisionError):
        return None
    if fa <= 0 or fb <= 0 or fa.denominator != 1 or fb.denominator != 1:
        return None
    g = math.gcd(fa.numerator, fb.numerator)
    return f"{fa.numerator // g}:{fb.numerator // g}"


def parse_sizes(text, based_on):
    """Parse editor lines ('16:9 = 1376x768', '1184x896', '# comment').

    Returns (sizes, errors, warnings, rows): sizes = [[ar, w, h], ...] in the given order,
    rows = one dict per size for the editor's preview table.
    """
    base = MODEL_PROFILES.get(PROFILE_ALIASES.get(based_on, based_on))
    grid = base.get("multiple_of", 16) if base else 16
    lo = base.get("min_dim", 1) if base else 1
    hi = base.get("max_dim", 8192) if base else 8192
    sizes, errors, warnings, rows, taken = [], [], [], [], set()
    for n, raw in enumerate(str(text or "").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            errors.append(f"line {n}: '{line}' not understood (write e.g. '16:9 = 1376x768' or '1376x768')")
            continue
        w, h = int(m.group(3)), int(m.group(4))
        if w <= 0 or h <= 0:
            errors.append(f"line {n}: {w}x{h} has a zero side")
            continue
        bad = []
        if w % grid or h % grid:
            fix = f"{max(grid, round(w / grid) * grid)}x{max(grid, round(h / grid) * grid)}"
            bad.append(f"not a multiple of {grid} (nearest {fix})")
        if min(w, h) < lo or max(w, h) > hi:
            bad.append(f"sides must stay within {lo}-{hi} px")
        if bad:
            errors.append(f"line {n}: {w}x{h} " + "; ".join(bad))
            continue
        written = _norm_ar(m.group(1), m.group(2)) if m.group(1) else None
        ar = written or _auto_ar(w, h, taken)
        if ar in taken:
            errors.append(f"line {n}: {ar} is listed twice (one size per aspect ratio)")
            continue
        if written:
            a, b = (int(x) for x in written.split(":"))
            drift = abs((w / h) / (a / b) - 1)
            if drift > AR_WARN_TOL:
                warnings.append(f"line {n}: {w}x{h} is {drift:.0%} off {written}")
        taken.add(ar)
        sizes.append([ar, w, h])
        rows.append({"ar": ar, "w": w, "h": h, "mp": round(w * h / (1024 * 1024), 2)})
    if not sizes and not errors:
        errors.append("add at least one size")
    if len(sizes) > MAX_SIZES:
        errors.append(f"at most {MAX_SIZES} sizes")
    return sizes, errors, warnings, rows


def sizes_text(entry):
    """Editor text for a stored entry."""
    return "\n".join(f"{ar} = {w}x{h}" for ar, w, h in entry.get("sizes", []))


def base_text(based_on):
    """Editor text with the built-in table of ``based_on`` (a starting point)."""
    base = MODEL_PROFILES.get(PROFILE_ALIASES.get(based_on, based_on)) or {}
    return "\n".join(f"{ar} = {w}x{h}" for ar, (w, h) in base.get("native_resolutions", {}).items())


# ----------------------------------------------------------------------------
# editor actions (called by routes.py; pure enough to test)
# ----------------------------------------------------------------------------
def _check_name(name, old_name, items):
    name = str(name or "").strip()
    if not name:
        return name, "give the profile a name"
    if len(name) > MAX_NAME:
        return name, f"name is longer than {MAX_NAME} characters"
    if "|" in name or name.startswith("★"):
        return name, "the name must not contain '|' or start with ★"
    if name in MODEL_PROFILES or name in PROFILE_ALIASES:
        return name, f"'{name}' is a built-in profile; pick another name"
    for e in items:
        if e["name"] == old_name:
            continue
        if e["name"] == name or name in (e.get("aliases") or []):
            return name, f"a profile named '{name}' already exists"
    return name, ""


def check(data):
    """Dry run of save(): parsed rows, errors and warnings, nothing written."""
    based_on = str(data.get("based_on") or "")
    sizes, errors, warnings, rows = parse_sizes(data.get("text", ""), based_on)
    if based_on not in MODEL_PROFILES:
        errors.insert(0, "pick the model it is based on")
    name, err = _check_name(data.get("name"), data.get("old_name"), load())
    if err:
        errors.insert(0, err)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "rows": rows,
            "display_name": display_name(name) if name else ""}


def save(data):
    """Create or update a profile ({name, old_name?, based_on, text}). Returns check() + saved."""
    with _LOCK:
        _CACHE["stamp"] = None
        result = check(data)
        if not result["ok"]:
            return result
        items = [dict(e) for e in load()]
        name = str(data.get("name")).strip()
        old = str(data.get("old_name") or "").strip()
        sizes = parse_sizes(data.get("text", ""), data.get("based_on"))[0]
        entry = {"name": name, "based_on": data.get("based_on"), "sizes": sizes, "aliases": []}
        for i, e in enumerate(items):
            if old and e["name"] == old:
                al = [a for a in (e.get("aliases") or []) if a != name]
                if old != name:
                    al.append(old)
                entry["aliases"] = al
                items[i] = entry
                break
        else:
            items.append(entry)
        _write(items)
        result["saved"] = display_name(name)
        return result


def delete(name):
    with _LOCK:
        _CACHE["stamp"] = None
        items = [e for e in load() if e["name"] != name]
        if len(items) == len(load()):
            return {"ok": False, "errors": [f"no profile named '{name}'"]}
        _write(items)
        return {"ok": True, "deleted": display_name(name)}


def listing():
    """Everything the editor needs: my profiles (with editor text) and the built-in bases."""
    bases = [{"name": k, "kind": v.get("kind", "image"), "multiple_of": v.get("multiple_of"),
              "min_dim": v.get("min_dim"), "max_dim": v.get("max_dim"),
              "recommended_mp": v.get("recommended_mp"), "text": base_text(k)}
             for k, v in MODEL_PROFILES.items() if not v.get("hidden")]
    mine = [{"name": e["name"], "display_name": display_name(e["name"]), "based_on": e.get("based_on"),
             "text": sizes_text(e), "usable": _build_profile(e) is not None}
            for e in load()]
    return {"profiles": mine, "bases": bases, "path": store_path() or ""}
