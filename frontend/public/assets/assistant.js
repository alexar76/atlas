/* ATLAS Analyst — floating grounded chat (DeepSeek by default). */
(function (global) {
  "use strict";

  const SUGGESTIONS = [
    { label: "Situation report", q: "Составь ситуационный отчёт по всем доступным датчикам", report: true },
    { label: "Air quality", q: "Проанализируй качество воздуха по станциям в снимке" },
    { label: "Weather compare", q: "Сравни погоду Berlin vs NYC по живым readings" },
    { label: "Earthquakes", q: "Что с землетрясениями? Краткий разбор последних событий" },
    { label: "Anomalies", q: "Есть ли аномалии или пробелы в данных датчиков?" },
  ];

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

    const root = el("div", "ai-root");
    const fab = el("button", "ai-fab", "<span>AI</span>");
    fab.type = "button";
    fab.title = "ATLAS Analyst";
    fab.setAttribute("aria-label", "Open ATLAS Analyst");

    const panel = el("div", "ai-panel");
    panel.hidden = true;
    panel.innerHTML =
      `<header class="ai-head">` +
      `<div><strong>ATLAS Analyst</strong><div class="ai-sub">DeepSeek · live sensors</div></div>` +
      `<button type="button" class="ghost ai-close" aria-label="Close">✕</button>` +
      `</header>` +
      `<div class="ai-meta"><select class="ai-provider" title="Provider"></select>` +
      `<select class="ai-role" title="Model"><option value="heavy">pro</option><option value="light">flash</option></select></div>` +
      `<div class="ai-chips"></div>` +
      `<div class="ai-messages" role="log" aria-live="polite"></div>` +
      `<form class="ai-form">` +
      `<textarea class="ai-input" rows="2" placeholder="Ask about sensors or request a report…"></textarea>` +
      `<button type="submit" class="ai-send">Ask</button>` +
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

    addMsg(
      "assistant",
      "ATLAS Analyst online. I see live GAIA relays — ask for analysis or a situation report."
    );

    SUGGESTIONS.forEach((s) => {
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
        for (const p of data.providers || []) {
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = (p.is_default ? "★ " : "") + p.id + (p.available ? "" : " (no key)");
          opt.disabled = !p.available && !p.is_default;
          if (p.is_default) opt.selected = true;
          providerSel.appendChild(opt);
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
      const pending = el("div", "ai-msg ai-assistant ai-pending", "Analyzing live sensors…");
      messages.appendChild(pending);
      messages.scrollTop = messages.scrollHeight;
      try {
        const body = {
          question: q,
          locale: getLocale(),
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
          addMsg("assistant", data.detail || ("Error " + r.status));
        } else {
          let answer = data.answer || "(empty)";
          const meta = data.meta || {};
          if (meta.offline) {
            answer += "\n\n— offline mode (set DEEPSEEK_API_KEY)";
          } else if (meta.model) {
            answer += `\n\n— ${meta.provider || "llm"} · ${meta.model}`;
          }
          addMsg("assistant", answer);
        }
      } catch (err) {
        pending.remove();
        addMsg("assistant", "Request failed: " + (err && err.message ? err.message : err));
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

    return { ask, open: () => { panel.hidden = false; loadProviders(); } };
  }

  global.AtlasAI = { mount };
})(window);
