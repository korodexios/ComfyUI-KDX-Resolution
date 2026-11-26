import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Settings -> "KDX Resolution": choose which model profiles appear in the
// model dropdowns of the KDX-Resolution nodes (AutoRes Core, Nearest Native
// Preset, Resolution Step, Preset Picker).
//
// Only the dropdown lists are filtered in the browser.  The server still
// accepts every profile, so saved workflows keep working, and a node whose
// current value is a hidden model keeps showing that value.

const KINDS_ID = "KDX.Resolution.ModelKinds";
const KIND_OPTIONS = ["image + video", "image only", "video only"];
const MODEL_WIDGETS = { model_profile: true, model: true };
const ALWAYS_SHOWN = new Set(["auto"]);

let PROFILES = [];
try {
  const res = await api.fetchApi("/kdx_resolution/profiles");
  if (res.ok) PROFILES = (await res.json()).profiles || [];
} catch (e) {
  console.warn("[KDX-Resolution] model list unavailable, settings disabled", e);
}
const BY_NAME = new Map(PROFILES.map((p) => [p.name, p]));

const modelId = (name) => "KDX.Resolution.Model." + name.replace(/[^A-Za-z0-9]+/g, "_");

function getSetting(id, fallback) {
  try {
    const v = app.extensionManager?.setting?.get?.(id) ?? app.ui?.settings?.getSettingValue?.(id);
    return v === undefined || v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

// The node's own "model_list" input (all / image / video models).
const NODE_LIST_KIND = { "image models": "image", "video models": "video" };

function isVisible(name, nodeKind) {
  const p = BY_NAME.get(name);
  if (!p) return true; // "auto", custom preset lists, unknown values
  if (nodeKind && p.kind !== nodeKind) return false;
  const kinds = getSetting(KINDS_ID, KIND_OPTIONS[0]);
  if (kinds === "image only" && p.kind !== "image") return false;
  if (kinds === "video only" && p.kind !== "video") return false;
  return getSetting(modelId(name), true) !== false;
}

// pickFirst: the user just changed model_list -> if the current model is not
// in the new list, select the first one that is (and tell the node).
function filterNode(node, pickFirst = false) {
  if (!node?.comfyClass?.startsWith("KDX_")) return;
  const nodeKind = NODE_LIST_KIND[node.widgets?.find((w) => w.name === "model_list")?.value];
  for (const w of node.widgets || []) {
    if (!MODEL_WIDGETS[w.name] || !Array.isArray(w.options?.values)) continue;
    if (!w._kdxAllValues) w._kdxAllValues = [...w.options.values];
    const shown = w._kdxAllValues.filter((v) => ALWAYS_SHOWN.has(v) || isVisible(v, nodeKind));
    if (pickFirst && shown.length && !shown.includes(w.value)) {
      w.value = shown.find((v) => !ALWAYS_SHOWN.has(v)) ?? shown[0];
      w.callback?.(w.value);
    }
    // keep the node's current value selectable even if its model is hidden
    if (w.value !== undefined && !shown.includes(w.value) && w._kdxAllValues.includes(w.value)) {
      shown.unshift(w.value);
    }
    w.options.values = shown.length ? shown : [...w._kdxAllValues];
  }
  node.setDirtyCanvas?.(true, true);
}

function hookModelList(node) {
  const w = node.widgets?.find((x) => x.name === "model_list");
  if (!w || w._kdxListHooked) return;
  w._kdxListHooked = true;
  const orig = w.callback;
  w.callback = function () {
    const r = orig?.apply(this, arguments);
    filterNode(node, true);
    return r;
  };
}

function openSettings() {
  const cmd = app.extensionManager?.command;
  try {
    if (cmd?.execute) return cmd.execute("Comfy.ShowSettingsDialog");
  } catch (e) {
    console.warn("[KDX-Resolution] could not open settings", e);
  }
}

function refilterAll() {
  const nodes = app.graph?._nodes || app.graph?.nodes || [];
  nodes.forEach(filterNode);
}

const settings = [];
if (PROFILES.length) {
  settings.push({
    id: KINDS_ID,
    name: "Show model profiles of kind",
    category: ["KDX Resolution", "Model list", "Kinds"],
    type: "combo",
    options: KIND_OPTIONS,
    defaultValue: KIND_OPTIONS[0],
    tooltip: "Quick filter for all KDX-Resolution model dropdowns.",
    onChange: () => refilterAll(),
  });
  for (const p of PROFILES) {
    const flags = [p.kind, p.verified ? "official sizes" : "community sizes"];
    if (p.recommended_mp) flags.push(`~${p.recommended_mp} MP`);
    settings.push({
      id: modelId(p.name),
      name: `${p.name}  (${flags.join(", ")})`,
      category: ["KDX Resolution", p.kind === "video" ? "Video models" : "Image models", p.name],
      type: "boolean",
      defaultValue: true,
      tooltip: p.note || undefined,
      onChange: () => refilterAll(),
    });
  }
}

app.registerExtension({
  name: "KDX.ResolutionSettings",
  settings,
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.category !== "KDX/Resolution") return;
    const origMenu = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (_, options) {
      const r = origMenu?.apply(this, arguments);
      options?.push?.({
        content: "KDX: choose visible models… (Settings → KDX Resolution)",
        callback: openSettings,
      });
      return r;
    };
  },
  nodeCreated(node) {
    hookModelList(node);
    filterNode(node);
  },
  loadedGraphNode(node) {
    hookModelList(node);
    filterNode(node);
  },
});
