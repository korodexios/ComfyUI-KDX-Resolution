"""ComfyUI sends no Cache-Control for .mjs: relative module imports carry ?v=<version>."""

import os
import re
import unittest

from _helpers import ROOT


def _version():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        return re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M).group(1)


class TestWebCache(unittest.TestCase):
    def test_mjs_imports_carry_version(self):
        version = _version()
        found = 0
        for base, _dirs, files in os.walk(os.path.join(ROOT, "web")):
            for name in files:
                if not name.endswith((".js", ".mjs")):
                    continue
                with open(os.path.join(base, name), encoding="utf-8") as f:
                    for spec in re.findall(r'from\s+"(\./[^"]+\.mjs[^"]*)"', f.read()):
                        found += 1
                        self.assertTrue(spec.endswith(f"?v={version}"), f"{name}: {spec}")
        self.assertGreater(found, 0)


if __name__ == "__main__":
    unittest.main()
