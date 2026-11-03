// Injected into every page during recording. Reports only trusted (user)
// events through the exposed binding `__rrEmit`; script-generated events are
// ignored. Selectors prefer stable attributes over structure.
(() => {
  if (window.__rrRecorderInstalled) return;
  window.__rrRecorderInstalled = true;

  const cssEscape = (s) => (window.CSS && CSS.escape ? CSS.escape(s) : s.replace(/["\\]/g, "\\$&"));
  const unique = (sel) => {
    try { return document.querySelectorAll(sel).length === 1; } catch (_) { return false; }
  };

  function selectorFor(el) {
    if (!(el instanceof Element)) return null;
    const tid = el.getAttribute("data-testid");
    if (tid && unique(`[data-testid="${cssEscape(tid)}"]`)) return `[data-testid="${cssEscape(tid)}"]`;
    if (el.id && unique(`#${cssEscape(el.id)}`)) return `#${cssEscape(el.id)}`;
    const name = el.getAttribute("name");
    if (name) {
      const s = `${el.tagName.toLowerCase()}[name="${cssEscape(name)}"]`;
      if (unique(s)) return s;
    }
    const tag = el.tagName.toLowerCase();
    if ((tag === "button" || tag === "a") && el.textContent.trim()) {
      const text = el.textContent.trim().replace(/\s+/g, " ").slice(0, 80);
      const s = `${tag}:has-text("${text.replace(/"/g, '\\"')}")`;
      const same = [...document.querySelectorAll(tag)].filter((e) => e.textContent.trim().replace(/\s+/g, " ").slice(0, 80) === text);
      if (same.length === 1) return s;
    }
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.documentElement; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
      parts.unshift(`${n.tagName.toLowerCase()}:nth-of-type(${i})`);
    }
    return parts.join(" > ");
  }

  const actionable = (t) => (t instanceof Element ? t.closest("button, a, input, select, textarea, label, [role=button], [onclick]") : null);

  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    const el = actionable(e.target);
    // A click on inert content only moves focus; it is not an action.
    if (!el) return;
    // Clicks that only focus a text field are represented by the later fill.
    if (el.matches("input:not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]), textarea")) return;
    window.__rrEmit({ type: "browser_click", selector: selectorFor(el), url: location.href, title: document.title });
  }, true);

  document.addEventListener("change", (e) => {
    if (!e.isTrusted) return;
    const el = e.target;
    if (!el.matches("input, textarea, select")) return;
    if (el.type === "password") {
      window.__rrEmit({ type: "unsupported", reason: "password fields are not recorded", url: location.href });
      return;
    }
    window.__rrEmit({ type: "browser_fill", selector: selectorFor(el), value: el.value, url: location.href, title: document.title });
  }, true);

  document.addEventListener("keydown", (e) => {
    if (!e.isTrusted || e.key !== "Enter") return;
    const el = e.target;
    // Enter/Space on a button already produces a trusted click; recording the
    // key too would replay the activation twice. Only text inputs keep Enter.
    if (!(el instanceof Element) || !el.matches("input:not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]), select")) return;
    // Commit the pending value first so fill precedes the Enter press.
    if (el.matches("input")) {
      window.__rrEmit({ type: "browser_fill", selector: selectorFor(el), value: el.value, url: location.href, title: document.title });
    }
    window.__rrEmit({ type: "browser_press", selector: selectorFor(el), key: "Enter", url: location.href, title: document.title });
  }, true);
})();
