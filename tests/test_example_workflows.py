"""example_workflows/*.json: up to date with the builder, structurally valid, and runnable."""

import json
import os
import sys
import unittest

from _helpers import ROOT, call

sys.path.insert(0, os.path.join(ROOT, "tools_dev"))
import build_example_workflows as builder  # noqa: E402

from kdx_resolution.nodes import NODE_CLASS_MAPPINGS  # noqa: E402

FOLDER = os.path.join(ROOT, "example_workflows")


def to_api_prompt(wf):
    """Minimal UI-workflow -> API-prompt conversion (what the frontend does on queue)."""
    links = {link[0]: link for link in wf["links"]}
    prompt = {}
    for node in wf["nodes"]:
        inputs = {}
        if node["type"] in NODE_CLASS_MAPPINGS:
            values = iter(node["widgets_values"])
            for name, spec in builder.input_specs(NODE_CLASS_MAPPINGS[node["type"]]):
                if builder.is_widget(spec):
                    inputs[name] = next(values)
                    if name in builder.CONTROL_AFTER_GENERATE:
                        next(values)
        else:
            names = builder.CORE_NODES[node["type"]][2]
            inputs.update(zip(names, node["widgets_values"], strict=True))
        for inp in node["inputs"]:
            if inp["link"] is not None:
                _, src, slot, _, _, _ = links[inp["link"]]
                inputs[inp["name"]] = [str(src), slot]
        prompt[str(node["id"])] = {"class_type": node["type"], "inputs": inputs}
    return prompt


def execute(prompt):
    """Run every KDX node (resolving links); core nodes are only checked for their inputs."""
    results = {}

    def value(v):
        if isinstance(v, list):
            return run(v[0])[v[1]]
        return v

    def run(nid):
        if nid not in results:
            node = prompt[nid]
            kwargs = {k: value(v) for k, v in node["inputs"].items()}
            if node["class_type"] in NODE_CLASS_MAPPINGS:
                results[nid] = call(NODE_CLASS_MAPPINGS[node["class_type"]], **kwargs)
            else:
                results[nid] = (kwargs,)
        return results[nid]

    for nid in prompt:
        run(nid)
    return results


class TestExampleWorkflows(unittest.TestCase):
    def test_files_match_builder(self):
        built = builder.build_all()
        on_disk = sorted(f[:-5] for f in os.listdir(FOLDER) if f.endswith(".json"))
        self.assertEqual(on_disk, sorted(built), "run: python tools_dev/build_example_workflows.py")
        for name, data in built.items():
            with open(os.path.join(FOLDER, name + ".json"), encoding="utf-8") as f:
                self.assertEqual(f.read(), builder.dumps(data), f"{name} is stale: re-run the builder")

    def test_workflows_run_and_have_an_output_node(self):
        for fname in sorted(os.listdir(FOLDER)):
            with open(os.path.join(FOLDER, fname), encoding="utf-8") as f:
                wf = json.load(f)
            with self.subTest(workflow=fname):
                self.assertTrue(any(n["type"] == "PreviewAny" for n in wf["nodes"]), "no output node")
                prompt = to_api_prompt(wf)
                results = execute(prompt)
                for nid, node in prompt.items():
                    if node["class_type"] == "EmptyLatentImage":
                        kwargs = results[nid][0]
                        self.assertGreater(kwargs["width"], 0)
                        self.assertEqual(kwargs["width"] % 8, 0)
                        self.assertEqual(kwargs["height"] % 8, 0)
                    if node["class_type"] in NODE_CLASS_MAPPINGS:
                        cls = NODE_CLASS_MAPPINGS[node["class_type"]]
                        if hasattr(cls, "VALIDATE_INPUTS"):
                            args = {k: v for k, v in node["inputs"].items()
                                    if k in cls.VALIDATE_INPUTS.__code__.co_varnames and not isinstance(v, list)}
                            self.assertIs(cls.VALIDATE_INPUTS(**args), True)


if __name__ == "__main__":
    unittest.main()
