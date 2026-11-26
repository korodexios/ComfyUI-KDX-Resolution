"""KDX-Resolution — ComfyUI resolution toolkit (headless, stdlib only).

The code lives in the ``kdx_resolution`` package:
  * ``profiles.py`` — MODEL_PROFILES (native tables, grid, bounds)
  * ``solver.py``   — AR parsing, lattice solver, validation
  * ``presets.py``  — Preset Picker registry (+ custom JSON lists)
  * ``nodes.py``    — ComfyUI node classes and mappings
  * ``routes.py``   — read-only model list for the web UI settings
"""

if __package__:  # loaded by ComfyUI as a package
    from .kdx_resolution.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from .kdx_resolution.routes import register as _register_routes
else:  # imported as a plain module (e.g. by pytest from the repo root)
    from kdx_resolution.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from kdx_resolution.routes import register as _register_routes

_register_routes()

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
