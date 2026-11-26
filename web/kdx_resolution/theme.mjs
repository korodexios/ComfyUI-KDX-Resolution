// KDX Resolution - look shared with KDX Wildcard Studio and KDX LLM: KDX blue accent + light/dark tokens.
//
// Same accent and tokens as the theme.mjs of KDX Wildcard Studio and KDX LLM, but every
// class here is prefixed `kdxr-` so the packs never restyle each other's elements.
// Light or dark: compare the luminance of the page background with the page text (as
// Pixaroma's light_theme.mjs); the result is the shared `html.kdx-light` class, which
// all KDX packs compute the same way. Default is dark.
// (.mjs on purpose: ComfyUI auto-loads only *.js from WEB_DIRECTORY.)

export const ACCENT = {
  dark: { acc: "#6f8dff", onAcc: "#060b1f", accText: "#9bb0ff" },
  light: { acc: "#2f4fd1", onAcc: "#ffffff", accText: "#2742b0" },
};

const CSS = `
.kdxr-root{--kdx-acc:${ACCENT.dark.acc};--kdx-on-acc:${ACCENT.dark.onAcc};--kdx-acc-text:${ACCENT.dark.accText};
 --kdx-bg:#1b1e21;--kdx-card:#23272b;--kdx-fg:#e7e9ea;--kdx-muted:#9aa1a7;--kdx-border:#363c42;
 --kdx-off-bg:#2b3035;--kdx-off-fg:#8b9298;--kdx-warn:#f0b429;--kdx-err:#ff6b6b;--kdx-ok:#4cc38a;--kdx-field:#15181a;
 font:12px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--kdx-fg);box-sizing:border-box}
html.kdx-light .kdxr-root{--kdx-acc:${ACCENT.light.acc};--kdx-on-acc:${ACCENT.light.onAcc};--kdx-acc-text:${ACCENT.light.accText};
 --kdx-bg:#f6f7f6;--kdx-card:#ffffff;--kdx-fg:#1d211f;--kdx-muted:#4f5752;--kdx-border:#c9d0cb;
 --kdx-off-bg:#eceeed;--kdx-off-fg:#5e6661;--kdx-warn:#8a5a00;--kdx-err:#b3261e;--kdx-ok:#1e7a4c;--kdx-field:#ffffff}

textarea.kdxr-root.kdxr-summary{background:var(--kdx-field);color:var(--kdx-fg);border:1px solid var(--kdx-border);
 border-left:3px solid var(--kdx-ok);border-radius:6px;padding:6px 8px;user-select:text;resize:none;cursor:default}
textarea.kdxr-root.kdxr-summary::placeholder{color:var(--kdx-muted)}
textarea.kdxr-root.kdxr-summary:focus-visible{outline:2px solid var(--kdx-acc);outline-offset:-1px}
textarea.kdxr-root.kdxr-summary.warn{border-left-color:var(--kdx-warn)}
textarea.kdxr-root.kdxr-summary.err{border-left-color:var(--kdx-err);color:var(--kdx-err)}
textarea.kdxr-root.kdxr-summary.wait{border-left-color:var(--kdx-border);color:var(--kdx-muted)}
`;

let injected = false;

function luminance(color) {
  const m = String(color).match(/\d+(\.\d+)?/g);
  if (!m || m.length < 3) return null;
  const [r, g, b] = m.slice(0, 3).map((v) => {
    const c = Number(v) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function detectLight() {
  try {
    const cs = getComputedStyle(document.body);
    const bg = luminance(cs.backgroundColor);
    const fg = luminance(cs.color);
    const light = bg != null && fg != null && bg > fg;
    document.documentElement.classList.toggle("kdx-light", light);
  } catch (_e) { /* keep dark */ }
}

export function ensureTheme() {
  if (injected) return;
  injected = true;
  const st = document.createElement("style");
  st.id = "kdx-resolution-style";
  st.textContent = CSS;
  document.head.appendChild(st);
  detectLight();
  // ComfyUI rewrites the palette as inline style on <html> when the theme changes.
  new MutationObserver(() => detectLight()).observe(document.documentElement, {
    attributes: true, attributeFilter: ["style"],
  });
}
