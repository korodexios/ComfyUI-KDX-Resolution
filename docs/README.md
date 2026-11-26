# KDX Resolution — user guide

| Page | What it covers |
|---|---|
| [01 Quick start](01-quick-start.md) | install, your first size, which node to use, the result box |
| [02 Nodes](02-nodes.md) | every node: inputs, outputs, examples |
| [03 Model profiles and presets](03-model-profiles.md) | the 28 model profiles, native tables, your own preset lists, hiding models |
| [04 With KDX Wildcard Studio and KDX LLM](04-kdx-packs.md) | aspect ratio from a template or an LLM JSON answer, Prompt Extractor |
| [05 Example workflows](05-example-workflows.md) | the workflows in `example_workflows/`, step by step |
| [06 Development](06-development.md) | tests, lint, code layout, rules for changing nodes |

Two rules that hold everywhere:

- **1 MP = 1024 × 1024 = 1 048 576 px** (ComfyUI convention, not 1 000 000).
- Every computed size is a multiple of the model's grid (`multiple_of`) and within its size limits.
