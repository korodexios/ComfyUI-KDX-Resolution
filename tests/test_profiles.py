"""Data checks for MODEL_PROFILES: every table entry must honour its own contract."""

import unittest

from _helpers import ROOT  # noqa: F401  (sets sys.path)

from kdx_resolution.profiles import MODEL_PROFILES

REQUIRED_KEYS = {"kind", "family", "base_resolution", "multiple_of", "min_dim", "max_dim", "native_resolutions"}


class TestProfiles(unittest.TestCase):
    def test_required_keys(self):
        for name, prof in MODEL_PROFILES.items():
            with self.subTest(profile=name):
                self.assertTrue(REQUIRED_KEYS <= set(prof), REQUIRED_KEYS - set(prof))
                self.assertIn(prof["kind"], ("image", "video"))
                self.assertLess(prof["min_dim"], prof["max_dim"])

    def test_native_entries_on_grid_in_bounds_and_close_to_label(self):
        for name, prof in MODEL_PROFILES.items():
            align = prof["multiple_of"]
            for ar, (w, h) in prof["native_resolutions"].items():
                with self.subTest(profile=name, ar=ar):
                    self.assertEqual(w % align, 0)
                    self.assertEqual(h % align, 0)
                    self.assertGreaterEqual(min(w, h), prof["min_dim"])
                    self.assertLessEqual(max(w, h), prof["max_dim"])
                    x, y = (int(v) for v in ar.split(":"))
                    # SDXL-style buckets label 1152x896 (9:7) as "4:3": allow 5 %.
                    self.assertLess(abs(w / h - x / y) / (x / y), 0.05)

    def test_concrete_buckets_on_grid_and_in_bounds(self):
        for name, prof in MODEL_PROFILES.items():
            align = prof["multiple_of"]
            for w, h in prof.get("concrete_buckets", []):
                with self.subTest(profile=name, bucket=(w, h)):
                    self.assertEqual(w % align, 0)
                    self.assertEqual(h % align, 0)
                    self.assertGreaterEqual(min(w, h), prof["min_dim"])
                    self.assertLessEqual(max(w, h), prof["max_dim"])

    def test_video_profiles_have_frame_rules(self):
        for name, prof in MODEL_PROFILES.items():
            if prof["kind"] == "video":
                with self.subTest(profile=name):
                    self.assertIn("frame_formula", prof)
                    self.assertGreater(prof["max_frames"], 0)


if __name__ == "__main__":
    unittest.main()
