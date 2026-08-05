/* ATLAS map client — viewport-cached readings + human-readable detail. */
(function (global) {
  "use strict";

  const lib = global.AtlasMapLib;
  if (!lib) {
    throw new Error("AtlasMapLib missing — load map-lib.js before atlas.js");
  }

  const {
    STYLE,
    DEFAULT_LAYERS,
    el,
    debounce,
    stationsToGeoJSON,
    quakesToGeoJSON,
    inBbox,
    ensureSources,
  } = lib;

  function mount(opts) {
    const mode = opts.mode || "full";
    const enabled = { ...DEFAULT_LAYERS };
    let snapshot = null;
    let map = null;
    let es = null;
    let viewportBusy = false;
    let lastBboxKey = "";
    let activePopup = null;

    const mapEl = el("map");
    map = new maplibregl.Map({
      container: mapEl,
      style: STYLE,
      center: [10, 30],
      zoom: mode === "embed" ? 1.2 : 1.6,
      attributionControl: mode !== "embed",
      interactive: true,
    });
    if (mode === "full") {
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "bottom-right");
    }

    function currentBbox() {
      const b = map.getBounds();
      return {
        west: b.getWest(),
        south: b.getSouth(),
        east: b.getEast(),
        north: b.getNorth(),
      };
    }

    function setHud(snap) {
      const pill = el("status-pill");
      if (pill) {
        const st = snap?.status || "…";
        pill.textContent = snap?.stale ? `${st} · stale` : st;
        pill.dataset.state = snap?.stale ? "degraded" : st;
      }
      const ss = el("stat-stations");
      if (ss) {
        const cached = snap?.summary?.cached_readings ?? 0;
        const total = snap?.summary?.stations ?? 0;
        ss.textContent = `${cached}/${total} readings`;
      }
      const sq = el("stat-quakes");
      if (sq) sq.textContent = `${(snap?.quakes || []).length} quakes`;
      const sa = el("stat-age");
      if (sa) {
        const age = snap?.age_ms ?? 0;
        sa.textContent = age < 1000 ? "fleet live" : `fleet ${Math.round(age / 1000)}s`;
      }
    }

    function renderLayers(snap) {
      const host = el("layers");
      if (!host) return;
      const meta = snap?.layers || {};
      const counts = {};
      for (const s of snap?.stations || []) {
        counts[s.layer] = (counts[s.layer] || 0) + 1;
      }
      host.innerHTML = "";
      for (const [key, info] of Object.entries(meta)) {
        const row = document.createElement("label");
        row.className = "layer" + (enabled[key] !== false ? " active" : "");
        row.style.setProperty("--lc", info.color || "#3dd6c6");
        row.innerHTML =
          `<span class="swatch"></span><span class="name">${info.label || key}</span>` +
          `<span class="count">${counts[key] || 0}</span>`;
        row.addEventListener("click", () => {
          enabled[key] = !enabled[key];
          applySnapshot(snapshot);
          renderLayers(snapshot);
          renderStations(snapshot);
        });
        host.appendChild(row);
      }
    }

    function visibleStations(snap) {
      if (!map || !snap) return [];
      const b = currentBbox();
      return (snap.stations || [])
        .filter((s) => enabled[s.layer] !== false)
        .filter((s) => inBbox(s, b) || (s.kind === "region" && inBbox(s, {
          west: b.west - 4, south: b.south - 4, east: b.east + 4, north: b.north + 4,
        })))
        .sort((a, b2) => Number(b2.has_reading) - Number(a.has_reading) || Number(b2.online) - Number(a.online));
    }

    function renderStations(snap) {
      const host = el("station-list");
      if (!host) return;
      host.innerHTML = "";
      const list = visibleStations(snap);
      const hint = el("viewport-hint");
      if (hint) {
        hint.textContent = list.length ? `${list.length} in view` : "pan to sensors";
      }
      for (const s of list) {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "station" + (s.online ? "" : " off");
        card.style.setProperty("--lc", s.color || "#3dd6c6");
        const badge = s.has_reading
          ? `<span class="badge live">live</span>`
          : `<span class="badge">pin</span>`;
        card.innerHTML =
          `<div class="row"><span class="id">${s.id}</span>${badge}</div>` +
          `<div class="row" style="margin-top:4px"><span class="headline">${s.headline || "Tap for reading"}</span></div>` +
          `<div class="meta">${s.layer} · ${s.place || s.site || ""}</div>`;
        card.addEventListener("click", () => {
          if (Number.isFinite(s.lat) && Number.isFinite(s.lon)) {
            map.flyTo({ center: [s.lon, s.lat], zoom: Math.max(map.getZoom(), s.kind === "region" ? 4 : 5.5), essential: true });
          }
          openDetail(s.id);
        });
        host.appendChild(card);
      }
    }

    function applySnapshot(snap) {
      snapshot = snap;
      if (!snap || !map.isStyleLoaded()) return;
      ensureSources(map);
      map.getSource("stations").setData(stationsToGeoJSON(snap.stations, enabled));
      map.getSource("quakes").setData(quakesToGeoJSON(snap.quakes, enabled));
      setHud(snap);
      if (mode === "full") {
        renderLayers(snap);
        renderStations(snap);
      }
    }

    async function fetchSnapshot() {
      const r = await fetch("/api/v1/snapshot", { headers: { accept: "application/json" } });
      if (!r.ok) throw new Error("snapshot " + r.status);
      return r.json();
    }

    async function refreshViewport(force) {
      if (!map || viewportBusy) return;
      const bbox = currentBbox();
      const key = [bbox.west.toFixed(2), bbox.south.toFixed(2), bbox.east.toFixed(2), bbox.north.toFixed(2), !!force].join("|");
      if (!force && key === lastBboxKey) return;
      viewportBusy = true;
      const hint = el("viewport-hint");
      if (hint) hint.textContent = "loading…";
      try {
        const r = await fetch("/api/v1/viewport", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify({ ...bbox, force: !!force }),
        });
        if (!r.ok) throw new Error("viewport " + r.status);
        const data = await r.json();
        lastBboxKey = key;
        if (data.snapshot) applySnapshot(data.snapshot);
        else if (snapshot) {
          const byId = Object.fromEntries((snapshot.stations || []).map((s) => [s.id, s]));
          for (const s of data.stations || []) byId[s.id] = { ...byId[s.id], ...s, has_reading: true };
          applySnapshot({ ...snapshot, stations: Object.values(byId), quakes: data.quakes || snapshot.quakes });
        }
        if (hint) {
          const n = (data.requested || []).length;
          const hits = data.cache_hits || 0;
          hint.textContent = n ? `${n} sensors · ${hits} cache` : "no sensors here";
        }
      } catch (err) {
        if (hint) hint.textContent = "viewport error";
        console.warn(err);
      } finally {
        viewportBusy = false;
      }
    }

    function closeDetail() {
      const panel = el("detail");
      if (panel) panel.hidden = true;
      if (activePopup) {
        activePopup.remove();
        activePopup = null;
      }
    }

    function renderDetail(detail) {
      const panel = el("detail");
      if (!panel) return;
      panel.hidden = false;
      panel.classList.remove("loading");
      el("detail-title").textContent = detail.title || detail.label || detail.id;
      el("detail-sub").textContent = detail.subtitle || detail.place || "";
      el("detail-status").textContent = detail.status_line || "";
      el("detail-summary").textContent = detail.summary || "";
      const metrics = el("detail-metrics");
      metrics.innerHTML = "";
      for (const m of detail.metrics || []) {
        const row = document.createElement("div");
        row.className = "metric";
        row.innerHTML =
          `<span class="label">${m.label}</span><span class="value">${m.value}</span>` +
          (m.hint ? `<span class="hint">${m.hint}</span>` : "");
        metrics.appendChild(row);
      }
      const meta = [];
      if (detail.id) meta.push(`Device ${detail.id}`);
      if (detail.model) meta.push(detail.model);
      if (detail.source) meta.push(`Source: ${detail.source}`);
      if (detail.site) meta.push(`Site: ${detail.site}`);
      if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon)) {
        meta.push(`${Number(detail.lat).toFixed(4)}°, ${Number(detail.lon).toFixed(4)}°`);
      }
      el("detail-meta").textContent = meta.join(" · ");

      if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon) && map) {
        if (activePopup) activePopup.remove();
        const lines = (detail.metrics || [])
          .slice(0, 4)
          .map((m) => `<div><span style="opacity:.55">${m.label}</span> ${m.value}</div>`)
          .join("");
        activePopup = new maplibregl.Popup({ offset: 14, closeButton: false, maxWidth: "260px" })
          .setLngLat([detail.lon, detail.lat])
          .setHTML(
            `<strong style="color:${detail.color || "#3dd6c6"}">${detail.title || detail.id}</strong>` +
            `<div style="opacity:.7;margin:4px 0 6px">${detail.place || ""}</div>` +
            `<div style="margin-bottom:6px">${detail.headline || ""}</div>${lines}`
          )
          .addTo(map);
      }
    }

    async function openDetail(deviceId) {
      const panel = el("detail");
      if (panel && mode === "full") {
        panel.hidden = false;
        panel.classList.add("loading");
        el("detail-title").textContent = deviceId;
        el("detail-sub").textContent = "Fetching live reading…";
        el("detail-status").textContent = "";
        el("detail-summary").textContent = "";
        el("detail-metrics").innerHTML = "";
        el("detail-meta").textContent = "";
      }
      try {
        const r = await fetch(`/api/v1/stations/${encodeURIComponent(deviceId)}`, {
          headers: { accept: "application/json" },
        });
        if (!r.ok) throw new Error("station " + r.status);
        const detail = await r.json();
        if (snapshot) {
          const stations = (snapshot.stations || []).map((s) =>
            s.id === deviceId
              ? {
                  ...s,
                  ...detail,
                  has_reading: true,
                  headline: detail.headline || s.headline,
                  values: detail.values || {},
                }
              : s
          );
          applySnapshot({ ...snapshot, stations });
        }
        if (mode === "full") renderDetail(detail);
        else if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon)) {
          if (activePopup) activePopup.remove();
          activePopup = new maplibregl.Popup({ offset: 12, closeButton: true, maxWidth: "240px" })
            .setLngLat([detail.lon, detail.lat])
            .setHTML(
              `<strong style="color:${detail.color || "#3dd6c6"}">${detail.title || detail.id}</strong>` +
              `<div style="margin:4px 0;opacity:.75">${detail.headline || ""}</div>` +
              `<div style="opacity:.65">${detail.summary || ""}</div>`
            )
            .addTo(map);
        }
      } catch (err) {
        if (panel && mode === "full") {
          panel.classList.remove("loading");
          el("detail-summary").textContent = "Could not load this sensor. Try again.";
        }
        console.warn(err);
      }
    }

    map.on("load", () => {
      ensureSources(map);
      applySnapshot(snapshot);
      refreshViewport(false);
    });

    map.on("moveend", debounce(() => {
      if (mode === "full") renderStations(snapshot);
      refreshViewport(false);
    }, 450));

    map.on("click", "stations-core", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      openDetail(f.properties.id);
    });
    map.on("click", "quakes-core", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      openDetail("usgs-quake-01");
    });
    map.on("mouseenter", "stations-core", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "stations-core", () => { map.getCanvas().style.cursor = ""; });

    const closeBtn = el("detail-close");
    if (closeBtn) closeBtn.addEventListener("click", closeDetail);

    function connectSSE() {
      if (es) es.close();
      es = new EventSource("/api/v1/stream");
      es.addEventListener("snapshot", (ev) => {
        try {
          applySnapshot(JSON.parse(ev.data));
        } catch (_) {}
      });
    }

    const btn = el("btn-refresh");
    if (btn) {
      btn.addEventListener("click", async () => {
        lastBboxKey = "";
        await refreshViewport(true);
      });
    }

    const openFull = el("open-full");
    if (openFull) openFull.href = "/";

    fetchSnapshot()
      .then((snap) => {
        applySnapshot(snap);
        const pts = (snap.stations || []).filter(
          (s) => Number.isFinite(s.lat) && Number.isFinite(s.lon) && !(Math.abs(s.lat) < 1e-6 && Math.abs(s.lon) < 1e-6)
        );
        if (pts.length && mode === "full") {
          const bounds = new maplibregl.LngLatBounds();
          pts.forEach((p) => bounds.extend([p.lon, p.lat]));
          (snap.quakes || []).forEach((q) => bounds.extend([q.lon, q.lat]));
          map.once("moveend", () => refreshViewport(false));
          map.fitBounds(bounds, { padding: 80, maxZoom: 4, duration: 1100 });
        } else {
          refreshViewport(false);
        }
      })
      .catch(() => setHud({ status: "error", summary: {} }));

    connectSSE();
    setInterval(() => {
      fetchSnapshot().then(applySnapshot).catch(() => {});
    }, 45000);

    return { map, applySnapshot, openDetail, refreshViewport, visibleStations: () => visibleStations(snapshot) };
  }

  global.AtlasMap = { mount };
})(window);
