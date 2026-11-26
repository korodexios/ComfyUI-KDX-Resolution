# 06 Development

```bash
python -m unittest discover -s tests -v      # or: python -m pytest
ruff check .
python tools_dev/build_example_workflows.py  # after changing node inputs
python tools_dev/build_model_table.py        # after changing MODEL_PROFILES
```

The tests need no ComfyUI and no third-party packages. CI runs ruff and the tests on Python 3.10–3.13.

## Code layout

| Path | Contents |
|---|---|
| `kdx_resolution/solver.py` | the math: ratio parsing, lattice solve, nearest native size |
| `kdx_resolution/profiles.py` | `MODEL_PROFILES`, the single source of truth for model data |
| `kdx_resolution/presets.py` | Preset Picker lists (profiles + custom JSON files) |
| `kdx_resolution/nodes.py` | the ComfyUI nodes (V1 API) |
| `kdx_resolution/summary.py` | text of the result box |
| `kdx_resolution/routes.py` | model list for the settings |
| `web/` | preset filter, node colours, model settings, result box |
| `tools_dev/` | generators for the example workflows and the model table in [03](03-model-profiles.md) |

## Rules for changes

- Saved workflows store widget values by position: never rename, reorder or remove node inputs; add
  new inputs at the end. Class names (`KDX_...`) never change.
- Profile names are stored in workflows too: when renaming one, add the old name to `PROFILE_ALIASES`.
- Any change in `web/` needs a version bump in `pyproject.toml` and in every `?v=` import
  (`tests/test_web_cache.py` checks it), otherwise browsers keep the old files.
- New model profile: add it to `MODEL_PROFILES` with a `source` link, then regenerate the model table.
