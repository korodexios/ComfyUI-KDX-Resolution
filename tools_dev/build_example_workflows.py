"""Generate example_workflows/*.json from the current node definitions.

Run from the pack root:  python tools_dev/build_example_workflows.py

Widget values are written in the exact order of each node's INPUT_TYPES, so
the files stay loadable after inputs change — re-run this script then.
ComfyUI lists the files under Templates → custom nodes → ComfyUI-KDX-Resolution.
tests/test_example_workflows.py checks the files are up to date and runs them.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDGET_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN"}
#: Inputs for which the ComfyUI frontend adds a "control after generate" widget value.
CONTROL_AFTER_GENERATE = {"seed", "noise_seed"}


def load_classes():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from kdx_resolution.nodes import NODE_CLASS_MAPPINGS

    return NODE_CLASS_MAPPINGS


def is_widget(spec):
    typ = spec[0]
    return isinstance(typ, list) or typ in WIDGET_TYPES


def input_specs(cls):
    raw = cls.INPUT_TYPES()
    return list((raw.get("required") or {}).items()) + list((raw.get("optional") or {}).items())


def widget_default(spec):
    typ = spec[0]
    opts = spec[1] if len(spec) > 1 else {}
    if "default" in opts:
        return opts["default"]
    if isinstance(typ, list):
        return typ[0]
    return {"STRING": "", "INT": 0, "FLOAT": 0.0, "BOOLEAN": False}[typ]


# Core ComfyUI nodes used by the examples: (inputs, outputs, widget names)
CORE_NODES = {
    "EmptyLatentImage": ([("width", "INT"), ("height", "INT"), ("batch_size", "INT")], [("LATENT", "LATENT")],
                         ["width", "height", "batch_size"]),
    "PreviewAny": ([("source", "*")], [], []),
}


class Workflow:
    def __init__(self, classes):
        self.classes = classes
        self.nodes = []
        self.links = []

    def node(self, node_type, pos, size=(320, 200), values=None, title=None):
        node_id = len(self.nodes) + 1
        values = dict(values or {})
        if node_type in self.classes:
            cls = self.classes[node_type]
            specs = input_specs(cls)
            unknown = set(values) - {n for n, _ in specs} - {n + "_control" for n in CONTROL_AFTER_GENERATE}
            assert not unknown, (node_type, unknown)
            widgets_values = []
            for n, s in specs:
                if is_widget(s):
                    widgets_values.append(values.get(n, widget_default(s)))
                    if n in CONTROL_AFTER_GENERATE:
                        widgets_values.append(values.get(n + "_control", "fixed"))
            inputs = [{"name": n, "type": s[0], "link": None} for n, s in specs if not is_widget(s)]
            outputs = [{"name": name, "type": typ, "links": [], "slot_index": i}
                       for i, (name, typ) in enumerate(zip(cls.RETURN_NAMES, cls.RETURN_TYPES, strict=True))]
            widget_specs = {n: s for n, s in specs if is_widget(s)}
        else:
            core_inputs, core_outputs, core_widgets = CORE_NODES[node_type]
            widget_specs = {n: (t,) for n, t in core_inputs if n in core_widgets}
            widgets_values = [values.get(n, 1 if n == "batch_size" else 1024) for n in core_widgets]
            inputs = [{"name": n, "type": t, "link": None} for n, t in core_inputs if n not in core_widgets]
            outputs = [{"name": n, "type": t, "links": [], "slot_index": i} for i, (n, t) in enumerate(core_outputs)]
        node = {
            "id": node_id,
            "type": node_type,
            "pos": list(pos),
            "size": list(size),
            "flags": {},
            "order": node_id - 1,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "properties": {"Node name for S&R": node_type},
            "widgets_values": widgets_values,
            "_widget_specs": widget_specs,
        }
        if title:
            node["title"] = title
        self.nodes.append(node)
        return node_id

    def link(self, src_id, src_output, dst_id, dst_input):
        src, dst = self.nodes[src_id - 1], self.nodes[dst_id - 1]
        src_slot = next(i for i, o in enumerate(src["outputs"]) if o["name"] == src_output)
        typ = src["outputs"][src_slot]["type"]
        slot = next((i for i, inp in enumerate(dst["inputs"]) if inp["name"] == dst_input), None)
        if slot is None:  # widget converted to an input
            spec = dst["_widget_specs"][dst_input]
            dst["inputs"].append({"name": dst_input, "type": spec[0] if not isinstance(spec[0], list) else "COMBO",
                                  "widget": {"name": dst_input}, "link": None})
            slot = len(dst["inputs"]) - 1
        link_id = len(self.links) + 1
        dst["inputs"][slot]["link"] = link_id
        src["outputs"][src_slot]["links"].append(link_id)
        self.links.append([link_id, src_id, src_slot, dst_id, slot, typ])

    def to_json(self):
        nodes = []
        for node in self.nodes:
            node = {k: v for k, v in node.items() if k != "_widget_specs"}
            for out in node["outputs"]:
                if not out["links"]:
                    out["links"] = None
            nodes.append(node)
        return {
            "last_node_id": len(nodes),
            "last_link_id": len(self.links),
            "nodes": nodes,
            "links": self.links,
            "groups": [],
            "config": {},
            "extra": {"ds": {"scale": 0.9, "offset": [0, 0]}},
            "version": 0.4,
        }


def preset_to_latent(c):
    wf = Workflow(c)
    picker = wf.node("KDX_Preset_Picker", (40, 60), (380, 200), {
        "model": "SDXL", "preset": "SDXL | ~16:9 | 1344x768"})
    latent = wf.node("EmptyLatentImage", (470, 60), (300, 110))
    label = wf.node("PreviewAny", (470, 220), (300, 120), title="label")
    wf.link(picker, "width", latent, "width")
    wf.link(picker, "height", latent, "height")
    wf.link(picker, "label", label, "source")
    return wf


def llm_json_to_resolution(c):
    wf = Workflow(c)
    extractor = wf.node("KDX_AR_Extractor", (40, 60), (380, 260), {
        "mode": "json",
        "input_text": '{"prompt": "a lighthouse in a storm", "aspect_ratio": "21:9"}',
    }, title="AR from an LLM JSON answer")
    core = wf.node("KDX_AutoResolution_Core", (470, 60), (380, 470), {
        "model_profile": "Flux (dev/schnell)", "target_megapixels": 1.0})
    latent = wf.node("EmptyLatentImage", (900, 60), (300, 110))
    info = wf.node("PreviewAny", (900, 220), (360, 160), title="info (which rule was used)")
    wf.link(extractor, "extracted_ar", core, "ar_input")
    wf.link(core, "width", latent, "width")
    wf.link(core, "height", latent, "height")
    wf.link(core, "info", info, "source")
    return wf


def megapixels_and_steps(c):
    wf = Workflow(c)
    mp = wf.node("KDX_Megapixel_Selector", (40, 60), (360, 260), {
        "aspect_ratio": "16:9", "target_megapixels": 1.0, "alignment": "16"})
    step = wf.node("KDX_Resolution_Step", (440, 60), (320, 230), {
        "mode": "jump", "steps": 2, "direction": "up", "model_profile": "SDXL"}, title="2 sizes bigger, same AR")
    scaler = wf.node("KDX_Resolution_Scaler", (440, 330), (320, 160), {"scale_factor": 1.5, "alignment": "16"},
                     title="hires fix x1.5")
    s1 = wf.node("KDX_Resolution_To_String", (800, 60), (280, 100))
    s2 = wf.node("KDX_Resolution_To_String", (800, 330), (280, 100))
    p1 = wf.node("PreviewAny", (1120, 60), (260, 120), title="stepped size")
    p2 = wf.node("PreviewAny", (1120, 330), (260, 120), title="hires size")
    for src, dst in ((mp, step), (mp, scaler)):
        wf.link(src, "width", dst, "width")
        wf.link(src, "height", dst, "height")
    wf.link(step, "width", s1, "width")
    wf.link(step, "height", s1, "height")
    wf.link(scaler, "aligned_width", s2, "width")
    wf.link(scaler, "aligned_height", s2, "height")
    wf.link(s1, "resolution_string", p1, "source")
    wf.link(s2, "resolution_string", p2, "source")
    return wf


def batch_test_ratios(c):
    wf = Workflow(c)
    batch = wf.node("KDX_AR_Batch_Tester", (40, 60), (340, 170), {
        "ratios_list": "1:1, 3:2, 2:3, 16:9, 9:16", "mode": "Sequential", "seed_control": "increment"},
        title="next AR on every queue")
    core = wf.node("KDX_AutoResolution_Core", (420, 60), (380, 470), {"model_profile": "SDXL"})
    latent = wf.node("EmptyLatentImage", (850, 60), (300, 110))
    text = wf.node("KDX_Resolution_To_String", (850, 220), (280, 100))
    show = wf.node("PreviewAny", (1170, 220), (260, 120), title="size")
    wf.link(batch, "test_ar_string", core, "ar_input")
    wf.link(core, "width", latent, "width")
    wf.link(core, "height", latent, "height")
    wf.link(core, "width", text, "width")
    wf.link(core, "height", text, "height")
    wf.link(text, "resolution_string", show, "source")
    return wf


EXAMPLES = {
    "KDX Resolution - 1 preset picker to latent": preset_to_latent,
    "KDX Resolution - 2 LLM JSON aspect ratio to latent": llm_json_to_resolution,
    "KDX Resolution - 3 megapixels, size steps and hires scale": megapixels_and_steps,
    "KDX Resolution - 4 test several aspect ratios": batch_test_ratios,
}


def build_all(classes=None):
    classes = classes or load_classes()
    return {name: build(classes).to_json() for name, build in EXAMPLES.items()}


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main():
    out_dir = os.path.join(ROOT, "example_workflows")
    os.makedirs(out_dir, exist_ok=True)
    for name, data in build_all().items():
        path = os.path.join(out_dir, name + ".json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps(data))
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
