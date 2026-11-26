"""Pure resolution math: AR parsing, lattice solver, rounding, validation.

Stdlib only (fractions, math, re) so it can be unit-tested without ComfyUI.
"""

import math
import re
from fractions import Fraction

# ============================================================================
# SHARED HELPERS
# ============================================================================

def _norm_ar(ar: str) -> str:
    """Normalize an aspect-ratio string to 'W:H' (colon-separated).

    Accepts '4/3', '4x3', '4 : 3', '4: 3' and returns '4:3'.
    """
    ar = str(ar).strip().replace(" ", "")
    ar = ar.replace("/", ":").replace("x", ":").replace("X", ":")
    # Collapse duplicate colons: "4::3" -> "4:3"
    while "::" in ar:
        ar = ar.replace("::", ":")
    return ar


def _parse_ar_to_fraction(ar: str):
    """Return Fraction(w, h) for a normalized AR string, or None."""
    try:
        parts = ar.split(":")
        if len(parts) != 2:
            return None
        w, h = int(parts[0]), int(parts[1])
        if w <= 0 or h <= 0:
            return None
        return Fraction(w, h)
    except (ValueError, IndexError):
        return None


def _reduce_ar(ar: str) -> str:
    """Normalize and reduce an AR string: '32/18' -> '16:9', '1920x1080' -> '16:9'.

    Unparseable input is returned normalized but otherwise unchanged.
    """
    norm = _norm_ar(ar)
    frac = _parse_ar_to_fraction(norm)
    return f"{frac.numerator}:{frac.denominator}" if frac is not None else norm


def ar_drift(w: int, h: int, ar_frac) -> float:
    """Relative AR error of (w, h) against ``ar_frac`` (0.0 = exact)."""
    target = float(ar_frac)
    return abs(w / h - target) / target


_MP_LINE = re.compile(r"^(\d+(?:\.\d+)?)\s*MP\s*[:=]\s*(\d+)\s*[xX]\s*(\d+)$", re.IGNORECASE)


def parse_mp_grid(text: str) -> dict:
    """Parse a manual MP grid: '4.0 MP = 2048x2048' -> {4.0: (2048, 2048)}.

    Blank lines, '#' comments and entries with a zero side are ignored.
    """
    grid = {}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _MP_LINE.match(line)
        if m and int(m.group(2)) > 0 and int(m.group(3)) > 0:
            grid[float(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return grid


def _clamp_dim(value: int, align: int, min_dim: int, max_dim: int) -> int:
    """Clamp a dimension to [min_dim, max_dim] and round DOWN to the grid."""
    v = min(max(int(value), min_dim), max_dim)
    return max(align, (v // align) * align)


# ============================================================================
# LATTICE SOLVER (re-implemented from R1 principles; zero AR drift)
#
# A lattice is the set of grid-aligned (w, h) with w = k*w0, h = k*h0
# where (w0, h0) is the AR's reduced integer form.  Every point on the
# lattice has the EXACT AR — no drift, ever.
# ============================================================================

def lattice_step(w0: int, h0: int, align: int):
    """Smallest positive lattice step: the k such that (w0*k, h0*k) lands on
    the `align` grid.  Returns (dw, dh) — the exact-AR grid increment."""
    w0, h0 = max(1, int(w0)), max(1, int(h0))
    align = max(1, int(align))
    k = math.lcm(math.lcm(w0, align) // w0, math.lcm(h0, align) // h0)
    return (w0 * k, h0 * k)


def _parse_frame_formula(formula: str) -> tuple:
    """Parse '4n+1' -> (4, 1), '4n' -> (4, 0), '8n+1' -> (8, 1)."""
    f = str(formula or "").replace(" ", "").lower()
    m = re.fullmatch(r"(\d+)n\+(\d+)", f)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"(\d+)n", f)
    if m:
        return int(m.group(1)), 0
    return None


def snap_frames(frames: int, formula: str, max_frames: int = 0) -> int:
    """Snap a frame count to the model's frame formula.

    '4n+1': 65 -> 65, 66 -> 65, 67 -> 65 (nearest 4n+1)
    '8n+1': 100 -> 97  (nearest 8n+1)
    'fixed': returns max_frames if set, else frames
    """
    frames = int(frames)
    if formula == "fixed":
        return max_frames if max_frames else frames
    p = _parse_frame_formula(formula)
    if not p:
        return min(frames, max_frames) if max_frames else frames
    k, b = p
    n_min = 1 if b == 0 else 0
    n = math.floor((frames - b) / k + 0.5)
    n = max(n_min, n)
    if max_frames:
        n = min(n, max(n_min, (max_frames - b) // k))
    result = k * n + b
    return max(result, k * n_min + b)


#: Max AR drift accepted when the exact lattice is too coarse and a
#: grid-rounded fallback is used instead (1.5 %).
FALLBACK_AR_TOL = 0.015


def lattice_solve_exact(ar_w: int, ar_h: int, base_w: int, base_h: int,
                        align: int, min_dim: int, max_dim: int):
    """Solve for the exact-AR lattice point closest in area to base_w*base_h.

    The lattice is (w0*k, h0*k) with (w0, h0) the reduced AR — every point
    has the EXACT ratio (zero drift).  On-grid points are exactly the
    multiples of the lattice step: (j*dw, j*dh), j >= 1, where (dw, dh) is
    the smallest on-grid step for this ratio.

    If the exact lattice is too coarse for the request — the nearest exact
    point is outside [min_dim, max_dim] or more than 25 % off in area (e.g.
    1366:768 on a /32 grid has a 21856 px step) — a grid-rounded candidate
    (``round3``) is used instead, provided its AR drift is within
    ``FALLBACK_AR_TOL`` (if no exact point fits the bounds at all, the
    candidate with the smaller drift is used).  Otherwise the exact point wins: zero drift is worth
    more than area accuracy (9:16 with min_dim=512 on /32 can only be 576x1024).

    Returns (w, h) — both on the `align` grid and within [min_dim, max_dim].
    """
    g = math.gcd(ar_w, ar_h)
    w0, h0 = ar_w // g, ar_h // g
    dw, dh = lattice_step(w0, h0, align)
    target_area = max(1.0, float(base_w) * float(base_h))
    step_area = float(dw) * dh
    # Feasible j range: both dims within [min_dim, max_dim].
    j_lo = max(1, math.ceil(min_dim / dw), math.ceil(min_dim / dh))
    j_hi = min(int(max_dim // dw), int(max_dim // dh))
    if j_hi >= j_lo:
        # |step_area*j^2 - target| is minimal next to j* = sqrt(target/step);
        # clamp j* into the feasible range FIRST (a target above max_dim must
        # give the largest feasible point, not the smallest).
        j_star = min(max(int(round(math.sqrt(target_area / step_area))), j_lo), j_hi)
        best_j = min(range(max(j_lo, j_star - 2), min(j_hi, j_star + 2) + 1),
                     key=lambda j: abs(step_area * j * j - target_area))
        w, h = dw * best_j, dh * best_j
        exact_in_bounds = True
    else:  # no exact point fits the bounds at all
        w, h = _clamp_dim(dw, align, min_dim, max_dim), _clamp_dim(dh, align, min_dim, max_dim)
        exact_in_bounds = False

    area_err = abs(w * h - target_area) / target_area
    if exact_in_bounds and area_err <= 0.25:
        return (w, h)

    ar_frac = Fraction(w0, h0)
    cw, ch = round3(ar_frac, target_area, align)
    cw, ch = _clamp_dim(cw, align, min_dim, max_dim), _clamp_dim(ch, align, min_dim, max_dim)
    cand_drift = ar_drift(cw, ch, ar_frac)
    exact_drift = ar_drift(w, h, ar_frac)
    cand_area_err = abs(cw * ch - target_area) / target_area
    if not exact_in_bounds:
        # The clamped "exact" point is no longer exact: keep the closer AR.
        return (cw, ch) if cand_drift <= exact_drift else (w, h)
    if cand_drift <= FALLBACK_AR_TOL and cand_area_err < area_err:
        return (cw, ch)
    return (w, h)


def round3(ar_frac: Fraction, target_px: float, align: int):
    """3-pass rounding fallback (R2 principle): round-both / round-W-derive-H
    / round-H-derive-W, then keep the candidate with the best real AR error
    (tie: closest area).  Returns (w, h) on the align grid."""
    ratio = float(ar_frac)
    h_f = math.sqrt(target_px / ratio)
    w_f = h_f * ratio
    a = max(align, int(round(w_f / align)) * align)
    b = max(align, int(round(h_f / align)) * align)
    cands = []
    # pass 1: both rounded independently
    cands.append((a, b))
    # pass 2: W rounded, H derived from the exact ratio
    w2 = a
    h2 = max(align, int(round(w2 / ratio / align)) * align)
    cands.append((w2, h2))
    # pass 3: H rounded, W derived from the exact ratio
    h3 = b
    w3 = max(align, int(round(h3 * ratio / align)) * align)
    cands.append((w3, h3))
    # pass 4: both dims from the exact area anchor (h = sqrt(px/ratio)),
    # grid-rounded — a fourth candidate that sometimes lands exact where the
    # ratio-anchored passes fall between grid points
    h4 = max(align, int(round(math.sqrt(target_px / ratio) / align)) * align)
    w4 = max(align, int(round(h4 * ratio / align)) * align)
    cands.append((w4, h4))
    best = min(cands, key=lambda wh: (
        abs(wh[0] / wh[1] - ratio) / ratio, abs(wh[0] * wh[1] - target_px)
    ))
    return best


# ============================================================================
# NEAREST NATIVE PRESET (orientation tolerance + angle/area scoring)
# ============================================================================

def nearest_native_preset(w: int, h: int, profile: dict):
    """Find the native resolution in `profile` closest to (w, h).

    Scoring: 2 * angle_error + 0.1 * area_error (relative).  Angle dominates;
    the area term breaks ties so near-square inputs land on 1:1 and the
    area penalty keeps extreme ratios from hijacking.  Returns
    (ar_string, w, h) or ("", 0, 0) if the profile has no table.
    """
    table = profile.get("native_resolutions", {})
    if not table or w <= 0 or h <= 0:
        return ("", 0, 0)
    actual = w / h
    cands = []
    for ar, (pw, ph) in table.items():
        pf = float(_parse_ar_to_fraction(ar))
        angle_err = abs(math.atan(actual) - math.atan(pf))
        area_err = abs(w * h - pw * ph) / float(pw * ph)
        cands.append((2 * angle_err + 0.1 * area_err, ar, pw, ph))
    cands.sort(key=lambda c: c[0])
    _, ar, pw, ph = cands[0]
    return (ar, pw, ph)


# ============================================================================
# RE-VALIDATION (round, then re-validate guarantees — R7 principle)
# ============================================================================

def validate_resolution(w: int, h: int, ar_frac, align: int, min_dim: int,
                        max_dim: int, ar_tol: float = 0.015):
    """Re-check every guarantee after computation.

    Returns (ok: bool, info: str).  info is empty when ok, otherwise a
    short human-readable list of violated guarantees.
    """
    problems = []
    if w % align != 0 or h % align != 0:
        problems.append(f"off /{align} grid")
    if w < min_dim or h < min_dim:
        problems.append(f"below min {min_dim}")
    if w > max_dim or h > max_dim:
        problems.append(f"above max {max_dim}")
    if ar_frac is not None:
        drift = abs(w / h - float(ar_frac)) / float(ar_frac)
        if drift > ar_tol:
            problems.append(f"AR drift {drift:.4f} > {ar_tol}")
    if problems:
        return (False, "; ".join(problems))
    return (True, "")
