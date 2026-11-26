"""Regression tests for bugs found in the 0.2.0 audit (one test per bug)."""

import json
import os
import tempfile
import unittest
from fractions import Fraction
from unittest import mock

from _helpers import ROOT, call  # noqa: F401  (sets sys.path)

from kdx_resolution import presets
from kdx_resolution.nodes import (
    KDX_AR_Batch_Tester,
    KDX_AR_Extractor,
    KDX_AR_Validator,
    KDX_AutoResolution_Core,
    KDX_Megapixel_Selector,
    KDX_Nearest_Native_Preset,
    KDX_Preset_Picker,
    KDX_Resolution_Step,
    KDX_Reverse_AR_Matcher,
)
from kdx_resolution.profiles import MODEL_PROFILES, _profile
from kdx_resolution.solver import ar_drift


def core(ar="1:1", profile="SDXL", mp=0.0, custom_table="", mp_grid="", fallback_ar="1:1",
         alignment="default", direct_override=""):
    return call(KDX_AutoResolution_Core, ar_input=ar, model_profile=profile, target_megapixels=mp,
                custom_table=custom_table, mp_grid=mp_grid, fallback_ar=fallback_ar, alignment=alignment,
                direct_override=direct_override)


def step(w, h, mode="jump", steps=1, direction="up", profile="SDXL"):
    return call(KDX_Resolution_Step, width=w, height=h, mode=mode, steps=steps, direction=direction,
                model_profile=profile)


class TestCoreRegressions(unittest.TestCase):
    def test_messy_ratio_with_target_mp(self):
        # was 4096x4096 "UNRESOLVED: AR drift 0.4378"
        w, h, _, mp, _, info = core("1366x768", "SDXL", mp=1.0)
        self.assertNotIn("UNRESOLVED", info)
        self.assertLess(abs(mp - 1.0), 0.1)
        self.assertLessEqual(ar_drift(w, h, Fraction(16, 9)), 0.015)

    def test_huge_target_mp_gives_largest_size_not_smallest(self):
        w, h, *_ = core("1:1", "SDXL", mp=50.0)  # SDXL max_dim 4096
        self.assertEqual((w, h), (4096, 4096))

    def test_unreduced_ar_matches_native_table(self):
        for ar in ("32:18", "1920x1080", "16/9"):
            w, h, matched, _, fb, info = core(ar, "SDXL")
            self.assertEqual((w, h, matched, fb), (1344, 768, "16:9", False), ar)
            self.assertNotIn("NOTE", info)

    def test_native_table_values_have_no_drift_note(self):
        for name, prof in MODEL_PROFILES.items():
            for ar in prof["native_resolutions"]:
                with self.subTest(profile=name, ar=ar):
                    self.assertNotIn("NOTE", core(ar, name)[5])

    def test_nearest_native_uses_ar_not_size(self):
        # Wan 2.2 base 720 vs 1280x720 table entry: 2:1 used to land on 4:3
        self.assertEqual(core("2:1", "Wan 2.2")[2], "16:9")
        self.assertEqual(core("1:2", "Wan 2.2")[2], "9:16")
        self.assertEqual(core("5:4", "Qwen-Image-2.1")[2], "4:3")
        self.assertEqual(core("4:5", "Qwen-Image-2.1")[2], "3:4")

    def test_default_custom_table_is_inert(self):
        # The default custom table used to inject 21:9 = 3072x1312 into every model (SD 1.5 too)
        default = KDX_AutoResolution_Core.INPUT_TYPES()["required"]["custom_table"][1]["default"]
        w, h, ar, _, _, info = core("21:9", "SD 1.5", custom_table=default)
        self.assertLessEqual(max(w, h), MODEL_PROFILES["SD 1.5"]["max_dim"])
        self.assertNotIn("custom table", info)

    def test_zero_direct_override_is_ignored(self):
        w, h, ar, _, _, info = core("16:9", "SDXL", direct_override="0x0")
        self.assertEqual((w, h, ar), (1344, 768, "16:9"))
        self.assertIn("ignored invalid direct_override", info)

    def test_invalid_ar_uses_fallback_through_whole_chain(self):
        # fallback_ar not in the table used to give a base-size SQUARE labelled "21:9"
        w, h, ar, _, fb, info = core("", "Flux (dev/schnell)", fallback_ar="21:9")
        self.assertTrue(fb)
        self.assertGreater(w / h, 1.5)
        self.assertIn("fallback_ar", info)
        # and a fallback honours target_megapixels
        w, h, *_ = core("nonsense", "SDXL", mp=2.0, fallback_ar="1:1")
        self.assertEqual(w, h)
        self.assertGreater(w * h, 1.8 * 1024 * 1024)

    def test_mp_grid_entry_is_snapped_to_requested_ar(self):
        w, h, *_ = core("16:9", "SDXL", mp=4.0, mp_grid="4 MP = 2048x2048")
        self.assertLessEqual(ar_drift(w, h, Fraction(16, 9)), 0.015)
        self.assertLess(abs(w * h - 2048 * 2048) / (2048 * 2048), 0.1)
        # an entry that already has the AR is used verbatim
        self.assertEqual(core("1:1", "SDXL", mp=4.0, mp_grid="4 MP = 2048x2048")[:2], (2048, 2048))

    def test_old_profile_name_still_works(self):
        self.assertIs(_profile("Z-Image (turbop/base)"), MODEL_PROFILES["Z-Image (turbo/base)"])
        self.assertIs(KDX_AutoResolution_Core.VALIDATE_INPUTS(model_profile="Z-Image (turbop/base)"), True)
        self.assertIsInstance(KDX_AutoResolution_Core.VALIDATE_INPUTS(model_profile="Nope"), str)
        self.assertEqual(core("16:9", "Z-Image (turbop/base)")[:2], (1280, 720))
        self.assertEqual(core("16:9", "Qwen-Image (2.0/edit)")[:2], (1664, 928))


class TestMegapixelRegressions(unittest.TestCase):
    def mps(self, ar, mp, align="32", grid=""):
        return call(KDX_Megapixel_Selector, aspect_ratio=ar, target_megapixels=mp, alignment=align, mp_grid=grid)

    def test_messy_ratio(self):
        w, h, mp = self.mps("1366:768", 1.0)  # was 8192x8192 = 64 MP
        self.assertLess(abs(mp - 1.0), 0.1)

    def test_grid_snapped(self):
        w, h, _ = self.mps("16:9", 4.0, grid="4 MP = 2048x2048")  # was 2048x2048 regardless of AR
        self.assertLessEqual(ar_drift(w, h, Fraction(16, 9)), 0.015)


class TestStepRegressions(unittest.TestCase):
    def test_messy_input_ratio(self):
        w, h, ar, _ = step(1366, 768)  # was 4096x4096 with ar "683:384"
        self.assertEqual(ar, "16:9")
        self.assertEqual(Fraction(w, h), Fraction(16, 9))
        self.assertGreater(w, 1366)
        self.assertLess(w, 2000)

    def test_jump_keeps_ar_at_max_bound(self):
        w, h, ar, _ = step(3840, 2160, steps=3)  # was 4096x2592 (AR broken by clamping)
        self.assertEqual((w, h), (4096, 2304))

    def test_jump_down_stops_at_min_bound(self):
        w, h, _, _ = step(512, 512, steps=50, direction="down")
        self.assertEqual((w, h), (256, 256))

    def test_auto_alignment_divides_input(self):
        w, h, _, _ = step(1200, 720, profile="auto")  # gcd 240 -> /16, not /128
        self.assertEqual((w % 16, h % 16), (0, 0))
        self.assertEqual(Fraction(w, h), Fraction(5, 3))


class TestSmallNodeRegressions(unittest.TestCase):
    def test_batch_tester_is_cacheable(self):
        # IS_CHANGED -> NaN re-ran every downstream node on every queue
        self.assertFalse(hasattr(KDX_AR_Batch_Tester, "IS_CHANGED"))

    def test_extractor_json_variants(self):
        def ex(text, key="aspect_ratio", mode="json"):
            return call(KDX_AR_Extractor, mode=mode, input_text=text, key=key, fallback_value="1:1")
        self.assertEqual(ex('Sure! Here it is: {"aspect_ratio": "16:9"} Enjoy.'), ("16:9", False))
        self.assertEqual(ex('{"shots": [{"ar": "9:16"}]}', key="shots.0.ar"), ("9:16", False))
        self.assertEqual(ex('{"aspect_ratio": "16:9 (widescreen)"}'), ("16:9", False))
        self.assertEqual(ex('[1, 2]'), ("1:1", True))
        self.assertEqual(ex('{"aspect_ratio": {"w": 1}}'), ("1:1", True))
        self.assertEqual(ex("0:0 then 3:2", mode="text"), ("3:2", False))
        self.assertEqual(ex("--ar 0:5", mode="marker"), ("1:1", True))

    def test_validator_compares_reduced_ratios(self):
        self.assertEqual(call(KDX_AR_Validator, text_to_check="32:18", known_ratios="1:1, 16:9"), (True, "16:9"))

    def test_reverse_matcher_symmetric(self):
        a = call(KDX_Reverse_AR_Matcher, width=2000, height=1000)[0]
        b = call(KDX_Reverse_AR_Matcher, width=1000, height=2000)[0]
        self.assertEqual(a.split(":")[::-1], b.split(":"))

    def test_nearest_native_rejects_unknown_profile_at_validation(self):
        self.assertIsInstance(KDX_Nearest_Native_Preset.VALIDATE_INPUTS(model_profile="Nope"), str)
        self.assertIs(KDX_Resolution_Step.VALIDATE_INPUTS(model_profile="auto"), True)


class TestPresetRegressions(unittest.TestCase):
    def test_saved_preset_not_in_list_still_validates_and_runs(self):
        p = "My Old List | 16:9 | 1920x1080"
        self.assertIs(KDX_Preset_Picker.VALIDATE_INPUTS(model="My Old List", preset=p), True)
        self.assertIsInstance(KDX_Preset_Picker.VALIDATE_INPUTS(preset="garbage"), str)
        self.assertEqual(call(KDX_Preset_Picker, model="x", preset=p, orientation="as listed", scale=1.0)[:2],
                         (1920, 1080))

    def _registry_with(self, content):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kdx_custom_presets.local.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            with mock.patch.object(presets, "CUSTOM_PRESET_PATHS", [path]):
                presets._KDX_CACHE.update(data=None, mtime=None)
                try:
                    return presets._load_registry()[0]
                finally:
                    presets._KDX_CACHE.update(data=None, mtime=None)

    def test_broken_custom_files_do_not_crash(self):
        for content in ("[1, 2]", "{not json", json.dumps({"A": {"presets": [["x", 1], "0x5", None, "640x480"]}}),
                        json.dumps({"B": {"presets": "1280x720"}}), json.dumps({"C": "nope"})):
            with self.subTest(content=content):
                reg = self._registry_with(content)
                self.assertIn("SDXL", reg)
        reg = self._registry_with(json.dumps({"A": {"presets": [["x", 1], "0x5", "640x480"]}}))
        self.assertEqual(reg["A"], [(640, 480)])

    def test_local_list_based_on_model(self):
        reg = self._registry_with(json.dumps({"Mine | v2": {"based_on": "SDXL", "include_base": True,
                                                             "presets": ["1920x1080"]}}))
        self.assertIn("Mine / v2", reg)  # " | " would break the dropdown label
        self.assertEqual(reg["Mine / v2"][-1], (1920, 1080))
        self.assertGreater(len(reg["Mine / v2"]), 5)


if __name__ == "__main__":
    unittest.main()
