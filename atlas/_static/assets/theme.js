/* ATLAS theme switcher — localStorage + MapLibre basemap sync. */
(function (global) {
  "use strict";

  const STORAGE_KEY = "atlas-theme";
  const DEFAULT_ID = "void-teal";

  const THEMES = [
    { id: "void-teal", name: "Void Teal", kind: "dark · default", sw: "#3dd6c6" },
    { id: "void-sky", name: "Void Sky", kind: "dark", sw: "#5eb8ff" },
    { id: "void-amber", name: "Void Amber", kind: "dark", sw: "#f0a040" },
    { id: "ops-green", name: "Ops Green", kind: "dark", sw: "#34d399" },
    { id: "deep-violet", name: "Deep Violet", kind: "dark · premium", sw: "#c084fc" },
    { id: "graphite", name: "Graphite", kind: "dark", sw: "#94a3b8" },
    { id: "premium-gold", name: "Premium Gold", kind: "dark · premium", sw: "#d4af37" },
    { id: "orbit-light", name: "Orbit Light", kind: "light", sw: "#0d9488" },
    { id: "paper-ops", name: "Paper Ops", kind: "light", sw: "#0f766e" },
    { id: "premium-pearl", name: "Premium Pearl", kind: "light · premium", sw: "#0891b2" },
  ];

  const IDS = new Set(THEMES.map((t) => t.id));

  function readStored() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v && IDS.has(v)) return v;
    } catch (_) { /* private mode */ }
    return DEFAULT_ID;
  }

  function basemapMode() {
    const raw = getComputedStyle(document.documentElement)
      .getPropertyValue("--map-basemap")
      .trim()
      .toLowerCase();
    return raw === "light" ? "light" : "dark";
  }

  function applyTheme(id, opts) {
    const themeId = IDS.has(id) ? id : DEFAULT_ID;
    document.documentElement.dataset.theme = themeId;
    try {
      localStorage.setItem(STORAGE_KEY, themeId);
    } catch (_) { /* ignore */ }
    const mode = basemapMode();
    if (opts && typeof opts.onBasemap === "function") {
      opts.onBasemap(mode, themeId);
    }
    global.dispatchEvent(
      new CustomEvent("atlas:theme", { detail: { id: themeId, basemap: mode } })
    );
    return themeId;
  }

  function current() {
    return document.documentElement.dataset.theme || DEFAULT_ID;
  }

  function mountPicker(hudEl, opts) {
    if (!hudEl) return null;
    const getLocale = (opts && opts.getLocale) || (() => null);
    const tr = (key) => global.AtlasI18n
      ? global.AtlasI18n.t(key, null, getLocale())
      : key;
    const kindLabel = (raw) => String(raw || "")
      .split("·")
      .map((part) => tr(`theme.${part.trim()}`))
      .join(" · ");
    const wrap = document.createElement("div");
    wrap.className = "theme-wrap";
    wrap.innerHTML =
      `<button type="button" class="theme-btn" id="theme-btn" aria-haspopup="listbox" aria-expanded="false" title="${tr("theme.title")}">` +
      `<span class="dot" aria-hidden="true"></span><span class="label">${tr("theme.title")}</span>` +
      `</button>` +
      `<div class="theme-menu" id="theme-menu" role="listbox" hidden></div>`;
    hudEl.appendChild(wrap);

    const btn = wrap.querySelector("#theme-btn");
    const menu = wrap.querySelector("#theme-menu");
    const label = wrap.querySelector(".label");

    function renderMenu() {
      const cur = current();
      menu.innerHTML = THEMES.map((t) => {
        const checked = t.id === cur ? "true" : "false";
        return (
          `<button type="button" class="theme-opt" role="option" data-id="${t.id}" aria-checked="${checked}">` +
          `<span class="sw" style="--sw:${t.sw}"></span>` +
          `<span class="meta"><span class="name">${t.name}</span><span class="kind">${kindLabel(t.kind)}</span></span>` +
          `</button>`
        );
      }).join("");
      const meta = THEMES.find((t) => t.id === cur);
      if (meta && label) label.textContent = meta.name;
    }

    function close() {
      menu.hidden = true;
      btn.setAttribute("aria-expanded", "false");
    }

    function open() {
      renderMenu();
      menu.hidden = false;
      btn.setAttribute("aria-expanded", "true");
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (menu.hidden) open();
      else close();
    });

    menu.addEventListener("click", (e) => {
      const opt = e.target.closest(".theme-opt");
      if (!opt) return;
      applyTheme(opt.dataset.id, opts);
      renderMenu();
      close();
    });

    document.addEventListener("click", (e) => {
      if (!wrap.contains(e.target)) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });

    renderMenu();
    return { applyTheme, current, THEMES };
  }

  // Apply stored theme ASAP (before map paint if script is early).
  applyTheme(readStored());

  global.AtlasTheme = {
    THEMES,
    DEFAULT_ID,
    applyTheme,
    current,
    basemapMode,
    mountPicker,
    readStored,
  };
})(window);
