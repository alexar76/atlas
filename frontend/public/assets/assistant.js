/* ATLAS Analyst — floating grounded chat (DeepSeek by default). */
(function (global) {
  "use strict";

  const SUGGESTIONS = {
    en: [
      { label: "Situation report", q: "Write a situation report for all available sensors", report: true },
      { label: "Show Berlin", q: "Show Berlin weather and air quality on the map" },
      { label: "Fly to NYC", q: "Fly to New York and open the NWS and tide stations" },
      { label: "Earthquakes", q: "Show the latest earthquake and open its pin" },
      { label: "Ecosystem", q: "How do ATLAS, GAIA, the Hub, and ARGUS fit in the AIMarket ecosystem?" },
    ],
    ru: [
      { label: "Ситуация", q: "Составь ситуационный отчёт по всем доступным датчикам", report: true },
      { label: "Берлин", q: "Покажи на карте погоду и воздух в Берлине" },
      { label: "Нью-Йорк", q: "Приблизь Нью-Йорк и открой NWS и приливную станцию" },
      { label: "Сейсмика", q: "Покажи последнее землетрясение и открой пин" },
      { label: "Экосистема", q: "Как ATLAS, GAIA, Hub и ARGUS связаны в экосистеме AIMarket?" },
    ],
    es: [
      { label: "Informe", q: "Haz un informe de situación de todos los sensores disponibles", report: true },
      { label: "Berlín", q: "Muestra en el mapa el clima y el aire de Berlín" },
      { label: "Nueva York", q: "Vuela a Nueva York y abre NWS y la estación de marea" },
      { label: "Sismos", q: "Muestra el último terremoto y abre su pin" },
      { label: "Ecosistema", q: "¿Cómo encajan ATLAS, GAIA, el Hub y ARGUS en el ecosistema AIMarket?" },
    ],
    fr: [
      { label: "Rapport", q: "Rédige un rapport de situation pour tous les capteurs disponibles", report: true },
      { label: "Berlin", q: "Montre sur la carte la météo et l'air à Berlin" },
      { label: "New York", q: "Vole vers New York et ouvre NWS et la station de marée" },
      { label: "Séismes", q: "Montre le dernier séisme et ouvre son pin" },
      { label: "Écosystème", q: "Comment ATLAS, GAIA, le Hub et ARGUS s'articulent dans l'écosystème AIMarket ?" },
    ],
    zh: [
      { label: "态势报告", q: "请根据所有可用传感器写一份态势报告", report: true },
      { label: "柏林", q: "在地图上显示柏林的天气和空气质量" },
      { label: "纽约", q: "飞到纽约并打开 NWS 与潮汐站点" },
      { label: "地震", q: "显示最近地震并打开对应针脚" },
      { label: "生态", q: "ATLAS、GAIA、Hub 和 ARGUS 在 AIMarket 生态中如何协作？" },
    ],
  };

  const GREETING = {
    en: "ATLAS Analyst online. I can answer from live sensors + ecosystem brief — and fly the map / open pins when you ask.",
    ru: "ATLAS Analyst на связи. Отвечаю по датчикам и экосистеме — и приближаю карту / открываю пины по запросу.",
    es: "ATLAS Analyst en línea. Respondo con sensores + ecosistema — y vuelo el mapa / abro pins si lo pides.",
    fr: "ATLAS Analyst en ligne. Réponses capteurs + écosystème — et je vole la carte / ouvre les pins sur demande.",
    zh: "ATLAS Analyst 已上线。可答传感器与生态，并按请求飞向地图 / 打开针脚。",
  };

  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function mount(opts) {
    const getBbox = opts.getBbox || (() => null);
    const getStationIds = opts.getStationIds || (() => null);
    const getLocale = opts.getLocale || (() => "en");
    const onActions = opts.onActions || (async () => {});

    function uiLocale() {
      const raw = (getLocale() || "en").toString().slice(0, 2).toLowerCase();
      return SUGGESTIONS[raw] ? raw : "en";
    }

    function tr(key, vars) {
      return global.AtlasI18n
        ? global.AtlasI18n.t(key, vars, uiLocale())
        : key;
    }

    const root = el("div", "ai-root");
    const fab = el("button", "ai-fab", "<span>AI</span>");
    fab.type = "button";
    fab.title = "ATLAS Analyst";
    fab.setAttribute("aria-label", tr("assistant.open"));

    const panel = el("div", "ai-panel");
    panel.hidden = true;
    panel.innerHTML =
      `<header class="ai-head">` +
      `<div><strong>ATLAS Analyst</strong><div class="ai-sub">${tr("assistant.subtitle")}</div></div>` +
      `<button type="button" class="ghost ai-close" aria-label="${tr("shell.close")}">✕</button>` +
      `</header>` +
      `<div class="ai-meta"><select class="ai-provider" title="${tr("assistant.provider")}"></select>` +
      `<select class="ai-role" title="${tr("assistant.model")}"><option value="heavy">pro</option><option value="light">flash</option></select></div>` +
      `<div class="ai-chips"></div>` +
      `<div class="ai-messages" role="log" aria-live="polite"></div>` +
      `<form class="ai-form">` +
      `<textarea class="ai-input" rows="2" placeholder="${tr("assistant.placeholder")}"></textarea>` +
      `<button type="submit" class="ai-send">${tr("assistant.ask")}</button>` +
      `</form>`;

    root.appendChild(fab);
    root.appendChild(panel);
    document.body.appendChild(root);

    const messages = panel.querySelector(".ai-messages");
    const input = panel.querySelector(".ai-input");
    const form = panel.querySelector(".ai-form");
    const providerSel = panel.querySelector(".ai-provider");
    const roleSel = panel.querySelector(".ai-role");
    const chips = panel.querySelector(".ai-chips");
    let loading = false;
    let history = [];

    function addMsg(role, content) {
      const row = el("div", "ai-msg ai-" + role);
      row.textContent = content;
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;
      history.push({ role, content });
    }

    const loc0 = uiLocale();
    addMsg("assistant", GREETING[loc0] || GREETING.en);

    (SUGGESTIONS[loc0] || SUGGESTIONS.en).forEach((s) => {
      const b = el("button", "ai-chip", s.label);
      b.type = "button";
      b.addEventListener("click", () => {
        input.value = s.q;
        ask(s.q, !!s.report);
      });
      chips.appendChild(b);
    });

    async function loadProviders() {
      try {
        const r = await fetch("/api/ai/providers");
        const data = await r.json();
        providerSel.innerHTML = "";
        let defaultId = "";
        for (const p of data.providers || []) {
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent =
            (p.is_default ? "★ " : "") +
            p.id +
            (p.provider_type ? ` · ${p.provider_type}` : "") +
            (p.available ? "" : ` (${tr("assistant.unavailable")})`);
          opt.disabled = !p.available;
          if (p.is_default) defaultId = p.id;
          if (p.is_default && p.available) opt.selected = true;
          providerSel.appendChild(opt);
        }
        // Prefer the server default; only fall back to another *available*
        // provider. Never silently switch to an unreachable local backend.
        const defaultOpt = [...providerSel.options].find((o) => o.value === defaultId);
        if (defaultOpt && !defaultOpt.disabled) {
          providerSel.value = defaultId;
        } else {
          const avail = [...providerSel.options].find((o) => !o.disabled);
          providerSel.value = avail ? avail.value : defaultId || providerSel.value;
        }
        if (!providerSel.options.length) {
          const opt = document.createElement("option");
          opt.value = "deepseek_api";
          opt.textContent = "deepseek_api";
          providerSel.appendChild(opt);
        }
      } catch (_) {
        const opt = document.createElement("option");
        opt.value = "deepseek_api";
        opt.textContent = "deepseek_api";
        providerSel.appendChild(opt);
      }
    }

    async function ask(question, report) {
      const q = (question || "").trim();
      if (!q || loading) return;
      loading = true;
      addMsg("user", q);
      input.value = "";
      const pending = el("div", "ai-msg ai-assistant ai-pending", tr("assistant.analyzing"));
      messages.appendChild(pending);
      messages.scrollTop = messages.scrollHeight;
      try {
        const body = {
          question: q,
          locale: uiLocale(),
          provider: providerSel.value || "deepseek_api",
          model_role: roleSel.value || "heavy",
          report: !!report,
        };
        const bbox = getBbox();
        if (bbox) body.bbox = bbox;
        const ids = getStationIds();
        if (ids && ids.length) body.station_ids = ids;
        const r = await fetch("/api/ai/ask", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify(body),
        });
        const data = await r.json().catch(() => ({}));
        pending.remove();
        if (!r.ok) {
          addMsg("assistant", data.detail || tr("assistant.error", { status: r.status }));
        } else {
          let answer = data.answer || tr("assistant.empty");
          const meta = data.meta || {};
          if (meta.offline) {
            answer += `\n\n— ${tr("assistant.offline")}`;
          } else if (meta.blocked) {
            answer += `\n\n— ${tr("assistant.blocked")}`;
          } else if (meta.model) {
            answer += `\n\n— ${meta.provider || "llm"} · ${meta.model}` +
              (meta.provider_type ? ` · ${meta.provider_type}` : "");
          }
          addMsg("assistant", answer);
          const actions = data.actions || [];
          if (actions.length) {
            try {
              await onActions(actions);
            } catch (err) {
              console.warn("map actions failed", err);
            }
          }
        }
      } catch (err) {
        pending.remove();
        addMsg("assistant", tr("assistant.requestFailed", {
          error: err && err.message ? err.message : err,
        }));
      } finally {
        loading = false;
      }
    }

    fab.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) {
        loadProviders();
        input.focus();
      }
    });
    panel.querySelector(".ai-close").addEventListener("click", () => {
      panel.hidden = true;
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      ask(input.value, false);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        ask(input.value, false);
      }
    });

    loadProviders();
    return { root, ask };
  }

  global.AtlasAI = { mount };
})(typeof window !== "undefined" ? window : globalThis);
