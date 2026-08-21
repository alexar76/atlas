/* ATLAS map client — viewport-cached readings + human-readable detail. */
(function (global) {
  "use strict";

  const lib = global.AtlasMapLib;
  if (!lib) {
    throw new Error("AtlasMapLib missing — load map-lib.js before atlas.js");
  }

  const {
    STYLE,
    styleForBasemap,
    DEFAULT_LAYERS,
    el,
    esc,
    safeColor,
    normalizeBbox,
    debounce,
    readProjection,
    writeProjection,
    readGlobeSurface,
    writeGlobeSurface,
    applyProjection,
    applySky,
    setSensorData,
    ensureSources,
    inBbox,
  } = lib;

  function mount(opts) {
    const mode = opts.mode || "full";
    const currentLocale = () => {
      const raw = typeof opts.getLocale === "function" ? opts.getLocale() : "en";
      return global.AtlasI18n ? global.AtlasI18n.locale(raw) : String(raw || "en").slice(0, 2);
    };
    const tr = (key, vars) => global.AtlasI18n
      ? global.AtlasI18n.t(key, vars, currentLocale())
      : key;
    const enabled = { ...DEFAULT_LAYERS };
    // Shareable focused views for portal/use-case deep links, e.g.
    // ?layers=fire,weather or ?layers=jamming. Unknown keys fail open.
    try {
      const requested = (new URLSearchParams(global.location.search).get("layers") || "")
        .split(",")
        .map((key) => key.trim().toLowerCase())
        .filter((key) => Object.prototype.hasOwnProperty.call(DEFAULT_LAYERS, key));
      if (requested.length) {
        Object.keys(enabled).forEach((key) => { enabled[key] = requested.includes(key); });
        document.documentElement.dataset.focusLayers = requested.join(",");
      }
    } catch (_) { /* malformed URL: keep the complete map */ }
    let snapshot = null;
    let map = null;
    let es = null;
    let viewportBusy = false;
    let lastBboxKey = "";
    let activePopup = null;
    let mapReady = false;
    let lastPushAt = 0;
    // Session cache: every point ever shown, keyed by id. Region keys skip
    // re-fetch when the camera returns to an explored cell. Both expire —
    // FIRMS detections roll daily, so ghosts must not outlive their region.
    const pointCache = new Map();
    const regionCache = new Map(); // key → merged-at ms
    const REGION_TTL_MS = 10 * 60 * 1000;
    const EVENT_PIN_TTL_MS = 15 * 60 * 1000;
    // Comfortably under the pin TTL so event layers are re-merged before they expire.
    const EVENT_PIN_REFRESH_MS = 5 * 60 * 1000;
    // Sidebar must not snap back to catalog parents (fire=1) after a brief empty poll,
    // but a high-water mark must also decay once the feed genuinely shrinks.
    const layerHighWater = Object.create(null); // layer → {n, at}
    const HIGH_WATER_TTL_MS = 5 * 60 * 1000;
    let fireWatchdogAt = 0;
    let hintStickyUntil = 0;
    let projectionMode = mode === "full" ? "globe" : readProjection("mercator");
    let surfaceMode = readGlobeSurface("countries");
    let userInteracting = false;
    let spinRaf = 0;
    let spinResumeTimer = null;
    let introPlayed = false;
    /** Degrees per second while globe is in hero orbit (wow spin). */
    const HERO_SPIN_DPS = 14;
    const HERO_ZOOM = 2.22;
    const HERO_PITCH = 56;

    const mapEl = el("map");
    const initialBasemap =
      (global.AtlasTheme && global.AtlasTheme.basemapMode()) || "dark";
    if (mode === "full") {
      writeProjection("globe");
      try {
        document.documentElement.dataset.projection = "globe";
        document.documentElement.dataset.surface = surfaceMode;
        document.documentElement.dataset.basemap = initialBasemap;
      } catch (_) { /* ignore */ }
    }
    map = new maplibregl.Map({
      container: mapEl,
      style: styleForBasemap
        ? styleForBasemap(initialBasemap, projectionMode, surfaceMode)
        : STYLE,
      center: mode === "full" && projectionMode === "globe" ? [12, 16] : [10, 22],
      zoom: mode === "embed" ? 1.15 : projectionMode === "globe" ? 1.35 : 1.6,
      pitch: projectionMode === "globe" && mode === "full" ? 48 : 0,
      bearing: mode === "full" && projectionMode === "globe" ? -18 : 0,
      maxPitch: 85,
      attributionControl: false,
      interactive: true,
      locale: global.AtlasI18n ? global.AtlasI18n.mapLibreLocale(currentLocale()) : undefined,
    });
    if (mode === "full") {
      map.addControl(
        new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }),
        "bottom-right"
      );
      if (typeof maplibregl.GlobeControl === "function") {
        try {
          map.addControl(new maplibregl.GlobeControl(), "bottom-right");
        } catch (_) { /* optional */ }
      }
    }

    function syncQuietAttribution() {
      if (mode === "embed") return;
      let box = document.getElementById("atlas-attrib");
      if (!box) {
        box = document.createElement("div");
        box.id = "atlas-attrib";
        box.className = "atlas-attrib";
        box.setAttribute("aria-label", tr("map.attribution"));
        mapEl.appendChild(box);
      }
      const parts = [];
      try {
        const style = map.getStyle();
        const sources = (style && style.sources) || {};
        Object.keys(sources).forEach((id) => {
          const attr = sources[id] && sources[id].attribution;
          if (attr && parts.indexOf(attr) < 0) parts.push(attr);
        });
      } catch (_) { /* style settling */ }
      if (!parts.length) {
        parts.push(
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OSM</a> &copy; <a href="https://carto.com/" target="_blank" rel="noopener">CARTO</a>'
        );
      }
      box.innerHTML =
        '<a href="https://maplibre.org/" target="_blank" rel="noopener">MapLibre</a> · ' +
        parts.join(" · ");
    }

    map.on("load", syncQuietAttribution);
    map.on("styledata", syncQuietAttribution);

    let basemapKind = initialBasemap;

    function stopSpin() {
      if (spinRaf) {
        cancelAnimationFrame(spinRaf);
        spinRaf = 0;
      }
    }

    function spinFrame(ts) {
      spinRaf = 0;
      if (projectionMode !== "globe" || userInteracting || !map) return;
      if (map.getZoom() > 4.2) return;
      if (!spinFrame._last) spinFrame._last = ts || performance.now();
      const now = ts || performance.now();
      const dt = Math.min(0.05, (now - spinFrame._last) / 1000);
      spinFrame._last = now;
      map.rotateTo((map.getBearing() + HERO_SPIN_DPS * dt) % 360, { duration: 0 });
      spinRaf = requestAnimationFrame(spinFrame);
    }

    function startSpinSoon(delayMs) {
      clearTimeout(spinResumeTimer);
      spinResumeTimer = setTimeout(() => {
        if (projectionMode !== "globe" || userInteracting) return;
        stopSpin();
        spinFrame._last = 0;
        spinRaf = requestAnimationFrame(spinFrame);
      }, delayMs == null ? 200 : delayMs);
    }

    function playGlobeIntro() {
      if (introPlayed || mode !== "full" || projectionMode !== "globe" || !map) return;
      introPlayed = true;
      try {
        if (typeof map.setProjection === "function") {
          map.setProjection({ type: "globe" });
        }
        applySky(map, basemapKind, "globe");
      } catch (_) { /* ignore */ }
      map.jumpTo({ center: [28, 8], zoom: 1.2, pitch: 40, bearing: -35 });
      map.easeTo({
        center: [8, 18],
        zoom: HERO_ZOOM,
        pitch: HERO_PITCH,
        bearing: 25,
        duration: 3200,
        essential: true,
        easing: (t) => 1 - Math.pow(1 - t, 3),
      });
      map.once("moveend", () => {
        refreshViewport(false);
        startSpinSoon(0);
      });
      // Safety if moveend is skipped
      setTimeout(() => {
        if (projectionMode === "globe" && !userInteracting) {
          refreshViewport(false);
          startSpinSoon(0);
        }
      }, 3600);
    }

    function markInteracting() {
      userInteracting = true;
      stopSpin();
      clearTimeout(spinResumeTimer);
      spinResumeTimer = setTimeout(() => {
        userInteracting = false;
        startSpinSoon(400);
      }, 2200);
    }

    ["mousedown", "touchstart", "wheel", "dragstart"].forEach((evt) => {
      map.on(evt, markInteracting);
    });

    function setProjectionToggleUi() {
      const btn = el("proj-btn");
      if (!btn) return;
      const globe = projectionMode === "globe";
      btn.dataset.mode = globe ? "globe" : "flat";
      btn.setAttribute("aria-pressed", globe ? "true" : "false");
      btn.title = globe ? tr("projection.toFlat") : tr("projection.toGlobe");
      const label = btn.querySelector(".label");
      if (label) label.textContent = globe ? tr("projection.globe") : tr("projection.flat");
      document.documentElement.dataset.projection = globe ? "globe" : "mercator";
      const surfBtn = el("surface-btn");
      if (surfBtn) {
        surfBtn.hidden = !globe;
        setSurfaceToggleUi();
      }
    }

    function setSurfaceToggleUi() {
      const btn = el("surface-btn");
      if (!btn) return;
      const physical = surfaceMode === "physical";
      btn.dataset.mode = physical ? "physical" : "countries";
      btn.setAttribute("aria-pressed", physical ? "true" : "false");
      btn.title = physical
        ? tr("surface.toCountries")
        : tr("surface.toPhysical");
      const label = btn.querySelector(".label");
      if (label) label.textContent = physical ? tr("surface.physical") : tr("surface.countries");
      try {
        document.documentElement.dataset.surface = surfaceMode;
      } catch (_) { /* ignore */ }
    }

    function reloadMapStyle() {
      if (!map || !styleForBasemap) return;
      const center = map.getCenter();
      const zoom = map.getZoom();
      const bearing = map.getBearing();
      const pitch = map.getPitch();
      map.setStyle(styleForBasemap(basemapKind, projectionMode, surfaceMode));
      map.once("style.load", () => {
        map.jumpTo({ center, zoom, bearing, pitch });
        try {
          ensureSources(map);
          applySky(map, basemapKind, projectionMode);
          if (typeof map.setProjection === "function") {
            map.setProjection({ type: projectionMode === "globe" ? "globe" : "mercator" });
          }
        } catch (_) { /* style settling */ }
        applySnapshot(null);
        syncQuietAttribution();
      });
    }

    function setSurfaceMode(next) {
      const modeNext = next === "physical" ? "physical" : "countries";
      if (modeNext === surfaceMode) return;
      surfaceMode = modeNext;
      writeGlobeSurface(modeNext);
      setSurfaceToggleUi();
      reloadMapStyle();
    }

    function setProjectionMode(next, opts) {
      const modeNext = next === "globe" ? "globe" : "mercator";
      const animate = !(opts && opts.animate === false);
      projectionMode = modeNext;
      writeProjection(modeNext);
      setProjectionToggleUi();
      if (!map || !styleForBasemap) return;
      const center = map.getCenter();
      const zoom = map.getZoom();
      const bearing = map.getBearing();
      const pitch = map.getPitch();
      map.setStyle(styleForBasemap(basemapKind, projectionMode, surfaceMode));
      map.once("style.load", () => {
        try {
          ensureSources(map);
          applySky(map, basemapKind, projectionMode);
          if (typeof map.setProjection === "function") {
            map.setProjection({ type: modeNext === "globe" ? "globe" : "mercator" });
          }
        } catch (_) { /* style settling */ }
        applySnapshot(null);
        syncQuietAttribution();
        if (modeNext === "globe") {
          map.easeTo({
            center,
            zoom: Math.min(Math.max(zoom, 1.8), HERO_ZOOM),
            pitch: HERO_PITCH,
            bearing,
            duration: animate ? 1200 : 0,
          });
          startSpinSoon(600);
        } else {
          map.easeTo({
            center,
            zoom: Math.max(zoom, 1.4),
            pitch: 0,
            bearing: 0,
            duration: animate ? 900 : 0,
          });
          stopSpin();
        }
      });
    }

    function mountProjectionToggle() {
      const hud = el("hud");
      if (!hud || el("proj-btn")) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.id = "proj-btn";
      btn.className = "proj-btn";
      btn.innerHTML =
        `<span class="proj-icon" aria-hidden="true"></span>` +
        `<span class="label">${tr("projection.globe")}</span>`;
      btn.addEventListener("click", () => {
        setProjectionMode(projectionMode === "globe" ? "mercator" : "globe");
      });
      hud.appendChild(btn);

      const surf = document.createElement("button");
      surf.type = "button";
      surf.id = "surface-btn";
      surf.className = "proj-btn surface-btn";
      surf.innerHTML =
        `<span class="surf-icon" aria-hidden="true"></span>` +
        `<span class="label">${tr("surface.countries")}</span>`;
      surf.addEventListener("click", () => {
        setSurfaceMode(surfaceMode === "physical" ? "countries" : "physical");
      });
      hud.appendChild(surf);

      setProjectionToggleUi();
    }

    function applyBasemap(kind) {
      const next = kind === "light" ? "light" : "dark";
      if (next === basemapKind || !styleForBasemap) return;
      basemapKind = next;
      try {
        document.documentElement.dataset.basemap = next;
      } catch (_) { /* ignore */ }
      reloadMapStyle();
    }

    if (mode === "full") {
      mountProjectionToggle();
    }
    if (global.AtlasTheme && mode === "full") {
      global.AtlasTheme.mountPicker(el("hud"), { onBasemap: applyBasemap, getLocale: currentLocale });
    }
    global.addEventListener("atlas:theme", (ev) => {
      applyBasemap(ev.detail && ev.detail.basemap);
    });
    if (mode === "full" && projectionMode === "globe") {
      /* intro + spin kicked from markMapReady / snapshot */
    }
    // Normalized to the server contract (±180 / ±90) — MapLibre returns
    // unwrapped bounds when the world is narrower than the canvas.
    function currentBbox() {
      return normalizeBbox(map);
    }

    function setHud(snap) {
      const pill = el("status-pill");
      if (pill) {
        const st = snap?.status || "boot";
        const statusLabel = tr(`status.${st}`) === `status.${st}` ? st : tr(`status.${st}`);
        pill.textContent = snap?.stale ? `${statusLabel} · ${tr("status.stale")}` : statusLabel;
        pill.dataset.state = snap?.stale ? "degraded" : st;
      }
      const ss = el("stat-stations");
      if (ss) {
        const cached = snap?.summary?.cached_readings ?? 0;
        const total = snap?.summary?.stations ?? 0;
        const live = snap?.summary?.live ?? 0;
        const sim = snap?.summary?.sim ?? 0;
        ss.textContent = `${cached}/${total} · ${live} LIVE · ${sim} SIM`;
      }
      const sq = el("stat-quakes");
      if (sq) {
        const qn = (snap?.quakes || []).length;
        const fn = snap?.summary?.fires ?? (snap?.stations || []).filter((s) => s.layer === "fire").length;
        const quakeText = tr("hud.quakes", { count: qn });
        sq.textContent = fn > 1 ? `${quakeText} · ${tr("hud.fires", { count: fn })}` : quakeText;
      }
      const sa = el("stat-age");
      if (sa) {
        const age = snap?.age_ms ?? 0;
        sa.textContent = age < 1000
          ? tr("hud.fleetLive")
          : tr("hud.fleetAge", { seconds: Math.round(age / 1000) });
      }
    }

    function layerLabel(info, key) {
      const short = currentLocale();
      const labels = info && info.labels;
      if (labels && typeof labels === "object") {
        if (labels[short]) return labels[short];
        if (labels.en) return labels.en;
      }
      return (info && info.label) || key;
    }

    function formatLayerCount(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "—";
      try {
        return new Intl.NumberFormat(currentLocale(), { maximumFractionDigits: 0 }).format(number);
      } catch (_) {
        return String(Math.round(number));
      }
    }

    function layerCountPresentation(entry, inView) {
      const item = entry && typeof entry === "object" ? entry : {};
      const kind = String(item.count_kind || "stations");
      const status = String(item.status || "unavailable");
      const count = item.count === null || item.count === undefined ? null : Number(item.count);
      const total = Number(item.total_sources);
      let value = count === null ? "—" : formatLayerCount(count);
      if (
        count !== null && Number.isFinite(count) && Number.isFinite(total) && total > count &&
        (kind === "stations" || kind === "sources")
      ) {
        value = `${formatLayerCount(count)}/${formatLayerCount(total)}`;
      }
      const kindText = tr(`layer.countKind.${kind}`);
      const statusText = status === "live" ? "" : tr(`layer.status.${status}`);
      const viewText = (
        (status === "live" || status === "partial") && count !== null && Number.isFinite(inView)
      ) ? tr("layer.inView", { count: formatLayerCount(inView) }) : "";
      return {
        value,
        meta: [kindText, statusText || viewText].filter(Boolean).join(" · "),
        status,
      };
    }

    function expandedParentIds(now) {
      const parents = new Set();
      for (const item of pointCache.values()) {
        if (!item || !item.parent_id) continue;
        if (item.kind === "event" && item._at && now - item._at > EVENT_PIN_TTL_MS) continue;
        parents.add(String(item.parent_id));
      }
      return parents;
    }

    function actionableLayerCountsInView() {
      const counts = Object.create(null);
      if (!map) return counts;
      const bbox = currentBbox();
      const now = Date.now();
      const expandedParents = expandedParentIds(now);
      for (const item of pointCache.values()) {
        if (!item || !item.layer || !Number.isFinite(item.lat) || !Number.isFinite(item.lon)) continue;
        if (item.cluster_parent) continue;
        if (item.kind === "event" && item._at && now - item._at > EVENT_PIN_TTL_MS) continue;
        if (expandedParents.has(String(item.id))) continue;
        if (!(item.online || item.has_reading)) continue;
        if (!inBbox(item, bbox)) continue;
        counts[item.layer] = (counts[item.layer] || 0) + 1;
      }
      return counts;
    }

    function renderLayers(snap) {
      const host = el("layers");
      if (!host) return;
      const meta = snap?.layers || {};
      const contract = snap?.summary?.layer_counts;
      const hasContract = contract && typeof contract === "object" && Object.keys(contract).length > 0;
      const inViewCounts = actionableLayerCountsInView();
      const counts = {};
      if (!hasContract) {
        // Compatibility with older ATLAS servers. New servers provide the typed
        // layer_counts contract and never need this client-side reconstruction.
        const summaryCounts = snap?.summary?.by_layer;
        if (summaryCounts && typeof summaryCounts === "object") {
          for (const [k, v] of Object.entries(summaryCounts)) {
            const n = Number(v);
            if (Number.isFinite(n)) counts[k] = n;
          }
        }
        const fires = Number(snap?.summary?.fires);
        if (Number.isFinite(fires) && fires > (counts.fire || 0)) counts.fire = fires;
        for (const s of snap?.stations || []) {
          if (!s || !s.layer) continue;
          const matched = Number(s.hotspot_matched ?? s.hotspot_count);
          if (Number.isFinite(matched) && matched > (counts[s.layer] || 0)) {
            counts[s.layer] = matched;
          }
        }
        const nowMs = Date.now();
        for (const [k, v] of Object.entries(counts)) {
          const n = Number(v);
          if (!Number.isFinite(n) || n <= 0) continue;
          const hw = layerHighWater[k];
          if (!hw || nowMs - hw.at > HIGH_WATER_TTL_MS || n >= hw.n) {
            layerHighWater[k] = { n, at: nowMs };
          }
        }
        for (const [k, hw] of Object.entries(layerHighWater)) {
          if (!hw || nowMs - hw.at > HIGH_WATER_TTL_MS) {
            delete layerHighWater[k];
            continue;
          }
          if (hw.n > (counts[k] || 0)) counts[k] = hw.n;
        }
      }
      host.innerHTML = "";
      for (const [key, info] of Object.entries(meta)) {
        const row = document.createElement("label");
        row.className = "layer" + (enabled[key] !== false ? " active" : "");
        row.dataset.layer = key;
        row.style.setProperty("--lc", safeColor(info.color));
        const presented = layerCountPresentation(
          hasContract
            ? contract[key]
            : { count: counts[key] || 0, count_kind: "stations", status: "live" },
          Number(inViewCounts[key] || 0)
        );
        row.dataset.countStatus = presented.status;
        row.title = presented.meta;
        row.innerHTML =
          `<span class="swatch"></span><span class="name">${esc(layerLabel(info, key))}</span>` +
          `<span class="count-group"><span class="count">${esc(presented.value)}</span>` +
          `<span class="count-meta">${esc(presented.meta)}</span></span>`;
        row.addEventListener("click", () => {
          enabled[key] = !enabled[key];
          paintFromCache();
          renderLayers(snapshot);
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
      // Sidebar lists clickable sensors — event pins (up to 2000 densified
      // FIRMS detections) stay on the map, not as thousands of DOM cards.
      const list = visibleStations(snap)
        .filter((s) => s.kind !== "event")
        .slice(0, 120);
      const hint = el("viewport-hint");
      if (hint && Date.now() > hintStickyUntil) {
        hint.textContent = list.length
          ? tr("viewport.inView", { count: list.length })
          : tr("viewport.pan");
      }
      for (const s of list) {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "station" + (s.online ? "" : " off");
        card.style.setProperty("--lc", safeColor(s.color));
        const badge = s.live
          ? `<span class="badge live" title="${esc(tr("station.liveTitle"))}">LIVE</span>`
          : s.mode === "sim"
            ? `<span class="badge sim" title="${esc(tr("station.simTitle"))}">SIM</span>`
            : s.has_reading
              ? `<span class="badge">${esc(tr("station.reading"))}</span>`
              : `<span class="badge">${esc(tr("station.pin"))}</span>`;
        const modeHint = s.live ? tr("station.liveRelay") : (s.mode === "sim" ? "SIM" : tr("station.pin"));
        // Upstream (GAIA relay) strings are untrusted — escape every sink.
        card.innerHTML =
          `<div class="row"><span class="id">${esc(s.id)}</span>${badge}</div>` +
          `<div class="row" style="margin-top:4px"><span class="headline">${esc(s.headline || tr("station.tap"))}</span></div>` +
          `<div class="meta">${esc(s.layer)} · ${modeHint} · ${esc(s.place || s.site || "")}</div>`;
        card.addEventListener("click", () => {
          if (Number.isFinite(s.lat) && Number.isFinite(s.lon)) {
            markInteracting();
            map.flyTo({
              center: [s.lon, s.lat],
              zoom: Math.max(map.getZoom(), s.kind === "region" ? 4 : 5.5),
              pitch: projectionMode === "globe" ? Math.max(map.getPitch(), 42) : map.getPitch(),
              essential: true,
            });
          }
          openDetail(s.id);
        });
        host.appendChild(card);
      }
    }

    function regionKeysForBbox(b, zoom) {
      const z = Number.isFinite(zoom) ? zoom : 3;
      const step = z < 3 ? 20 : z < 5 ? 8 : z < 7 ? 3 : 1;
      const keys = [];
      const south = Math.floor(b.south / step) * step;
      const north = Math.ceil(b.north / step) * step;
      let west = Math.floor(b.west / step) * step;
      let east = Math.ceil(b.east / step) * step;
      if (b.west > b.east) {
        // dateline — cover both sides simply
        west = -180;
        east = 180;
      }
      for (let lat = south; lat < north; lat += step) {
        for (let lon = west; lon < east; lon += step) {
          keys.push(`${step}:${lat}:${lon}`);
        }
      }
      return keys;
    }

    function mergePoints(points) {
      const at = Date.now();
      for (const p of points || []) {
        if (!p || !p.id) continue;
        if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
        p._at = at;
        pointCache.set(String(p.id), p);
      }
    }

    function markRegions(b) {
      const z = map ? map.getZoom() : 3;
      const at = Date.now();
      for (const k of regionKeysForBbox(b, z)) regionCache.set(k, at);
    }

    function regionsCached(b) {
      const z = map ? map.getZoom() : 3;
      const keys = regionKeysForBbox(b, z);
      const now = Date.now();
      return (
        keys.length > 0 &&
        keys.every((k) => {
          const at = regionCache.get(k);
          return at && now - at < REGION_TTL_MS;
        })
      );
    }

    function pointsInView(b, pad) {
      const p = Number.isFinite(pad) ? pad : 2;
      const view = {
        west: b.west - p,
        south: b.south - p,
        east: b.east + p,
        north: b.north + p,
      };
      const out = [];
      const now = Date.now();
      const expandedParents = expandedParentIds(now);
      for (const s of pointCache.values()) {
        if (enabled[s.layer] === false) continue;
        if (s.cluster_parent) continue;
        // Event detections roll (FIRMS is a 24h feed) — drop ghosts the server
        // stopped sending instead of painting them forever.
        if (s.kind === "event" && s._at && now - s._at > EVENT_PIN_TTL_MS) continue;
        // Once a parent SKU has been expanded, paint/count its actionable
        // children only. Otherwise the summary pin becomes a fake extra event.
        if (expandedParents.has(String(s.id))) continue;
        if (inBbox(s, view)) out.push(s);
      }
      return out;
    }

    function paintFromCache() {
      if (!mapReady || !map) return;
      const b = currentBbox();
      const pts = pointsInView(b, 3);
      setSensorData(map, pts, snapshot?.quakes || [], enabled);
      setHud(snapshot);
      if (mode === "full") {
        renderLayers(snapshot);
        // IN VIEW list from cache ∩ camera (not the slim catalog snapshot).
        renderStations({ ...snapshot, stations: pts });
      }
    }

    // Gate on the map "load" event (sources/layers can be added), NOT on
    // isStyleLoaded(): the latter stays false while style changes are pending,
    // so snapshots used to be dropped with no retry (blank pins, HUD stuck).
    function applySnapshot(snap) {
      if (snap) snapshot = snap;
      if (!snapshot) return;
      // Catalog stations seed the cache; densified map_points arrive via viewport.
      mergePoints(snapshot.stations || []);
      if (!mapReady) return;
      paintFromCache();
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
      // Instant paint from session cache while (or instead of) fetching.
      paintFromCache();
      const cached = !force && regionsCached(bbox);
      if (cached) {
        lastBboxKey = key;
        const hint = el("viewport-hint");
        if (hint) {
          const n = pointsInView(bbox, 0).length;
          hint.textContent = tr("viewport.cacheHit", { count: n });
          hintStickyUntil = Date.now() + 4000;
        }
        // Map pins stay warm; still refresh sidebar totals (avoid stuck fire=1 after restart).
        fetchSnapshot()
          .then((snap) => {
            applySnapshot(snap);
            const fireN = Number(snap?.summary?.fires || snap?.summary?.by_layer?.fire || 0);
            // A genuinely fire-free feed (no FIRMS key / upstream down) must not
            // become a forced-refresh loop that burns the 6/min force budget:
            // one plain re-fetch per 5 minutes, no force.
            if (fireN <= 1 && Date.now() - fireWatchdogAt > 5 * 60 * 1000) {
              fireWatchdogAt = Date.now();
              regionCache.clear();
              lastBboxKey = "";
              refreshViewport(false);
            }
          })
          .catch(() => {});
        return;
      }
      viewportBusy = true;
      const hint = el("viewport-hint");
      if (hint) hint.textContent = tr("viewport.loading");
      try {
        const r = await fetch("/api/v1/viewport", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify({ ...bbox, force: !!force }),
        });
        if (!r.ok) throw new Error("viewport " + r.status);
        const data = await r.json();
        lastBboxKey = key;
        markRegions(bbox);
        if (data.snapshot) {
          snapshot = data.snapshot;
          mergePoints(data.snapshot.stations || []);
        }
        mergePoints(data.map_points || []);
        // Parent stations from ensure_readings may carry values without lat for events —
        // map_points already expanded.
        paintFromCache();
        if (hint) {
          const n = pointsInView(bbox, 0).length;
          const hits = data.cache_hits || 0;
          const fires = Number(data.snapshot?.summary?.fires || snapshot?.summary?.fires || 0);
          const firePins = Number(data.snapshot?.summary?.fire_pins || 0);
          const cachedN = pointCache.size;
          let fireBit = "";
          if (fires) {
            fireBit = ` · ${tr("viewport.fireSummary", { pins: firePins, total: fires })}`;
          }
          hint.textContent = tr("viewport.summary", { count: n, cached: cachedN, hits }) + fireBit;
          hintStickyUntil = Date.now() + 4000;
        }
      } catch (err) {
        if (hint) hint.textContent = tr("viewport.error");
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

    function externalHttpsUrl(raw) {
      try {
        const url = new URL(String(raw || ""));
        return url.protocol === "https:" ? url.href : "";
      } catch (_) {
        return "";
      }
    }

    function argoInvokeCurl(detail) {
      const invoke = detail && detail.invoke;
      if (!invoke || typeof invoke !== "object") return "";
      const endpoint = externalHttpsUrl(invoke.gateway_url);
      const capability = String(invoke.capability_id || "");
      const input = invoke.input && typeof invoke.input === "object" ? invoke.input : {};
      if (!endpoint || !capability) return "";
      const body = JSON.stringify({
        product_id: "gaia.gateway",
        capability_id: capability,
        source_hub: "atlas",
        input,
      });
      return `curl -sS -X POST '${endpoint}' -H 'content-type: application/json' -d '${body}'`;
    }

    function atlasPointInvokeCurl(detail) {
      const pointId = String(detail && detail.id || "").trim();
      const endpoint = externalHttpsUrl(`${global.location.origin}/ai-market/v2/invoke`);
      if (!pointId || !endpoint) return "";
      const body = JSON.stringify({
        product_id: "atlas.products",
        capability_id: "atlas.point.read@v1",
        input: { point_id: pointId, fresh: false },
      });
      return `curl -sS -X POST '${endpoint}' -H 'content-type: application/json' -d '${body}'`;
    }

    function renderDetailActions(detail) {
      const host = el("detail-actions");
      if (!host) return;
      host.innerHTML = "";
      const addLink = (url, label, secondary) => {
        const href = externalHttpsUrl(url);
        if (!href) return;
        const link = document.createElement("a");
        link.className = "detail-action" + (secondary ? " secondary" : "");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        host.appendChild(link);
      };
      addLink(detail.profile_url, tr("detail.openProfile"), false);
      addLink(detail.source_url, tr("detail.openSource"), true);
      if (!detail.profile_url) addLink(detail.directory_url, tr("detail.openDirectory"), false);
      const pointCurl = atlasPointInvokeCurl(detail);
      if (pointCurl) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "detail-action";
        button.textContent = tr("detail.copyPointInvoke");
        button.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(pointCurl);
            button.textContent = tr("detail.pointCopied");
            global.setTimeout(() => { button.textContent = tr("detail.copyPointInvoke"); }, 1800);
          } catch (_) {
            button.textContent = tr("detail.copyFailed");
          }
        });
        host.appendChild(button);
      }
      const curl = argoInvokeCurl(detail);
      if (curl) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "detail-action secondary";
        button.textContent = tr("detail.copyInvoke");
        button.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(curl);
            button.textContent = tr("detail.copied");
            global.setTimeout(() => { button.textContent = tr("detail.copyInvoke"); }, 1800);
          } catch (_) {
            button.textContent = tr("detail.copyFailed");
          }
        });
        host.appendChild(button);
      }
      host.hidden = host.childElementCount === 0;
    }

    function renderDetail(detail) {
      const panel = el("detail");
      if (!panel) return;
      panel.hidden = false;
      panel.classList.remove("loading");
      el("detail-title").textContent = detail.title || detail.label || detail.id;
      el("detail-sub").textContent = detail.subtitle || detail.place || "";
      const statusBits = [detail.status_line || ""];
      if (detail.profile_quality === "position_only_qc_rejected") {
        statusBits.push(tr("detail.qcRejected"));
      } else if (detail.profile_quality === "argovis_fallback_no_gdac_qc") {
        statusBits.push(tr("detail.qcFallback"));
      }
      el("detail-status").textContent = statusBits.filter(Boolean).join(" · ");
      el("detail-summary").textContent = detail.summary || "";
      if (detail.evidence_boundary) {
        el("detail-summary").textContent += ` ${detail.evidence_boundary}`;
      }
      const metrics = el("detail-metrics");
      metrics.innerHTML = "";
      for (const m of detail.metrics || []) {
        const row = document.createElement("div");
        row.className = "metric";
        row.innerHTML =
          `<span class="label">${esc(m.label)}</span><span class="value">${esc(m.value)}</span>` +
          (m.hint ? `<span class="hint">${esc(m.hint)}</span>` : "");
        metrics.appendChild(row);
      }
      renderDetailActions(detail);
      const meta = [];
      if (detail.id) meta.push(tr("detail.device", { value: detail.id }));
      if (detail.model) meta.push(detail.model);
      if (detail.source) meta.push(tr("detail.source", { value: detail.source }));
      if (detail.site) meta.push(tr("detail.site", { value: detail.site }));
      if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon)) {
        meta.push(`${Number(detail.lat).toFixed(4)}°, ${Number(detail.lon).toFixed(4)}°`);
      }
      el("detail-meta").textContent = meta.join(" · ");

      if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon) && map) {
        if (activePopup) activePopup.remove();
        const lines = (detail.metrics || [])
          .slice(0, 4)
          .map((m) => `<div><span style="opacity:.55">${esc(m.label)}</span> ${esc(m.value)}</div>`)
          .join("");
        activePopup = new maplibregl.Popup({ offset: 14, closeButton: false, maxWidth: "260px" })
          .setLngLat([detail.lon, detail.lat])
          .setHTML(
            `<strong style="color:${safeColor(detail.color)}">${esc(detail.title || detail.id)}</strong>` +
            `<div style="opacity:.7;margin:4px 0 6px">${esc(detail.place || "")}</div>` +
            `<div style="margin-bottom:6px">${esc(detail.headline || "")}</div>${lines}`
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
        el("detail-sub").textContent = tr("detail.fetching");
        el("detail-status").textContent = "";
        el("detail-summary").textContent = "";
        el("detail-metrics").innerHTML = "";
        const actions = el("detail-actions");
        if (actions) { actions.innerHTML = ""; actions.hidden = true; }
        el("detail-meta").textContent = "";
      }
      // The card needs a headline + metrics. Asking for the raw cluster made
      // argo-01 a 2.1 MB fetch to fill a sidebar; the pins already arrive via
      // /viewport. Only the fetch belongs in this try — a render bug below
      // must not be reported to the user as "could not load this sensor".
      let detail;
      try {
        const r = await fetch(
          `/api/v1/stations/${encodeURIComponent(deviceId)}?brief=1`,
          { headers: { accept: "application/json" } },
        );
        if (!r.ok) throw new Error("station " + r.status);
        detail = await r.json();
      } catch (err) {
        if (panel && mode === "full") {
          panel.classList.remove("loading");
          el("detail-summary").textContent = tr("detail.failed");
        }
        console.warn("station fetch failed", deviceId, err);
        return;
      }
      try {
        if (snapshot) {
          const prev = pointCache.get(String(deviceId)) || {};
          const merged = {
            ...prev,
            ...detail,
            id: deviceId,
            has_reading: true,
            headline: detail.headline || prev.headline,
            values: detail.values || {},
          };
          // A detail without finite coords must not drop the whole update —
          // keep the pin where the cache already has it.
          if (!Number.isFinite(detail.lat) || !Number.isFinite(detail.lon)) {
            merged.lat = prev.lat;
            merged.lon = prev.lon;
          }
          mergePoints([merged]);
          paintFromCache();
        }
        if (mode === "full") renderDetail(detail);
        else if (Number.isFinite(detail.lat) && Number.isFinite(detail.lon)) {
          if (activePopup) activePopup.remove();
          activePopup = new maplibregl.Popup({ offset: 12, closeButton: true, maxWidth: "240px" })
            .setLngLat([detail.lon, detail.lat])
            .setHTML(
              `<strong style="color:${safeColor(detail.color)}">${esc(detail.title || detail.id)}</strong>` +
              `<div style="margin:4px 0;opacity:.75">${esc(detail.headline || "")}</div>` +
              `<div style="opacity:.65">${esc(detail.summary || "")}</div>`
            )
            .addTo(map);
        }
      } catch (err) {
        // The data arrived; painting it did not. Clear the spinner but keep
        // whatever renderDetail managed to set — do not blame the network.
        if (panel && mode === "full") panel.classList.remove("loading");
        console.error("station render failed", deviceId, err);
      }
    }

    function flyToPlace(lon, lat, zoom) {
      if (!map || !Number.isFinite(lon) || !Number.isFinite(lat)) return Promise.resolve();
      return new Promise((resolve) => {
        const onEnd = () => {
          map.off("moveend", onEnd);
          resolve();
        };
        map.once("moveend", onEnd);
        markInteracting();
        map.flyTo({
          center: [lon, lat],
          zoom: Number.isFinite(zoom) ? zoom : Math.max(map.getZoom(), 6),
          pitch: projectionMode === "globe" ? Math.max(map.getPitch(), 45) : map.getPitch(),
          essential: true,
          duration: 1400,
        });
        // Safety if already there / no moveend
        setTimeout(() => {
          map.off("moveend", onEnd);
          resolve();
        }, 1600);
      });
    }

    async function applyActions(actions) {
      const list = Array.isArray(actions) ? actions : [];
      for (const action of list) {
        if (!action || typeof action !== "object") continue;
        if (action.type === "fly_to") {
          await flyToPlace(Number(action.lon), Number(action.lat), Number(action.zoom));
          lastBboxKey = "";
          await refreshViewport(false);
        } else if (action.type === "focus_station" && action.station_id) {
          const sid = String(action.station_id);
          const pin = (snapshot?.stations || []).find((s) => s.id === sid);
          if (pin && Number.isFinite(pin.lat) && Number.isFinite(pin.lon)) {
            await flyToPlace(
              pin.lon,
              pin.lat,
              pin.kind === "region" ? 4.5 : Math.max(map.getZoom(), 6.5)
            );
          }
          await openDetail(sid);
          await new Promise((r) => setTimeout(r, 350));
        }
      }
    }

    // Readiness = "sources/layers can be added". MapLibre's `load` event waits
    // for the first paint, which never happens in a hidden / prerendered /
    // headless tab — gating pins on it left the map blank with the HUD stuck.
    // `styledata` needs no paint, so whichever arrives first wins.
    function markMapReady() {
      if (mapReady) return;
      try {
        ensureSources(map);
        applySky(map, basemapKind, projectionMode);
      } catch (err) {
        return; // style not parsed yet — the next event retries
      }
      mapReady = true;
      // The container may have had no layout when the map was constructed
      // (canvas would stay stuck at MapLibre's 400×300 default).
      map.resize();
      applySnapshot(null);
      if (mode === "full" && projectionMode === "globe") {
        playGlobeIntro();
      } else {
        refreshViewport(false);
      }
    }

    map.on("load", markMapReady);
    map.on("styledata", markMapReady);
    map.on("idle", () => {
      try {
        const p = map.getProjection && map.getProjection();
        const t = p && p.type;
        if (t !== "globe" && t !== "mercator") return;
        const next = t === "globe" ? "globe" : "mercator";
        if (next === projectionMode) return;
        projectionMode = next;
        writeProjection(next);
        setProjectionToggleUi();
        if (next === "globe") startSpinSoon(800);
        else stopSpin();
      } catch (_) { /* ignore */ }
    });

    map.on("moveend", debounce(() => {
      paintFromCache();
      refreshViewport(false);
    }, 450));

    map.on("click", "stations-core", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      openDetail(f.properties.id);
    });
    map.on("click", "gnss-cells-fill", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      openDetail(f.properties.id);
    });
    map.on("click", "quakes-core", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      openDetail(f.properties.id);
    });
    map.on("mouseenter", "stations-core", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "stations-core", () => { map.getCanvas().style.cursor = ""; });
    map.on("mouseenter", "gnss-cells-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "gnss-cells-fill", () => { map.getCanvas().style.cursor = ""; });

    const closeBtn = el("detail-close");
    if (closeBtn) closeBtn.addEventListener("click", closeDetail);

    function connectSSE() {
      if (es) es.close();
      es = new EventSource("/api/v1/stream");
      es.addEventListener("snapshot", (ev) => {
        try {
          applySnapshot(JSON.parse(ev.data));
          lastPushAt = Date.now();
        } catch (_) {}
      });
    }

    const btn = el("btn-refresh");
    if (btn) {
      btn.addEventListener("click", async () => {
        lastBboxKey = "";
        regionCache.clear();
        await refreshViewport(true);
      });
    }

    const openFull = el("open-full");
    if (openFull) {
      const params = new URLSearchParams(global.location.search);
      params.set("lang", currentLocale());
      openFull.href = `/?${params.toString()}`;
    }

    fetchSnapshot()
      .then((snap) => {
        applySnapshot(snap);
        if (mode === "full" && projectionMode === "globe") {
          // Hero globe intro owns the camera — do not fitBounds (it kills the wow).
          if (!introPlayed) playGlobeIntro();
          else refreshViewport(false);
          return;
        }
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
    // Fallback poll only when the SSE stream went quiet (no double fetch).
    setInterval(() => {
      if (Date.now() - lastPushAt < 40000) return;
      fetchSnapshot().then(applySnapshot).catch(() => {});
    }, 45000);

    // Keep event pins alive on a map nobody is touching.
    //
    // Event detections (fire, quake, lightning, alerts) expire from the cache
    // after EVENT_PIN_TTL_MS, but nothing refetched them: refreshViewport()
    // early-returns while the bbox key is unchanged, and the poll above only
    // refreshes the snapshot. So a stationary map quietly drained — after 15
    // minutes every fire, quake and strike was gone and its layer read "0 here",
    // under a header still counting 115,683 detections. Station pins have no TTL,
    // which is why those stayed and made it look like a fires-only outage.
    //
    // Clearing the bbox key lets the region cache (10 min, i.e. shorter than the
    // pin TTL) decide whether an actual request goes out, so this costs nothing
    // on a warm region and never touches the force budget.
    setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      lastBboxKey = "";
      refreshViewport(false);
    }, EVENT_PIN_REFRESH_MS);

    return {
      map,
      applySnapshot,
      openDetail,
      refreshViewport,
      applyActions,
      flyToPlace,
      setProjectionMode,
      getProjectionMode: () => projectionMode,
      setSurfaceMode,
      getSurfaceMode: () => surfaceMode,
      visibleStations: () => visibleStations(snapshot),
    };
  }

  global.AtlasMap = { mount };
})(window);
