import { app } from "../../scripts/app.js";

// Filters the `preset` combo by the selected `model` (prefix "<model> | ").
app.registerExtension({
  name: "KDX.PresetFilter",

  nodeCreated(node) {
    if (node.comfyClass !== "KDX_Preset_Picker") return;
    const mw = node.widgets?.find((w) => w.name === "model");
    const pw = node.widgets?.find((w) => w.name === "preset");
    if (!mw || !pw) return;

    let all = [...pw.options.values];
    let shown = null;

    const apply = (resetValue) => {
      // A refresh (R, or a my-profiles save) replaced the list: start from the new one.
      if (shown && pw.options.values !== shown) all = [...pw.options.values];
      const pref = mw.value + " | ";
      const filtered = all.filter((v) => v.startsWith(pref));
      pw.options.values = shown = filtered.length ? filtered : all;
      if (resetValue && !pw.options.values.includes(pw.value)) {
        pw.value = pw.options.values[0];
      }
    };

    const orig = mw.callback;
    mw.callback = function () {
      const r = orig?.apply(this, arguments);
      apply(true);
      return r;
    };

    node._kdxApplyFilter = apply;
    apply(true);
  },

  // After loading a saved workflow: filter the list, but keep the saved value.
  loadedGraphNode(node) {
    if (node.comfyClass === "KDX_Preset_Picker") node._kdxApplyFilter?.(false);
  },
});
