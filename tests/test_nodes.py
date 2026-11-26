"""Node-level tests: ComfyUI contract (INPUT_TYPES / RETURN_TYPES) and behaviour."""

import unittest

from _helpers import ROOT, call  # noqa: F401  (sets sys.path)

from kdx_resolution import nodes
from kdx_resolution.nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    KDX_AR_Batch_Tester,
    KDX_AR_Extractor,
    KDX_AR_Validator,
    KDX_AutoResolution_Core,
    KDX_Megapixel_Selector,
    KDX_Nearest_Native_Preset,
    KDX_Preset_Picker,
    KDX_Resolution_Scaler,
    KDX_Resolution_Step,
    KDX_Resolution_To_String,
    KDX_Reverse_AR_Matcher,
)


def core(ar="1:1", profile="SDXL", mp=0.0, custom_table="", mp_grid="", fallback_ar="1:1",
         alignment="default", direct_override=""):
    return call(KDX_AutoResolution_Core, ar_input=ar, model_profile=profile, target_megapixels=mp,
                custom_table=custom_table, mp_grid=mp_grid, fallback_ar=fallback_ar, alignment=alignment,
                direct_override=direct_override)


class TestComfyContract(unittest.TestCase):
    def test_mappings_match(self):
        self.assertEqual(set(NODE_CLASS_MAPPINGS), set(NODE_DISPLAY_NAME_MAPPINGS))

    def test_every_node_is_well_formed(self):
        for name, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=name):
                spec = cls.INPUT_TYPES()
                self.assertIn("required", spec)
                self.assertTrue(callable(getattr(cls, cls.FUNCTION)))
                self.assertEqual(len(cls.RETURN_TYPES), len(cls.RETURN_NAMES))
                self.assertTrue(cls.CATEGORY.startswith("KDX"))
                for inp, cfg in {**spec["required"], **spec.get("optional", {})}.items():
                    kind = cfg[0]
                    if isinstance(kind, list):
                        self.assertTrue(kind, f"{inp}: empty combo")
                        default = cfg[1].get("default") if len(cfg) > 1 else None
                        if default is not None:
                            self.assertIn(default, kind, inp)

    def test_defaults_run(self):
        """Every node runs with nothing but its declared defaults (what a fresh node does)."""
        for name, cls in NODE_CLASS_MAPPINGS.items():
            spec = cls.INPUT_TYPES()
            kwargs = {}
            for inp, cfg in spec["required"].items():
                opts = cfg[1] if len(cfg) > 1 else {}
                kwargs[inp] = opts.get("default", cfg[0][0] if isinstance(cfg[0], list) else None)
            with self.subTest(node=name):
                out = call(cls, **kwargs)
                self.assertEqual(len(out), len(cls.RETURN_TYPES))


class TestPromptExtractor(unittest.TestCase):
    def run_(self, text, **kw):
        from kdx_resolution.nodes import KDX_Prompt_Extractor
        return call(KDX_Prompt_Extractor, input_text=text, **kw)

    def test_ar_and_resolution(self):
        out = self.run_("a cat, 16:9, photo")
        self.assertEqual((out[1], out[5], out[6]), ("16:9", True, False))
        out = self.run_("a cat 1920x1080")
        self.assertEqual((out[2], out[3], out[5], out[6]), (1920, 1080, False, True))
        self.assertEqual(self.run_("a cat 1280*720")[2:4], (1280, 720))
        self.assertEqual(self.run_("a cat 3x2")[1], "3:2")

    def test_marker_beats_plain_and_pick(self):
        text = "wide 16:9 scene, 1:1 crop --ar 4:3"
        self.assertEqual(self.run_(text)[1], "4:3")
        text = "16:9 first, 1:1 last"
        self.assertEqual(self.run_(text, pick="first")[1], "16:9")
        self.assertEqual(self.run_(text, pick="last")[1], "1:1")

    def test_remove_is_optional(self):
        text = "a cat, 16:9, 1920x1080, photo --ar 4:3"
        self.assertEqual(self.run_(text)[0], text)
        self.assertEqual(self.run_(text, remove_found=True)[0], "a cat, photo")
        out = self.run_(text, remove_found=True, extract_resolution=False)[0]
        self.assertIn("1920x1080", out)
        self.assertNotIn("16:9", out)

    def test_remove_cleans_separators(self):
        def rm(t):
            return self.run_(t, remove_found=True)[0]
        self.assertEqual(rm("from the waist up, 3:4, shot from arm's length."),
                         "from the waist up, shot from arm's length.")
        self.assertEqual(rm("from the waist up, 3:4. Shot low."), "from the waist up. Shot low.")
        self.assertEqual(rm("3:4, a woman in a room"), "a woman in a room")
        self.assertEqual(rm("a woman, 3:4"), "a woman")

    def test_custom_key_on_broken_json(self):
        broken = '{"aspect_ratio": "16:9", "style": "noir"'  # no closing brace
        out = self.run_(broken, custom_key="style", remove_found=True)
        self.assertEqual((out[1], out[4], out[7]), ("16:9", "noir", True))
        # plain text: the custom key and the ratio are removed from the prompt on request
        out = self.run_("a cat, style: noir, 16:9", custom_key="style", remove_found=True)
        self.assertEqual((out[0], out[4]), ("a cat", "noir"))
        self.assertEqual(self.run_("x --seed 42", custom_key="seed")[4], "42")

    def test_fallbacks(self):
        out = self.run_("nothing here", fallback_ar="3:2", fallback_width=512, fallback_height=768)
        self.assertEqual(out, ("nothing here", "3:2", 512, 768, "", False, False, False, False))
        self.assertEqual(self.run_("")[5:], (False, False, False, False))

    def test_keys_for_ar_resolution_and_prompt(self):
        # LLM answer: escaped quotes inside the prompt, a 16:9 in the prompt text, no closing brace
        text = ('{"aspect_ratio": "4:5", "size": "1280x720", "rewritten_prompt": "A sign says '
                '\\"open 16:9\\", warm light.\\nSecond line."')
        out = self.run_(text, ar_key="aspect_ratio", resolution_key="size", prompt_key="rewritten_prompt")
        self.assertEqual(out[0], 'A sign says "open 16:9", warm light.\nSecond line.')
        self.assertEqual(out[1:4], ("4:5", 1280, 720))
        self.assertEqual((out[5], out[6], out[8]), (True, True, True))
        # cut off in the middle of the prompt
        out = self.run_('{"aspect_ratio": "1:1", "rewritten_prompt": "A cat on a mat', ar_key="aspect_ratio",
                        prompt_key="rewritten_prompt")
        self.assertEqual((out[0], out[1]), ("A cat on a mat", "1:1"))
        # key given but missing in plain text: the ratio is still found by pattern, prompt = whole text
        out = self.run_("just text 16:9", ar_key="aspect_ratio", prompt_key="p")
        self.assertEqual((out[0], out[1], out[5], out[8]), ("just text 16:9", "16:9", True, False))
        # nothing at all: fallback ratio
        self.assertEqual(self.run_("just text", ar_key="aspect_ratio")[1:6:4], ("1:1", False))

    def test_auto_prompt_from_json_with_other_key_names(self):
        text = '{"ratio": "3:2", "image_description": "A wide 16:9 room, soft light.", "seed": "7"'
        out = self.run_(text)
        self.assertEqual(out[0], "A wide 16:9 room, soft light.")
        self.assertEqual((out[1], out[5], out[8]), ("3:2", True, True))  # ratio outside the prompt wins
        # no ratio outside the prompt: the one inside it is used (and removed on request)
        out = self.run_('{"p": "A wide 16:9 room, soft light."}', remove_found=True)
        self.assertEqual((out[0], out[1]), ("A wide room, soft light.", "16:9"))


class TestExtractor(unittest.TestCase):
    def run_(self, mode, text, key="aspect_ratio"):
        return call(KDX_AR_Extractor, mode=mode, input_text=text, key=key, fallback_value="1:1")

    def test_modes(self):
        self.assertEqual(self.run_("json", '{"aspect_ratio": "16:9"}'), ("16:9", False))
        self.assertEqual(self.run_("json", '```json\n{"a": {"b": "3x2"}}\n```', key="a.b"), ("3:2", False))
        self.assertEqual(self.run_("marker", "a cat --ar 3:2 --seed 4"), ("3:2", False))
        self.assertEqual(self.run_("text", "model 2 16:9 shot"), ("16:9", False))

    def test_fallbacks(self):
        self.assertEqual(self.run_("json", ""), ("1:1", True))
        self.assertEqual(self.run_("json", "not json"), ("1:1", True))
        self.assertEqual(self.run_("marker", "no marker"), ("1:1", True))


class TestCore(unittest.TestCase):
    def test_native_table(self):
        w, h, ar, mp, fb, info = core("16:9", "SDXL")
        self.assertEqual((w, h, ar, fb), (1344, 768, "16:9", False))
        self.assertIn("native table", info)

    def test_target_mp_lattice(self):
        w, h, ar, _, _, info = core("16:9", "Flux (dev/schnell)", mp=1.0)
        self.assertEqual((w, h), (1280, 720))
        self.assertIn("lattice", info)

    def test_direct_override(self):
        self.assertEqual(core(direct_override="1920x1080")[:3], (1920, 1080, "override"))

    def test_custom_table(self):
        w, h, _, _, _, info = core("21:9", "SDXL", custom_table="21:9 = 1600, 688")
        self.assertEqual((w, h), (1600, 688))
        self.assertIn("custom table", info)

    def test_unknown_ar_uses_fallback(self):
        w, h, ar, _, fb, _ = core("garbage", "SDXL", fallback_ar="16:9")
        self.assertEqual((w, h, ar, fb), (1344, 768, "16:9", True))


class TestSmallNodes(unittest.TestCase):
    def test_validator(self):
        self.assertEqual(call(KDX_AR_Validator, text_to_check="use 16/9", known_ratios="1:1, 16:9"), (True, "16:9"))
        self.assertEqual(call(KDX_AR_Validator, text_to_check="5:4", known_ratios="1:1"), (False, ""))

    def test_reverse_matcher(self):
        self.assertEqual(call(KDX_Reverse_AR_Matcher, width=1920, height=1080), ("16:9", 1.7778))
        self.assertEqual(call(KDX_Reverse_AR_Matcher, width=0, height=0), ("1:1", 1.0))

    def test_scaler(self):
        self.assertEqual(call(KDX_Resolution_Scaler, width=1024, height=768, scale_factor=1.5, alignment="32"),
                         (1536, 1152))

    def test_batch_tester(self):
        out = [call(KDX_AR_Batch_Tester, ratios_list="1:1, 3/2", mode="Sequential", seed=s)[0] for s in range(3)]
        self.assertEqual(out, ["1:1", "3:2", "1:1"])
        a = call(KDX_AR_Batch_Tester, ratios_list="1:1, 3:2, 16:9", mode="Random", seed=7)
        self.assertEqual(a, call(KDX_AR_Batch_Tester, ratios_list="1:1, 3:2, 16:9", mode="Random", seed=7))

    def test_megapixel_selector(self):
        self.assertEqual(call(KDX_Megapixel_Selector, aspect_ratio="1:1", target_megapixels=4.0, alignment="32",
                              mp_grid=""), (2048, 2048, 4.0))

    def test_nearest_native(self):
        self.assertEqual(call(KDX_Nearest_Native_Preset, width=1920, height=1080, model_profile="SDXL"),
                         ("16:9", 1344, 768))

    def test_to_string(self):
        self.assertEqual(call(KDX_Resolution_To_String, width=1920, height=1080), ("1920x1080",))

    def test_step_jump_and_snap(self):
        w, h, ar, j = call(KDX_Resolution_Step, width=1280, height=720, mode="jump", steps=1, direction="up",
                           model_profile="Flux (dev/schnell)")
        self.assertEqual((w, h, ar), (1536, 864, "16:9"))
        w, h, ar, _ = call(KDX_Resolution_Step, width=1300, height=700, mode="snap", steps=1, direction="up",
                           model_profile="Wan 2.2")
        self.assertEqual((w, h, ar), (1280, 720, "16:9"))


class TestPresetPicker(unittest.TestCase):
    def test_every_listed_preset_resolves(self):
        presets = KDX_Preset_Picker.INPUT_TYPES()["required"]["preset"][0]
        self.assertTrue(presets)
        for p in presets:
            w, h, _, _, label = call(KDX_Preset_Picker, model="", preset=p, orientation="as listed", scale=1.0)
            self.assertIn(f"{w}x{h}", p)
            self.assertTrue(label.startswith(p.split(" | ")[0]))

    def test_orientation_and_scale(self):
        p = "SDXL | 16:9 | 1344x768"
        self.assertEqual(call(KDX_Preset_Picker, model="SDXL", preset=p, orientation="portrait", scale=1.0)[:2],
                         (768, 1344))
        self.assertEqual(call(KDX_Preset_Picker, model="SDXL", preset=p, orientation="as listed", scale=2.0)[:2],
                         (2688, 1536))

    def test_ar_label(self):
        self.assertEqual(nodes._ar_label(1344, 768), "~16:9")  # 7:4 is within 3 % of 16:9
        self.assertEqual(nodes._ar_label(1920, 1080), "16:9")
        self.assertEqual(nodes._ar_label(1366, 768), "~16:9")


if __name__ == "__main__":
    unittest.main()


class TestNodeDocs(unittest.TestCase):
    def test_descriptions_and_tooltips(self):
        for name, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=name):
                self.assertTrue(cls.DESCRIPTION.strip())
                self.assertEqual(len(cls.OUTPUT_TOOLTIPS), len(cls.RETURN_TYPES))
                self.assertEqual(cls.CATEGORY, "KDX/Resolution")
                icon, sep, _ = NODE_DISPLAY_NAME_MAPPINGS[name].partition(" KDX • ")
                self.assertTrue(sep and icon and not icon.isascii(), "display name: '<emoji> KDX • <Name>'")
                spec = cls.INPUT_TYPES()
                for inp, cfg in {**spec["required"], **spec.get("optional", {})}.items():
                    self.assertGreater(len(cfg), 1, f"{name}.{inp} has no options")
                    self.assertTrue(cfg[1].get("tooltip"), f"{name}.{inp} has no tooltip")

    def test_icons_are_unique(self):
        icons = [n.partition(" KDX • ")[0] for n in NODE_DISPLAY_NAME_MAPPINGS.values()]
        self.assertEqual(len(icons), len(set(icons)), "every KDX node has its own icon (CONVENTIONS.md)")

    def test_web_files_reference_every_node(self):
        import os
        with open(os.path.join(ROOT, "web", "kdx_resolution_look.js"), encoding="utf-8") as f:
            js = f.read()
        for name in NODE_CLASS_MAPPINGS:
            self.assertIn(name + ":", js)
