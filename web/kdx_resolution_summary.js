import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { ensureTheme } from "./kdx_resolution/theme.mjs?v=0.6.7";

// A read-only text box at the bottom of every KDX-Resolution node that says
// which size the node gives and why (native table, custom table, lattice,
// fallback, warnings).
//
// * Live preview: when you change a value, the server computes the result
//   (POST /kdx_resolution/preview) and the box updates - no need to run.
// * After a run: the node's own result text (ui.kdx_summary) is shown.
// * Inputs that come from other nodes are only known during a run; the box
//   then says so and keeps the last run's result.
//
// The box is not saved in the workflow and not sent to the backend, so it
// does not shift saved widget values.

const CATEGORY = "KDX/Resolution";
const WIDGET = "kdx_summary";
const MIN_HEIGHT = 84;
const DEBOUNCE_MS = 300;
const TAG_PREVIEW = "— preview (updates as you edit)";
const TAG_RUN = "— result of the last run";

function getWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

// Box state -> left accent: ok (green), warn (⚠ note or ↪ fallback), err, wait (input from another node).
function stateOf(text) {
  if (text.startsWith("⚠")) return "err";
  if (text.startsWith("⏳")) return "wait";
  if (/^(⚠|↪)|^is_fallback: True$/m.test(text)) return "warn";
  return "ok";
}

function show(node, text) {
  const w = getWidget(node, WIDGET);
  if (!w) return;
  w.value = text || "";
  if (w.inputEl) {
    w.inputEl.value = w.value;
    const st = w.value ? stateOf(w.value) : "ok";
    for (const c of ["warn", "err", "wait"]) w.inputEl.classList.toggle(c, st === c);
  }
  node.setDirtyCanvas?.(true, false);
}

function addSummaryWidget(node) {
  if (getWidget(node, WIDGET)) return;
  let w;
  try {
    w = ComfyWidgets.STRING(node, WIDGET, ["STRING", { multiline: true }], app).widget;
  } catch (e) {
    console.warn("[KDX-Resolution] result box unavailable:", e);
    return;
  }
  w.serialize = false; // not saved in the workflow
  w.options = { ...(w.options || {}), serialize: false, getMinHeight: () => MIN_HEIGHT };
  w.value = "";
  if (w.inputEl) {
    ensureTheme();
    w.inputEl.readOnly = true;
    w.inputEl.placeholder = "The resulting size appears here.";
    w.inputEl.classList.add("kdxr-root", "kdxr-summary");
  }
  const size = node.computeSize?.();
  if (size && node.size && node.size[1] < size[1]) node.setSize?.([Math.max(node.size[0], size[0]), size[1]]);
}

function linkedInputs(node) {
  const names = new Set((node.widgets || []).map((w) => w.name));
  return (node.inputs || []).filter((i) => i.link != null && names.has(i.name)).map((i) => i.name);
}

function widgetValues(node) {
  const values = {};
  for (const w of node.widgets || []) {
    if (w.name === WIDGET || w.type === "button") continue;
    const v = w.value;
    if (["string", "number", "boolean"].includes(typeof v)) values[w.name] = v;
  }
  return values;
}

async function refresh(node) {
  if (!getWidget(node, WIDGET)) return;
  const linked = linkedInputs(node);
  if (linked.length) {
    const from = `${linked.join(", ")} ${linked.length > 1 ? "come" : "comes"} from another node`;
    show(node, node._kdxLastRun
      ? `${node._kdxLastRun}\n${TAG_RUN} (${from})`
      : `⏳ ${from} — the size is shown after the workflow runs.`);
    return;
  }
  const seq = (node._kdxSeq = (node._kdxSeq || 0) + 1);
  try {
    const res = await api.fetchApi("/kdx_resolution/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node: node.comfyClass, inputs: widgetValues(node) }),
    });
    const data = await res.json();
    if (seq !== node._kdxSeq) return; // a newer request is on its way
    show(node, data.error ? `⚠ ${data.error}` : `${data.summary}\n${TAG_PREVIEW}`);
  } catch (e) {
    if (seq === node._kdxSeq && node._kdxLastRun) show(node, `${node._kdxLastRun}\n${TAG_RUN}`);
  }
}

function schedule(node) {
  clearTimeout(node._kdxTimer);
  node._kdxTimer = setTimeout(() => refresh(node), DEBOUNCE_MS);
}

function hookWidgets(node) {
  for (const w of node.widgets || []) {
    if (w.name === WIDGET || w._kdxHooked) continue;
    w._kdxHooked = true;
    const orig = w.callback;
    w.callback = function () {
      const r = orig?.apply(this, arguments);
      schedule(node);
      return r;
    };
    w.inputEl?.addEventListener?.("input", () => schedule(node));
  }
}

app.registerExtension({
  name: "KDX.ResolutionSummary",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.category !== CATEGORY) return;
    nodeType.prototype._kdxResolution = true;

    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = origExecuted?.apply(this, arguments);
      const text = message?.kdx_summary?.[0];
      if (text !== undefined) {
        this._kdxLastRun = text;
        show(this, `${text}\n${TAG_RUN}`);
      }
      return r;
    };

    const origConn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = origConn?.apply(this, arguments);
      schedule(this);
      return r;
    };
  },

  nodeCreated(node) {
    if (!node._kdxResolution) return;
    addSummaryWidget(node);
    hookWidgets(node);
    schedule(node);
  },

  loadedGraphNode(node) {
    if (!node._kdxResolution) return;
    hookWidgets(node);
    schedule(node);
  },
});
