/* NOAA/NWS MRMS imagery. Independent of the NEXRAD station-status layer. */
(function (global) {
  "use strict";

  const ID = "noaa-radar-imagery";
  const SERVICE = "https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer";
  const LATEST = `${SERVICE}/query?f=json&where=1%3D1&outFields=idp_validtime,idp_validendtime` +
    "&orderByFields=idp_validtime+DESC&resultRecordCount=5&returnGeometry=false";
  const MAX_AGE_MS = 20 * 60 * 1000;
  const WINDOW_MS = 10 * 60 * 1000;
  const FUTURE_TOLERANCE_MS = 2 * 60 * 1000;
  const POLL_MS = 2 * 60 * 1000;

  function mount(map) {
    const toggle = document.getElementById("radar-imagery-toggle");
    const status = document.getElementById("radar-imagery-status");
    if (!toggle || !status) return;

    let frame = null;
    let appliedFrame = null;
    let pending = null;
    let refreshAt = 0;
    let interval = null;
    let clockChecked = false;
    let clock = null;

    function fresh(timestamp) {
      const now = clock ? clock.utc + (global.performance.now() - clock.monotonic) : Date.now();
      const age = now - timestamp;
      return Number.isSafeInteger(timestamp) && age <= MAX_AGE_MS && age >= -FUTURE_TOLERANCE_MS;
    }

    async function readServerClock(signal) {
      try {
        const response = await fetch("/health", { cache: "no-store", signal });
        const utc = Date.parse(response.headers.get("Date"));
        if (response.ok && Number.isFinite(utc)) return { utc, monotonic: global.performance.now() };
      } catch (_) { /* Use the browser clock when ATLAS has no usable Date header. */ }
      return null;
    }

    async function readTimestamp(signal) {
      const options = { cache: "no-cache", signal };
      try {
        const response = await fetch(LATEST, options);
        if (response.ok) {
          const catalog = await response.json();
          const times = (catalog.features || [])
            .map(({ attributes }) => attributes?.idp_validendtime ?? attributes?.idp_validtime)
            .filter(Number.isSafeInteger);
          if (times.length) return Math.max(...times);
        }
      } catch (_) { /* The service-level extent can still work if the catalog is unavailable. */ }

      const response = await fetch(`${SERVICE}?f=pjson`, options);
      if (!response.ok) throw new Error(`Radar metadata HTTP ${response.status}`);
      const metadata = await response.json();
      return metadata.timeInfo?.timeExtent?.[1];
    }

    function showStatus(message) {
      status.textContent = message ? global.AtlasI18n.t(message) : "";
    }

    function removeLayer() {
      if (map.getLayer(ID)) map.removeLayer(ID);
      if (map.getSource(ID)) map.removeSource(ID);
      appliedFrame = null;
    }

    function render() {
      if (!toggle.checked) return;
      if (!fresh(frame)) {
        removeLayer();
        showStatus(pending ? "radar.loading" : "radar.unavailable");
        return;
      }

      const source = map.getSource(ID);
      if (!source && !map.isStyleLoaded()) return;
      if (source && frame === appliedFrame) return;

      const start = frame - WINDOW_MS;
      const tiles = [
        `${SERVICE}/exportImage?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857` +
        `&size=256,256&format=png32&transparent=true&time=${start},${frame}&f=image`,
      ];
      appliedFrame = frame;
      if (source) {
        source.setTiles(tiles);
      } else {
        map.addSource(ID, {
          type: "raster", tiles, tileSize: 256, maxzoom: 9,
          bounds: [-176, 9, 150, 73],
          attribution: '<a href="https://radar.weather.gov/" target="_blank" rel="noopener">NOAA/NWS radar</a>',
        });
        const before = map.getStyle().layers.find((layer) => layer.type === "symbol" || layer.source === "stations");
        map.addLayer({
          id: ID, source: ID, type: "raster",
          paint: { "raster-opacity": 0.75, "raster-fade-duration": 0 },
        }, before?.id);
      }
      const utcTime = (value) => new Date(value).toISOString().slice(11, 16);
      status.textContent = `${utcTime(start)}–${utcTime(frame)} UTC`;
    }

    async function refresh() {
      const now = global.performance.now();
      if (!toggle.checked || document.hidden || pending || now < refreshAt) return;
      const request = new AbortController();
      pending = request;
      refreshAt = now + POLL_MS;
      render();
      const timeout = global.setTimeout(() => request.abort(), 8000);
      try {
        const [timestamp, serverClock] = await Promise.all([
          readTimestamp(request.signal),
          clockChecked ? clock : readServerClock(request.signal),
        ]);
        if (pending !== request) return;
        clock = serverClock;
        clockChecked = true;
        if (fresh(timestamp) && (frame === null || timestamp > frame)) {
          frame = timestamp;
        }
      } catch (_) {
        // Keep the last verified frame only until its freshness window expires.
      } finally {
        global.clearTimeout(timeout);
        if (pending === request) {
          pending = null;
          render();
        }
      }
    }

    function tick() {
      render();
      refresh();
    }

    toggle.addEventListener("change", () => {
      toggle.closest(".layer").classList.toggle("active", toggle.checked);
      if (toggle.checked) {
        tick();
        interval = global.setInterval(tick, 30 * 1000);
        return;
      }
      global.clearInterval(interval);
      pending?.abort();
      pending = null;
      refreshAt = 0;
      removeLayer();
      showStatus("");
    });
    map.on("idle", render);
    document.addEventListener("visibilitychange", tick);
  }

  global.AtlasRadarImagery = { mount };
})(window);
