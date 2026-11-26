"""Result text inside the node: run-time ui output, live preview and the preview route."""

import json
import unittest

from _helpers import ROOT, call_full  # noqa: F401  (sets sys.path)

from kdx_resolution.nodes import NODE_CLASS_MAPPINGS, KDX_AutoResolution_Core, preview_node
from kdx_resolution.routes import MAX_BODY, handle_preview


class TestRunSummary(unittest.TestCase):
    def test_every_node_returns_ui_summary_with_defaults(self):
        for name, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=name):
                res = preview_node(name, {})
                self.assertIn("summary", res, res)
                self.assertNotIn("summary unavailable", res["summary"])
                self.assertEqual(cls.FUNCTION, "kdx_execute")
                self.assertTrue(callable(getattr(cls, cls.KDX_IMPL)))

    def test_ui_and_result(self):
        out = call_full(KDX_AutoResolution_Core, ar_input="16:9", model_profile="SDXL", target_megapixels=0.0,
                        custom_table="", mp_grid="", fallback_ar="1:1", alignment="default")
        self.assertEqual(out["result"][:2], (1344, 768))
        text = out["ui"]["kdx_summary"][0]
        self.assertIn("1344 × 768 px", text)
        self.assertIn("native table 16:9", text)


class TestCustomTableFeedback(unittest.TestCase):
    def run_core(self, **kw):
        base = dict(ar_input="21:9", model_profile="Flux (dev/schnell)", target_megapixels=0.0,
                    custom_table="", mp_grid="", fallback_ar="1:1", alignment="default")
        base.update(kw)
        return call_full(KDX_AutoResolution_Core, **base)

    def test_custom_entry_keeps_users_spelling(self):
        out = self.run_core(custom_table="21:9 = 1600, 688")
        self.assertEqual(out["result"][2], "21:9")  # not the reduced "7:3"
        self.assertIn("▶ 21:9 = 1600×688", out["ui"]["kdx_summary"][0])

    def test_bad_lines_are_reported(self):
        out = self.run_core(custom_table="21:9 = 1600, 688\n16:9 1920\n0:1 = 5, 5")
        info = out["result"][5]
        self.assertIn("not understood", info)
        self.assertIn("'16:9 1920'", info)
        self.assertIn("'0:1 = 5, 5'", info)

    def test_native_label_kept(self):
        self.assertEqual(self.run_core(model_profile="SDXL")["result"][2], "21:9")

    def test_label_keeps_simple_input_spelling_off_table(self):
        out = self.run_core(target_megapixels=1.0)  # Flux has no 21:9 entry
        self.assertEqual(out["result"][2], "21:9")
        self.assertIn("exact 21:9", out["result"][5])
        self.assertEqual(self.run_core(ar_input="1366x768", target_megapixels=1.0)["result"][2], "683:384")


class TestPreviewRoute(unittest.TestCase):
    def body(self, data):
        return json.dumps(data).encode()

    def test_ok(self):
        res = handle_preview(self.body({"node": "KDX_Megapixel_Selector",
                                        "inputs": {"aspect_ratio": "1:1", "target_megapixels": 4.0}}))
        self.assertIn("2048 × 2048 px", res["summary"])

    def test_rejects_bad_requests(self):
        self.assertIn("error", handle_preview(b"not json"))
        self.assertIn("error", handle_preview(self.body([1, 2])))
        self.assertIn("error", handle_preview(self.body({"node": "os.system", "inputs": {}})))
        self.assertIn("error", handle_preview(self.body({"node": "KDX_AutoResolution_Core",
                                                         "inputs": {"ar_input": {"x": 1}}})))
        self.assertIn("error", handle_preview(b"x" * (MAX_BODY + 1)))
        big = {"node": "KDX_AR_Extractor", "inputs": {"input_text": "x" * 30000}}
        self.assertIn("error", handle_preview(self.body(big)))

    def test_validation_errors_are_shown(self):
        res = preview_node("KDX_AutoResolution_Core", {"model_profile": "Nope"})
        self.assertIn("Unknown model_profile", res["error"])


if __name__ == "__main__":
    unittest.main()
