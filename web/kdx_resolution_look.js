import { app } from "../../scripts/app.js";

// Node colours by role (LiteGraph palette values, same scheme as KDX-LLM).
// Applied only to freshly created nodes: a colour the user picked is kept,
// because a saved workflow's colour is restored after nodeCreated runs.
const ROLE_COLORS = {
  size: { color: "#232", bgcolor: "#353" },      // green  - produces W×H
  ratio: { color: "#323", bgcolor: "#535" },     // purple - works with AR text
  transform: { color: "#223", bgcolor: "#335" }, // blue   - changes an existing W×H
};
const NODE_ROLES = {
  KDX_Preset_Picker: "size",
  KDX_AutoResolution_Core: "size",
  KDX_Megapixel_Selector: "size",
  KDX_AR_Extractor: "ratio",
  KDX_Prompt_Extractor: "ratio",
  KDX_AR_Validator: "ratio",
  KDX_AR_Batch_Tester: "ratio",
  KDX_Reverse_AR_Matcher: "ratio",
  KDX_Nearest_Native_Preset: "transform",
  KDX_Resolution_Step: "transform",
  KDX_Resolution_Scaler: "transform",
  KDX_Resolution_To_String: "transform",
};

app.registerExtension({
  name: "KDX.ResolutionLook",
  nodeCreated(node) {
    const role = NODE_ROLES[node.comfyClass];
    if (!role || node.color || node.bgcolor) return;
    Object.assign(node, ROLE_COLORS[role]);
  },
});
