"""Profile metadata (verified/source/recommended_mp) and the size warnings built on it."""

import unittest

from _helpers import ROOT, call  # noqa: F401  (sets sys.path)

from kdx_resolution.nodes import KDX_AutoResolution_Core, KDX_Preset_Picker
from kdx_resolution.profiles import MODEL_PROFILES, PROFILE_ALIASES
from kdx_resolution.solver import snap_frames


def core(ar, profile, mp):
    return call(KDX_AutoResolution_Core, ar_input=ar, model_profile=profile, target_megapixels=mp,
                custom_table="", mp_grid="", fallback_ar="1:1", alignment="default")


class TestProfileMetadata(unittest.TestCase):
    def test_fields(self):
        for name, prof in MODEL_PROFILES.items():
            with self.subTest(profile=name):
                self.assertIsInstance(prof["verified"], bool)
                if prof["verified"]:
                    self.assertTrue(prof.get("source", "").startswith("https://"))
                self.assertGreater(prof["recommended_mp"], 0)
                self.assertNotIn("hidden", prof)

    def test_aliases_point_to_existing_profiles(self):
        for old, new in PROFILE_ALIASES.items():
            self.assertNotIn(old, MODEL_PROFILES)
            self.assertIn(new, MODEL_PROFILES)

    def test_official_values(self):
        """Spot checks against the makers' published tables."""
        p = MODEL_PROFILES
        self.assertEqual(p["Wan 2.2"]["native_resolutions"]["16:9"], (1280, 720))
        self.assertIn([832, 480], p["Wan 2.2"]["concrete_buckets"])
        self.assertEqual(p["Wan 2.2 TI2V-5B"]["native_resolutions"]["16:9"], (1280, 704))
        self.assertEqual(p["Hunyuan Video"]["native_resolutions"]["4:3"], (1104, 832))
        self.assertEqual(p["CogVideoX 5B"]["native_resolutions"], {"3:2": (720, 480)})
        self.assertEqual(p["CogVideoX 1.5 5B"]["native_resolutions"]["16:9"], (1360, 768))
        self.assertEqual(p["Mochi 1"]["native_resolutions"]["16:9"], (848, 480))
        self.assertEqual(p["Z-Image (turbo/base)"]["native_resolutions"]["3:2"], (1248, 832))
        self.assertEqual(p["Qwen-Image-2.1"]["native_resolutions"]["16:9"], (2752, 1536))
        self.assertEqual(p["MiniMax H3 Image"]["native_resolutions"]["21:9"], (6272, 2688))

    def test_frame_formulas(self):
        self.assertEqual(snap_frames(160, "6n+1", 163), 163)   # Mochi
        self.assertEqual(snap_frames(80, "16n+1", 161), 81)    # CogVideoX 1.5
        self.assertEqual(snap_frames(300, "8n+1", 257), 257)   # LTX


class TestSizeWarnings(unittest.TestCase):
    def test_far_above_training_size_is_reported(self):
        w, h, _, _, _, info = core("1:1", "SDXL", 50.0)
        self.assertEqual((w, h), (4096, 4096))  # hard limit: max_dim
        self.assertIn("far above what SDXL was trained for", info)
        self.assertNotIn("NOTE", core("1:1", "SDXL", 1.5)[5])

    def test_max_mp_is_enforced(self):
        w, h, _, mp, _, info = core("1:1", "Flux-2 (dev/pro/flash/krea)", 8.0)
        self.assertLessEqual(mp, 4.0)
        self.assertGreater(mp, 3.5)
        self.assertIn("maximum of 4 MP", info)

    def test_video_profile_bounds(self):
        w, h, *_ = core("16:9", "Wan 2.2", 4.0)
        self.assertLessEqual(max(w, h), 1280)

    def test_picker_lists_new_profiles(self):
        presets = KDX_Preset_Picker.INPUT_TYPES()["required"]["preset"][0]
        for needle in ("Wan 2.2 TI2V-5B | ", "CogVideoX 1.5 5B | ", "Mochi 1 | "):
            self.assertTrue(any(p.startswith(needle) for p in presets), needle)


class TestWebSettingsSupport(unittest.TestCase):
    def test_profile_summary_is_json_and_complete(self):
        import json

        from kdx_resolution.profiles import profile_summary
        data = json.loads(json.dumps(profile_summary()))
        self.assertEqual([p["name"] for p in data], list(MODEL_PROFILES))
        self.assertTrue(all(p["kind"] in ("image", "video") for p in data))

    def test_route_registration_is_harmless_outside_comfyui(self):
        from kdx_resolution.routes import register
        self.assertFalse(register())

    def test_settings_js_uses_the_route(self):
        import os
        with open(os.path.join(ROOT, "web", "kdx_resolution_settings.js"), encoding="utf-8") as f:
            self.assertIn("/kdx_resolution/profiles", f.read())

    def test_docs_model_table_is_up_to_date(self):
        import os
        import sys
        sys.path.insert(0, os.path.join(ROOT, "tools_dev"))
        import build_model_table
        with open(os.path.join(ROOT, "docs", "03-model-profiles.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertEqual(readme, build_model_table.render(readme),
                         "run: python tools_dev/build_model_table.py")
        for name in MODEL_PROFILES:
            self.assertIn(f"| {name} |", readme)

class TestModelListInput(unittest.TestCase):
    NODES = ("KDX_AutoResolution_Core", "KDX_Preset_Picker", "KDX_Nearest_Native_Preset", "KDX_Resolution_Step")

    def test_sits_above_model_dropdown_and_does_not_change_results(self):
        from kdx_resolution.nodes import NODE_CLASS_MAPPINGS, preview_node
        for name in self.NODES:
            with self.subTest(node=name):
                spec = NODE_CLASS_MAPPINGS[name].INPUT_TYPES()
                order = list(spec["required"]) + list(spec.get("optional", {}))
                model = "model" if name == "KDX_Preset_Picker" else "model_profile"
                self.assertEqual(order.index("model_list") + 1, order.index(model))
                results = {preview_node(name, {"model_list": v})["summary"]
                           for v in ("all models", "image models", "video models")}
                self.assertEqual(len(results), 1)

    def test_new_profiles(self):
        for name, kind in (("Krea 2 (turbo/raw)", "image"), ("FLUX 3 Image Klein", "image"),
                           ("LTX 2.5", "video"), ("HunyuanVideo 1.5", "video"),
                           ("MOVA (OpenMOSS, video+audio)", "video")):
            self.assertEqual(MODEL_PROFILES[name]["kind"], kind)
        self.assertEqual(core("1:1", "Krea 2 (turbo/raw)", 0)[:2], (2048, 2048))
        self.assertEqual(core("16:9", "MOVA (OpenMOSS, video+audio)", 0)[:2], (1280, 720))
        self.assertEqual(core("16:9", "LTX 2.5", 0)[:2], (1920, 1088))


if __name__ == "__main__":
    unittest.main()
