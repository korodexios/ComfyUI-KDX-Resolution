"""Load the node pack the way ComfyUI does (folder imported as a package)."""

import importlib.util
import os
import sys
import unittest

from _helpers import ROOT


class TestPackageLoad(unittest.TestCase):
    def test_comfyui_style_import(self):
        name = "ComfyUI-KDX-Resolution-loadtest"  # ComfyUI uses the folder name
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual(module.WEB_DIRECTORY, "./web")
        self.assertIn("KDX_AutoResolution_Core", module.NODE_CLASS_MAPPINGS)
        self.assertEqual(set(module.NODE_CLASS_MAPPINGS), set(module.NODE_DISPLAY_NAME_MAPPINGS))
        self.assertTrue(os.path.isdir(os.path.join(ROOT, "web")))


if __name__ == "__main__":
    unittest.main()
