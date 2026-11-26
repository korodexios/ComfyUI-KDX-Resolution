"""Unit tests for the pure resolution math in kdx_resolution.solver."""

import itertools
import unittest
from fractions import Fraction

from _helpers import ROOT  # noqa: F401  (sets sys.path)

from kdx_resolution.profiles import MODEL_PROFILES
from kdx_resolution.solver import (
    FALLBACK_AR_TOL,
    _norm_ar,
    _parse_ar_to_fraction,
    _reduce_ar,
    ar_drift,
    lattice_solve_exact,
    lattice_step,
    nearest_native_preset,
    parse_mp_grid,
    round3,
    snap_frames,
    validate_resolution,
)


class TestArParsing(unittest.TestCase):
    def test_norm_ar_separators(self):
        for raw in ("4/3", "4x3", "4X3", "4 : 3", "4: 3", "4::3"):
            self.assertEqual(_norm_ar(raw), "4:3", raw)

    def test_parse_ar_to_fraction(self):
        self.assertEqual(_parse_ar_to_fraction("16:9"), Fraction(16, 9))
        for bad in ("", "abc", "0:5", "5:0", "1:2:3", "-1:2"):
            self.assertIsNone(_parse_ar_to_fraction(bad), bad)


class TestLattice(unittest.TestCase):
    def test_lattice_step_is_on_grid_and_exact(self):
        for (w0, h0), align in itertools.product([(1, 1), (16, 9), (3, 2), (21, 9), (4, 3)], (8, 16, 32, 64)):
            dw, dh = lattice_step(w0, h0, align)
            self.assertEqual(dw % align, 0)
            self.assertEqual(dh % align, 0)
            self.assertEqual(Fraction(dw, dh), Fraction(w0, h0))

    def test_solve_is_exact_or_close_and_near_target(self):
        """Exact AR when the lattice is fine enough; otherwise <= 1.5 % drift and <= 25 % area error."""
        ars = [(1, 1), (16, 9), (9, 16), (3, 2), (4, 3), (21, 9), (683, 384), (7, 5), (1000, 999)]
        for (aw, ah), align, mp in itertools.product(ars, (8, 16, 32, 64), (0.25, 0.5, 1, 2, 4, 8)):
            side = int((mp * 1024 * 1024) ** 0.5)
            w, h = lattice_solve_exact(aw, ah, side, side, align, align, 8192)
            with self.subTest(ar=(aw, ah), align=align, mp=mp):
                self.assertEqual((w % align, h % align), (0, 0))
                self.assertTrue(align <= min(w, h) and max(w, h) <= 8192)
                drift = ar_drift(w, h, Fraction(aw, ah))
                if drift:
                    # never worse than one grid step can explain (small sizes on /64 grids)
                    self.assertLessEqual(drift, max(FALLBACK_AR_TOL, 1.5 * align / min(w, h)))
                    self.assertLessEqual(abs(w * h - side * side) / (side * side), 0.3)

    def test_known_values(self):
        # 16:9 on /16: exact lattice step 256x144, closest to 1 MP is j=5 -> 1280x720
        self.assertEqual(lattice_solve_exact(16, 9, 1024, 1024, 16, 256, 4096), (1280, 720))
        self.assertEqual(lattice_solve_exact(1, 1, 2048, 2048, 32, 512, 8192), (2048, 2048))
        # 9:16, min 512 on /32: the only exact option is 576x1024 even though it overshoots 0.25 MP
        self.assertEqual(lattice_solve_exact(9, 16, 512, 512, 32, 512, 8192), (576, 1024))

    def test_target_above_max_gives_largest_point(self):
        # regression: used to return the SMALLEST lattice point (256x256)
        self.assertEqual(lattice_solve_exact(1, 1, 7240, 7240, 16, 256, 4096), (4096, 4096))

    def test_coarse_ratio_falls_back_to_grid(self):
        # regression: 1366:768 (=683:384) used to return 8192x8192 for 1 MP
        w, h = lattice_solve_exact(683, 384, 1024, 1024, 32, 32, 8192)
        self.assertLess(abs(w * h - 1024 * 1024) / (1024 * 1024), 0.1)
        self.assertLessEqual(ar_drift(w, h, Fraction(683, 384)), FALLBACK_AR_TOL)

    def test_reduce_ar_and_mp_grid(self):
        self.assertEqual(_reduce_ar("32/18"), "16:9")
        self.assertEqual(_reduce_ar("1920x1080"), "16:9")
        self.assertEqual(_reduce_ar("abc"), "abc")
        self.assertEqual(parse_mp_grid("# c\n1 MP = 1024x1024\n4.0 mp: 2048 x 2048\n2 MP = 0x5\nbad"),
                         {1.0: (1024, 1024), 4.0: (2048, 2048)})

    def test_round3_on_grid(self):
        for ar in (Fraction(16, 9), Fraction(3, 2), Fraction(7, 5)):
            w, h = round3(ar, 1024 * 1024, 32)
            self.assertEqual((w % 32, h % 32), (0, 0))
            self.assertLess(abs(w / h - float(ar)) / float(ar), 0.05)


class TestNearestNative(unittest.TestCase):
    def test_exact_entry_wins(self):
        prof = MODEL_PROFILES["SDXL"]
        for ar, (w, h) in prof["native_resolutions"].items():
            self.assertEqual(nearest_native_preset(w, h, prof), (ar, w, h))

    def test_empty(self):
        self.assertEqual(nearest_native_preset(0, 10, MODEL_PROFILES["SDXL"]), ("", 0, 0))
        self.assertEqual(nearest_native_preset(10, 10, {}), ("", 0, 0))


class TestValidate(unittest.TestCase):
    def test_ok_and_problems(self):
        self.assertEqual(validate_resolution(1024, 1024, Fraction(1), 32, 512, 2048), (True, ""))
        ok, info = validate_resolution(1000, 4000, Fraction(1), 32, 512, 2048)
        self.assertFalse(ok)
        for part in ("off /32 grid", "above max 2048", "AR drift"):
            self.assertIn(part, info)


class TestSnapFrames(unittest.TestCase):
    def test_formulas(self):
        self.assertEqual(snap_frames(66, "4n+1"), 65)
        self.assertEqual(snap_frames(100, "8n+1"), 97)
        self.assertEqual(snap_frames(500, "4n+1", 121), 121)
        self.assertEqual(snap_frames(1, "4n"), 4)
        self.assertEqual(snap_frames(10, "fixed", 25), 25)
        self.assertEqual(snap_frames(10, "weird", 5), 5)


if __name__ == "__main__":
    unittest.main()
