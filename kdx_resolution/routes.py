"""Small HTTP routes for the web UI. Registered only when running inside ComfyUI.

GET  /kdx_resolution/profiles  model list for Settings -> KDX Resolution
POST /kdx_resolution/preview   {"node": class name, "inputs": {...}} -> {"summary"} | {"error"}
                               live "what size will I get" text shown inside the node
Both are pure in-memory computations (no files, no network), so they run inline.
"""

import json
import logging

from .nodes import preview_node
from .profiles import profile_summary

log = logging.getLogger(__name__)

#: Largest accepted preview request body (bytes).
MAX_BODY = 64 * 1024


def handle_preview(body: bytes) -> dict:
    """Validate a preview request body and run the preview (testable without aiohttp)."""
    if len(body) > MAX_BODY:
        return {"error": "request too large"}
    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        return {"error": "invalid JSON"}
    if not isinstance(data, dict) or not isinstance(data.get("inputs", {}), dict):
        return {"error": "expected {'node': name, 'inputs': {...}}"}
    return preview_node(data.get("node"), data.get("inputs", {}))


def register():
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:  # not running inside ComfyUI (tests, tools)
        return False
    try:
        routes = PromptServer.instance.routes

        @routes.get("/kdx_resolution/profiles")
        async def kdx_resolution_profiles(request):
            return web.json_response({"profiles": profile_summary()})

        @routes.post("/kdx_resolution/preview")
        async def kdx_resolution_preview(request):
            body = await request.content.read(MAX_BODY + 1)
            return web.json_response(handle_preview(body))
    except Exception as e:  # never break node loading because of the UI helpers
        log.warning("[KDX-Resolution] web routes not registered: %s", e)
        return False
    return True
