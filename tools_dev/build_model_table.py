"""Regenerate the model table in docs/03-model-profiles.md from MODEL_PROFILES.

Run from the pack root:  python tools_dev/build_model_table.py
The table sits between the <!-- models:start --> and <!-- models:end --> markers;
tests/test_profile_sources.py fails when it is out of date.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- models:start -->", "<!-- models:end -->"


def table():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from kdx_resolution.profiles import MODEL_PROFILES

    rows = ["| Profile | Kind | Grid | ~MP | Native sizes | Frames | Sizes |", "|---|---|---|---|---|---|---|"]
    for kind in ("image", "video"):
        for name, p in MODEL_PROFILES.items():
            if p["kind"] != kind:
                continue
            sizes = ", ".join(f"{w}×{h}" for w, h in p["native_resolutions"].values())
            frames = (f"{p['frame_formula']} ≤{p['max_frames']} @{p['default_fps']} fps"
                      if kind == "video" else "")
            if p["verified"]:
                src = f"[official]({p['source']})"
            else:
                src = "community" + (f" ([info]({p['source']}))" if p.get("source") else "")
            grid, mp = f"/{p['multiple_of']}", f"{p['recommended_mp']:g}"
            rows.append(f"| {name} | {kind} | {grid} | {mp} | {sizes} | {frames} | {src} |")
    return "\n".join(rows) + "\n"


def render(readme: str) -> str:
    a, b = readme.index(START) + len(START), readme.index(END)
    return readme[:a] + "\n" + table() + readme[b:]


def main():
    path = os.path.join(ROOT, "docs", "03-model-profiles.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(text))
    print("updated the model table in docs/03-model-profiles.md")


if __name__ == "__main__":
    main()
