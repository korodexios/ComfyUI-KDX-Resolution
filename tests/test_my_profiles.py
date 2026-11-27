"""My profiles: parsing the editor text, saving, renaming, and use in every node."""

import json
import os
import shutil
import tempfile
import unittest

from _helpers import ROOT, call  # noqa: F401  (sets sys.path)

from kdx_resolution import my_profiles, routes
from kdx_resolution.nodes import (
    KDX_AutoResolution_Core,
    KDX_Nearest_Native_Preset,
    KDX_Preset_Picker,
)
from kdx_resolution.presets import _load_registry
from kdx_resolution.profiles import profile_names, profile_summary, validate_profile_name

KREA = "Krea 2 (turbo/raw)"
TABLE = """# my Krea sizes
1:1 = 1024x1024
16:9 = 1376x768
2.35:1 = 1568x672
1184x896
"""


def core(ar, profile, mp=0):
    return call(KDX_AutoResolution_Core, ar_input=ar, model_profile=profile, target_megapixels=mp,
                custom_table="", mp_grid="", fallback_ar="1:1", alignment="default")


class MyProfilesCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        my_profiles.PATH_OVERRIDE = os.path.join(self.dir, "kdx_resolution", "my_profiles.json")
        my_profiles._CACHE["stamp"] = None

    def tearDown(self):
        my_profiles.PATH_OVERRIDE = None
        my_profiles._CACHE["stamp"] = None
        shutil.rmtree(self.dir, ignore_errors=True)

    def save(self, name="Krea mine", text=TABLE, based_on=KREA, old_name=""):
        return my_profiles.save({"name": name, "old_name": old_name, "based_on": based_on, "text": text})


class TestParse(MyProfilesCase):
    def test_lines(self):
        sizes, errors, warnings, rows = my_profiles.parse_sizes(TABLE, KREA)
        self.assertEqual(errors, [])
        self.assertEqual(sizes, [["1:1", 1024, 1024], ["16:9", 1376, 768], ["7:3", 1568, 672],
                                 ["4:3", 1184, 896]])
        self.assertEqual(rows[1]["mp"], 1.01)

    def test_errors_name_the_line_and_the_fix(self):
        _, errors, _, _ = my_profiles.parse_sizes("1250x830\nhello\n16:9 = 1376x768\n16:9 = 1344x768", KREA)
        self.assertIn("line 1: 1250x830 not a multiple of 16 (nearest 1248x832)", errors[0])
        self.assertIn("line 2: 'hello' not understood", errors[1])
        self.assertIn("line 4: 16:9 is listed twice", errors[2])

    def test_limits_and_ar_warning(self):
        _, errors, warnings, _ = my_profiles.parse_sizes("1:1 = 256x256\n16:9 = 1024x1024", KREA)
        self.assertIn("within 512-4096 px", errors[0])
        self.assertIn("off 16:9", warnings[0])

    def test_empty(self):
        self.assertEqual(my_profiles.parse_sizes("# nothing", KREA)[1], ["add at least one size"])


class TestStore(MyProfilesCase):
    def test_save_and_use_everywhere(self):
        self.assertTrue(self.save()["ok"])
        name = "★ Krea mine"
        self.assertIn(name, profile_names())
        self.assertIs(validate_profile_name(name), True)
        self.assertEqual(core("16:9", name)[:2], (1376, 768))
        self.assertEqual(core("21:9", name)[:2], (1568, 672))
        # an AR the table does not have -> nearest native size of MY table
        self.assertEqual(core("3:2", name)[:2], (1184, 896))
        # grid and ~MP come from the base profile
        self.assertEqual(core("16:9", name, 1.0)[0] % 16, 0)
        self.assertEqual(call(KDX_Nearest_Native_Preset, width=1920, height=1080, model_profile=name)[:3],
                         ("16:9", 1376, 768))
        reg, grids = _load_registry()
        self.assertEqual(reg[name][0], (1024, 1024))
        self.assertEqual(grids[name], 16)
        self.assertIn(f"{name} | ~16:9 | 1376x768", KDX_Preset_Picker.INPUT_TYPES()["required"]["preset"][0])
        from kdx_resolution.summary import profile_line
        self.assertIn("your sizes (based on Krea 2 (turbo/raw))", profile_line(name))
        summary = {p["name"]: p for p in profile_summary()}
        self.assertTrue(summary[name]["custom"])
        self.assertEqual(summary[name]["kind"], "image")

    def test_file_format(self):
        self.save()
        with open(my_profiles.PATH_OVERRIDE, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["profiles"][0]["based_on"], KREA)
        self.assertEqual(data["profiles"][0]["sizes"][0], ["1:1", 1024, 1024])

    def test_rename_keeps_old_workflows_working(self):
        self.save()
        self.assertTrue(self.save(name="Krea final", old_name="Krea mine")["ok"])
        self.assertNotIn("★ Krea mine", profile_names())
        self.assertIs(validate_profile_name("★ Krea mine"), True)
        self.assertEqual(core("16:9", "★ Krea mine")[:2], (1376, 768))
        # the old name is still taken
        self.assertFalse(self.save(name="Krea mine")["ok"])

    def test_bad_names(self):
        for name, part in (("", "give the profile a name"), (KREA, "built-in"), ("a | b", "'|'"),
                           ("★ x", "'|'")):
            with self.subTest(name=name):
                result = self.save(name=name)
                self.assertFalse(result["ok"])
                self.assertIn(part, result["errors"][0])
        self.save()
        self.assertIn("already exists", self.save()["errors"][0])

    def test_invalid_table_is_not_saved(self):
        result = self.save(text="1250x830")
        self.assertFalse(result["ok"])
        self.assertFalse(os.path.exists(my_profiles.PATH_OVERRIDE))

    def test_delete(self):
        self.save()
        self.assertTrue(my_profiles.delete("Krea mine")["ok"])
        self.assertNotIn("★ Krea mine", profile_names())
        msg = validate_profile_name("★ Krea mine")
        self.assertIn("does not exist on this machine", msg)
        self.assertFalse(my_profiles.delete("Krea mine")["ok"])

    def test_broken_file_is_ignored(self):
        os.makedirs(os.path.dirname(my_profiles.PATH_OVERRIDE))
        with open(my_profiles.PATH_OVERRIDE, "w", encoding="utf-8") as f:
            f.write("{broken")
        self.assertEqual(my_profiles.profiles(), {})
        self.assertNotIn("★", "".join(profile_names()))

    def test_listing(self):
        self.save()
        data = my_profiles.listing()
        self.assertEqual(data["profiles"][0]["display_name"], "★ Krea mine")
        self.assertIn("16:9 = 1376x768", data["profiles"][0]["text"])
        base = {b["name"]: b for b in data["bases"]}[KREA]
        self.assertEqual(base["multiple_of"], 16)
        self.assertTrue(base["text"].startswith("1:1 = 1024x1024"))

    def test_routes(self):
        body = json.dumps({"name": "R", "based_on": KREA, "text": "1:1 = 1024x1024"}).encode()
        self.assertTrue(routes.handle_my_profiles("check", body)["ok"])
        self.assertFalse(os.path.exists(my_profiles.PATH_OVERRIDE))
        self.assertEqual(routes.handle_my_profiles("save", body)["saved"], "★ R")
        self.assertFalse(routes.handle_my_profiles("nope", body)["ok"])
        self.assertFalse(routes.handle_my_profiles("save", b"{x")["ok"])
        self.assertTrue(routes.handle_my_profiles("delete", b'{"name": "R"}')["ok"])

    def test_outside_comfyui_nothing_is_saved(self):
        my_profiles.PATH_OVERRIDE = None
        self.assertIsNone(my_profiles.store_path())
        self.assertEqual(my_profiles.profiles(), {})
        self.assertIn("inside ComfyUI", routes.handle_my_profiles(
            "save", json.dumps({"name": "x", "based_on": KREA, "text": "1024x1024"}).encode())["errors"][0])


if __name__ == "__main__":
    unittest.main()
