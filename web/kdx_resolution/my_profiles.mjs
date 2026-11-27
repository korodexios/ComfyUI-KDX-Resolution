// KDX Resolution - "My model profiles" editor.
//
// A my profile = a built-in profile (grid, size limits, ~MP) with your own size table.
// It appears in every model dropdown as "★ <name>". The server keeps the file
// (<user dir>/kdx_resolution/my_profiles.json) and checks every line; this dialog only edits.
//
// Opened from the right-click menu of any KDX Resolution node and from
// Extensions -> KDX Resolution in the top menu.

import { ensureTheme } from "./theme.mjs?v=0.6.7";

const CSS = `
.kdxr-mp-back{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:10000;display:flex;
 align-items:center;justify-content:center}
.kdxr-mp{width:min(860px,94vw);height:min(600px,90vh);display:flex;flex-direction:column;background:var(--kdx-bg);
 border:1px solid var(--kdx-border);border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.45);overflow:hidden;font-size:13px}
.kdxr-mp header{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--kdx-border)}
.kdxr-mp header h2{margin:0;font-size:15px;font-weight:600;flex:1}
.kdxr-mp header p{margin:0;color:var(--kdx-muted);font-size:12px}
.kdxr-mp .body{flex:1;display:flex;min-height:0}
.kdxr-mp .list{width:210px;border-right:1px solid var(--kdx-border);padding:8px;display:flex;flex-direction:column;
 gap:4px;overflow:auto;background:var(--kdx-card)}
.kdxr-mp .list button{all:unset;cursor:pointer;padding:6px 8px;border-radius:6px;white-space:nowrap;overflow:hidden;
 text-overflow:ellipsis;color:var(--kdx-fg)}
.kdxr-mp .list button:hover{background:var(--kdx-off-bg)}
.kdxr-mp .list button.sel{background:var(--kdx-acc);color:var(--kdx-on-acc)}
.kdxr-mp .list button.new{color:var(--kdx-acc-text);margin-top:4px}
.kdxr-mp .list button:focus-visible,.kdxr-mp button:focus-visible{outline:2px solid var(--kdx-acc);outline-offset:1px}
.kdxr-mp .list .empty{color:var(--kdx-muted);padding:6px 8px;font-size:12px}
.kdxr-mp .edit{flex:1;display:flex;flex-direction:column;gap:8px;padding:12px 14px;min-width:0;overflow:auto}
.kdxr-mp label{display:flex;flex-direction:column;gap:4px;color:var(--kdx-muted);font-size:12px}
.kdxr-mp input,.kdxr-mp select,.kdxr-mp textarea{background:var(--kdx-field);color:var(--kdx-fg);
 border:1px solid var(--kdx-border);border-radius:6px;padding:6px 8px;font:inherit}
.kdxr-mp input:focus-visible,.kdxr-mp select:focus-visible,.kdxr-mp textarea:focus-visible{outline:2px solid var(--kdx-acc);outline-offset:-1px}
.kdxr-mp .row{display:flex;gap:10px}
.kdxr-mp .row>label{flex:1}
.kdxr-mp .facts{color:var(--kdx-muted);font-size:12px}
.kdxr-mp .sizes{display:flex;gap:10px;flex:1;min-height:180px}
.kdxr-mp textarea{flex:1;resize:none;font-family:ui-monospace,Consolas,monospace;line-height:1.5}
.kdxr-mp table{border-collapse:collapse;font-variant-numeric:tabular-nums;align-self:flex-start}
.kdxr-mp .tbl{width:220px;overflow:auto;border:1px solid var(--kdx-border);border-radius:6px;background:var(--kdx-card)}
.kdxr-mp th,.kdxr-mp td{padding:3px 8px;text-align:right}
.kdxr-mp th{color:var(--kdx-muted);font-weight:500;position:sticky;top:0;background:var(--kdx-card)}
.kdxr-mp td:first-child,.kdxr-mp th:first-child{text-align:left}
.kdxr-mp .msgs{font-size:12px;display:flex;flex-direction:column;gap:2px;min-height:18px}
.kdxr-mp .msgs .err{color:var(--kdx-err)} .kdxr-mp .msgs .warn{color:var(--kdx-warn)} .kdxr-mp .msgs .ok{color:var(--kdx-ok)}
.kdxr-mp footer{display:flex;gap:8px;align-items:center;padding:10px 14px;border-top:1px solid var(--kdx-border)}
.kdxr-mp footer .hint{flex:1;color:var(--kdx-muted);font-size:12px}
.kdxr-mp .btn{cursor:pointer;border-radius:6px;padding:6px 14px;font:inherit;border:1px solid var(--kdx-border);
 background:var(--kdx-off-bg);color:var(--kdx-fg)}
.kdxr-mp .btn.primary{background:var(--kdx-acc);border-color:var(--kdx-acc);color:var(--kdx-on-acc);font-weight:600}
.kdxr-mp .btn.danger{color:var(--kdx-err)}
.kdxr-mp .btn.small{padding:3px 10px;font-size:12px}
.kdxr-mp .btn:disabled{opacity:.45;cursor:default}
.kdxr-mp .x{all:unset;cursor:pointer;padding:2px 8px;border-radius:6px;color:var(--kdx-muted);font-size:18px}
.kdxr-mp .x:hover{color:var(--kdx-fg);background:var(--kdx-off-bg)}
`;

const HELP = "One size per line, e.g.  16:9 = 1376x768  or just  1376x768  ·  # starts a comment";

let cssDone = false;

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid);
  return n;
}

async function getJson(api, url, body) {
  const res = await api.fetchApi(url, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

let open = null;

/** Open the editor. `onChanged()` runs after a save or delete (refresh the dropdowns). */
export async function openMyProfiles({ api, onChanged, select } = {}) {
  if (open) return;
  ensureTheme();
  if (!cssDone) {
    cssDone = true;
    document.head.append(el("style", { id: "kdx-resolution-my-profiles-style" }, CSS));
  }

  let data;
  try {
    data = await getJson(api, "/kdx_resolution/my_profiles");
  } catch (e) {
    console.warn("[KDX-Resolution] my profiles unavailable", e);
    window.alert("KDX Resolution: my profiles are unavailable (" + e.message + "). Restart ComfyUI after updating.");
    return;
  }
  const bases = data.bases || [];
  const baseByName = new Map(bases.map((b) => [b.name, b]));
  let mine = data.profiles || [];
  let current = null; // stored name being edited, null = new
  let saved = "";     // snapshot of the form when loaded/saved (unsaved-changes check)
  let checkTimer = 0;
  let lastCheck = null;

  const list = el("div", { class: "list", role: "listbox", "aria-label": "My profiles" });
  const name = el("input", { type: "text", maxlength: "60", placeholder: "e.g. Krea 2 mine", "aria-label": "Name" });
  const based = el("select", { "aria-label": "Based on" },
    el("option", { value: "" }, "— pick a model —"),
    ...["image", "video"].map((kind) => el("optgroup", { label: kind === "image" ? "Image models" : "Video models" },
      ...bases.filter((b) => b.kind === kind).map((b) => el("option", { value: b.name }, b.name)))));
  const facts = el("div", { class: "facts" });
  const text = el("textarea", { spellcheck: "false", "aria-label": "Sizes", placeholder: HELP });
  const tbody = el("tbody");
  const msgs = el("div", { class: "msgs", "aria-live": "polite" });
  const copyBtn = el("button", { class: "btn small", type: "button", title: "Put the base model's sizes into the box" },
    "Copy sizes from base");
  const delBtn = el("button", { class: "btn danger", type: "button" }, "Delete");
  const saveBtn = el("button", { class: "btn primary", type: "button" }, "Save");
  const hint = el("div", { class: "hint" });

  const form = () => JSON.stringify([name.value.trim(), based.value, text.value]);
  const dirty = () => form() !== saved;

  function renderList() {
    list.replaceChildren();
    if (!mine.length) list.append(el("div", { class: "empty" }, "No profiles yet."));
    for (const p of mine) {
      list.append(el("button", {
        type: "button", role: "option", class: p.name === current ? "sel" : "",
        "aria-selected": String(p.name === current), title: p.display_name + "  ·  based on " + p.based_on,
        onclick: () => confirmLeave() && load(p),
      }, p.display_name));
    }
    list.append(el("button", { type: "button", class: "new" + (current === null ? " sel" : ""),
      onclick: () => confirmLeave() && load(null) }, "＋ New profile"));
  }

  function renderFacts() {
    const b = baseByName.get(based.value);
    facts.textContent = b
      ? `Inherited from ${b.name}: grid /${b.multiple_of} · sides ${b.min_dim}–${b.max_dim} px` +
        (b.recommended_mp ? ` · trained ~${b.recommended_mp} MP` : "")
      : "The grid, size limits and ~MP come from the model you pick.";
    copyBtn.disabled = !b;
  }

  function load(p) {
    current = p ? p.name : null;
    name.value = p ? p.name : "";
    based.value = p ? p.based_on : "";
    text.value = p ? p.text : "";
    saved = form();
    delBtn.hidden = !p;
    renderList();
    renderFacts();
    (p ? text : name).focus();
    return check();
  }

  function confirmLeave() {
    return !dirty() || window.confirm("Discard the unsaved changes?");
  }

  function showResult(r) {
    tbody.replaceChildren(...(r.rows || []).map((row) =>
      el("tr", {}, el("td", {}, row.ar), el("td", {}, `${row.w}×${row.h}`), el("td", {}, row.mp.toFixed(2)))));
    msgs.replaceChildren(
      ...(r.errors || []).map((m) => el("div", { class: "err" }, "✖ " + m)),
      ...(r.warnings || []).map((m) => el("div", { class: "warn" }, "⚠ " + m)));
    if (r.ok && !(r.warnings || []).length && r.rows?.length) {
      msgs.append(el("div", { class: "ok" }, `✔ ${r.rows.length} size${r.rows.length > 1 ? "s" : ""}, ready to save`));
    }
    saveBtn.disabled = !r.ok || !dirty();
    hint.textContent = r.display_name ? `Shows in the model dropdowns as  ${r.display_name}` : HELP;
  }

  async function check() {
    clearTimeout(checkTimer);
    const body = { name: name.value, old_name: current || "", based_on: based.value, text: text.value };
    try {
      const r = await getJson(api, "/kdx_resolution/my_profiles/check", body);
      if (JSON.stringify(body) === JSON.stringify({ name: name.value, old_name: current || "",
        based_on: based.value, text: text.value })) {
        lastCheck = r;
        showResult(r);
      }
    } catch (e) {
      showResult({ ok: false, errors: ["check failed: " + e.message] });
    }
  }
  const later = () => { saveBtn.disabled = true; clearTimeout(checkTimer); checkTimer = setTimeout(check, 250); };

  async function reload(selectName) {
    const d = await getJson(api, "/kdx_resolution/my_profiles");
    mine = d.profiles || [];
    return load(mine.find((p) => p.name === selectName) || null);
  }

  async function save() {
    if (!lastCheck?.ok) return;
    saveBtn.disabled = true;
    const r = await getJson(api, "/kdx_resolution/my_profiles/save",
      { name: name.value, old_name: current || "", based_on: based.value, text: text.value });
    if (!r.ok) return showResult(r);
    await reload(name.value.trim());
    msgs.replaceChildren(el("div", { class: "ok" }, `✔ Saved as ${r.saved}. It is in the model dropdowns now.`));
    onChanged?.();
  }

  async function remove() {
    if (current === null) return;
    if (!window.confirm(`Delete "★ ${current}"? Workflows that use it will ask you to pick another model.`)) return;
    const r = await getJson(api, "/kdx_resolution/my_profiles/delete", { name: current });
    if (!r.ok) return showResult(r);
    await reload(null);
    onChanged?.();
  }

  function close() {
    if (!confirmLeave()) return;
    document.removeEventListener("keydown", onKey, true);
    back.remove();
    open = null;
  }
  function onKey(e) {
    if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); close(); }
    else if (e.key === "s" && (e.ctrlKey || e.metaKey)) { e.stopPropagation(); e.preventDefault(); save(); }
  }

  name.addEventListener("input", later);
  text.addEventListener("input", later);
  based.addEventListener("change", () => {
    renderFacts();
    if (!text.value.trim() && baseByName.get(based.value)) text.value = baseByName.get(based.value).text;
    check();
  });
  copyBtn.addEventListener("click", () => {
    const b = baseByName.get(based.value);
    if (!b) return;
    if (text.value.trim() && !window.confirm("Replace the sizes in the box with the sizes of " + b.name + "?")) return;
    text.value = b.text;
    check();
  });
  saveBtn.addEventListener("click", save);
  delBtn.addEventListener("click", remove);

  const dialog = el("div", { class: "kdxr-root kdxr-mp", role: "dialog", "aria-modal": "true", "aria-label": "My model profiles" },
    el("header", {},
      el("div", { style: "flex:1" }, el("h2", {}, "★ My model profiles"),
        el("p", {}, "A model's grid and limits with your own sizes. Pick it in any KDX Resolution model dropdown.")),
      el("button", { class: "x", type: "button", "aria-label": "Close", onclick: close }, "×")),
    el("div", { class: "body" }, list,
      el("div", { class: "edit" },
        el("div", { class: "row" },
          el("label", {}, "Name", name),
          el("label", {}, "Based on", based)),
        facts,
        el("div", { class: "row", style: "align-items:center" },
          el("div", { class: "facts", style: "flex:1" }, HELP), copyBtn),
        el("div", { class: "sizes" }, text,
          el("div", { class: "tbl" }, el("table", {},
            el("thead", {}, el("tr", {}, el("th", {}, "AR"), el("th", {}, "W×H"), el("th", {}, "MP"))), tbody))),
        msgs)),
    el("footer", {}, hint, delBtn, saveBtn));
  const back = el("div", { class: "kdxr-mp-back", onmousedown: (e) => { if (e.target === back) close(); } }, dialog);
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
  open = { close };

  renderList();
  load(mine.find((p) => p.name === select || p.display_name === select) || null);
}
