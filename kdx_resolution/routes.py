"""Small HTTP routes for the web UI. Registered only when running inside ComfyUI.

GET  /kdx_resolution/profiles  model list for Settings -> KDX Resolution
POST /kdx_resolution/preview   {"node": class name, "inputs": {...}} -> {"summary"} | {"error"}
                               live "what size will I get" text shown inside the node
Both are pure in-memory computations (no files, no network), so they run inline.

My profiles (editor: web/kdx_resolution_my_profiles.js):
GET  /kdx_resolution/my_profiles          {"profiles": [...], "bases": [...], "path"}
POST /kdx_resolution/my_profiles/check    {name, old_name?, based_on, text} -> rows/errors (dry run)
POST /kdx_resolution/my_profiles/save     same body -> writes the file, event kdx_resolution.profiles_changed
POST /kdx_resolution/my_profiles/delete   {name}
"""

import json
import logging

from . import my_profiles
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


def handle_my_profiles(action: str, body: bytes) -> dict:
    """Run one my-profiles editor action on a JSON body (testable without aiohttp)."""
    if len(body) > MAX_BODY:
        return {"ok": False, "errors": ["request too large"]}
    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        return {"ok": False, "errors": ["invalid JSON"]}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["expected a JSON object"]}
    try:
        if action == "check":
            return my_profiles.check(data)
        if action == "save":
            return my_profiles.save(data)
        if action == "delete":
            return my_profiles.delete(str(data.get("name") or ""))
    except (OSError, ValueError) as e:
        log.warning("[KDX-Resolution] my profiles %s failed: %s", action, e)
        return {"ok": False, "errors": [f"KDX Resolution: could not {action} the profile: {e}"]}
    return {"ok": False, "errors": [f"unknown action '{action}'"]}


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

        @routes.get("/kdx_resolution/my_profiles")
        async def kdx_resolution_my_profiles(request):
            return web.json_response(my_profiles.listing())

        @routes.post("/kdx_resolution/my_profiles/{action}")
        async def kdx_resolution_my_profiles_action(request):
            action = request.match_info["action"]
            body = await request.content.read(MAX_BODY + 1)
            result = handle_my_profiles(action, body)
            if action in ("save", "delete") and result.get("ok"):
                try:
                    PromptServer.instance.send_sync("kdx_resolution.profiles_changed", {})
                except Exception as e:  # the editor reloads on its own anyway
                    log.warning("[KDX-Resolution] profiles_changed event not sent: %s", e)
            return web.json_response(result)

        @routes.post("/kdx_resolution/preview")
        async def kdx_resolution_preview(request):
            body = await request.content.read(MAX_BODY + 1)
            return web.json_response(handle_preview(body))
    except Exception as e:  # never break node loading because of the UI helpers
        log.warning("[KDX-Resolution] web routes not registered: %s", e)
        return False
    return True
