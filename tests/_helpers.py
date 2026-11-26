"""Shared test setup: make the ``kdx_resolution`` package importable."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def call(node_cls, **kwargs):
    """Run a V1 node the way ComfyUI does (``getattr(node(), FUNCTION)(**kwargs)``) and
    return its output tuple (the ``result`` part when the node also returns ``ui``)."""
    out = getattr(node_cls(), node_cls.FUNCTION)(**kwargs)
    if isinstance(out, dict):
        assert set(out) == {"ui", "result"}, out.keys()
        return out["result"]
    return out


def call_full(node_cls, **kwargs):
    """Like ``call`` but returns the raw value (dict with ``ui`` and ``result``)."""
    return getattr(node_cls(), node_cls.FUNCTION)(**kwargs)
