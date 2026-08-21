/* ATLAS map primitives — style, geojson, layers, globe projection. */
(function (global) {
  "use strict";

  const CARTO_ATTR =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';
  const EOX_ATTR =
    '<a href="https://s2maps.eu">Sentinel-2</a> · <a href="https://eox.at">EOX</a>';

  const PROJECTION_KEY = "atlas-projection";
  const SURFACE_KEY = "atlas-globe-surface";

  function cartoTiles(kind) {
    const path = kind === "light" ? "light_all" : "dark_all";
    return [
      `https://a.basemaps.cartocdn.com/${path}/{z}/{x}/{y}@2x.png`,
      `https://b.basemaps.cartocdn.com/${path}/{z}/{x}/{y}@2x.png`,
      `https://c.basemaps.cartocdn.com/${path}/{z}/{x}/{y}@2x.png`,
    ];
  }

  function globeEarthSource() {
    return {
      type: "raster",
      tiles: [
        "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
      ],
      tileSize: 256,
      attribution: EOX_ATTR,
      maxzoom: 9,
    };
  }

  function readGlobeSurface(fallback) {
    try {
      const v = localStorage.getItem(SURFACE_KEY);
      if (v === "physical" || v === "countries") return v;
    } catch (_) { /* private */ }
    return fallback === "physical" ? "physical" : "countries";
  }

  function writeGlobeSurface(mode) {
    try {
      localStorage.setItem(SURFACE_KEY, mode === "physical" ? "physical" : "countries");
    } catch (_) { /* ignore */ }
  }

  function skyForBasemap(kind, projection) {
    const globe = projection === "globe";
    // Critical: any atmosphere-blend > 0 paints a night terminator that
    // multiplies dark CARTO tiles to near-black (looks like a broken globe).
    if (globe && kind === "light") {
      return {
        "sky-color": "#9ec9ff",
        "sky-horizon-blend": 0.45,
        "horizon-color": "#dce9f8",
        "horizon-fog-blend": 0.35,
        "fog-color": "#b8d0ea",
        "fog-ground-blend": 0.15,
        "atmosphere-blend": 0,
      };
    }
    if (globe) {
      return {
        "sky-color": "#020617",
        "sky-horizon-blend": 0.3,
        "horizon-color": "#0a2a36",
        "horizon-fog-blend": 0.4,
        "fog-color": "#020617",
        "fog-ground-blend": 0.12,
        "atmosphere-blend": 0,
      };
    }
    if (kind === "light") {
      return {
        "sky-color": "#9ec9ff",
        "sky-horizon-blend": 0.5,
        "horizon-color": "#e8f1ff",
        "horizon-fog-blend": 0.7,
        "fog-color": "#c5d9f2",
        "fog-ground-blend": 0.4,
        "atmosphere-blend": 0,
      };
    }
    return {
      "sky-color": "#020617",
      "sky-horizon-blend": 0.45,
      "horizon-color": "#0b3d4a",
      "horizon-fog-blend": 0.7,
      "fog-color": "#041018",
      "fog-ground-blend": 0.3,
      "atmosphere-blend": 0,
    };
  }

  function lightForProjection(projection, uiKind) {
    if (projection === "globe") {
      // intensity > 0 = day/night contrast; with dark basemap the night side
      // (and often most of the disc) reads as an empty black ball.
      return {
        anchor: "viewport",
        position: [1.15, 0, 30],
        intensity: 0,
        color: "#ffffff",
      };
    }
    return {
      anchor: "map",
      position: uiKind === "dark" ? [1.35, 210, 45] : [1.5, 90, 70],
      intensity: uiKind === "dark" ? 0.45 : 0.55,
    };
  }

  /** Raster paint tuned so country/city names stay legible on the globe. */
  function countriesRasterPaint(uiKind) {
    if (uiKind === "light") {
      return {
        "raster-opacity": 1,
        "raster-brightness-min": 0.02,
        "raster-brightness-max": 0.98,
        "raster-saturation": 0.08,
        "raster-contrast": 0.12,
      };
    }
    // Dark CARTO: labels are the bright pixels — never crush max, lift midtones a bit.
    return {
      "raster-opacity": 1,
      "raster-brightness-min": 0.28,
      "raster-brightness-max": 1,
      "raster-saturation": 0.35,
      "raster-contrast": 0.5,
    };
  }

  /**
   * @param {"light"|"dark"} kind UI theme basemap preference
   * @param {"globe"|"mercator"} projection
   * @param {"countries"|"physical"} [surface] globe Earth texture (default countries)
   */
  function styleForBasemap(kind, projection, surface) {
    const uiKind = kind === "light" ? "light" : "dark";
    const proj = projection === "globe" ? "globe" : "mercator";
    const globe = proj === "globe";
    const surf = surface === "physical" ? "physical" : "countries";

    if (globe) {
      // Countries follows UI theme (CARTO light/dark). Physical = Sentinel-2 option.
      const layers =
        surf === "physical"
          ? [
              {
                id: "earth-void",
                type: "background",
                paint: {
                  "background-color": uiKind === "light" ? "#0b1c28" : "#020617",
                },
              },
              {
                id: "earth-sat",
                type: "raster",
                source: "earth",
                paint: {
                  "raster-opacity": 1,
                  "raster-brightness-min": 0.04,
                  "raster-brightness-max": 0.92,
                  "raster-saturation": -0.06,
                  "raster-contrast": 0.14,
                },
              },
            ]
          : [
              {
                id: "carto-countries",
                type: "raster",
                source: "carto",
                paint: countriesRasterPaint(uiKind),
              },
            ];

      const sources =
        surf === "physical"
          ? { earth: globeEarthSource() }
          : {
              carto: {
                type: "raster",
                tiles: cartoTiles(uiKind),
                tileSize: 256,
                attribution: CARTO_ATTR,
              },
            };

      return {
        version: 8,
        projection: { type: "globe" },
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources,
        layers,
        sky: skyForBasemap(uiKind, "globe"),
        light: lightForProjection("globe", uiKind),
        metadata: { "atlas:surface": surf, "atlas:basemap": uiKind },
      };
    }

    return {
      version: 8,
      projection: { type: "mercator" },
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: {
        carto: {
          type: "raster",
          tiles: cartoTiles(uiKind),
          tileSize: 256,
          attribution: CARTO_ATTR,
        },
      },
      layers: [
        {
          id: "carto",
          type: "raster",
          source: "carto",
          paint: countriesRasterPaint(uiKind),
        },
      ],
      sky: skyForBasemap(uiKind, "mercator"),
      light: lightForProjection("mercator", uiKind),
      metadata: { "atlas:surface": "countries" },
    };
  }

  const STYLE = styleForBasemap("dark", "mercator");

  const DEFAULT_LAYERS = {
    weather: true,
    air: true,
    tide: true,
    river: true,
    marine: true,
    grid: true,
    quake: true,
    energy: true,
    fire: true,
    radiation: true,
    jamming: true,
    gnss: true,
    traffic: true,
    events: true,
    spacewx: true,
    lightning: true,
    alerts: true,
    argo: true,
    geomag: true,
    iot: true,
    flood: true,
    effis: true,
    volcano: true,
    ais: true,
    tsunami: true,
    cyclone: true,
    adsb: true,
  };

  function isUnsetEventPin(s) {
    if (s && s.cluster_parent) return true;
    const layer = s && s.layer;
    if (!(layer === "quake" || layer === "fire" || layer === "jamming" || layer === "traffic"
        || layer === "events" || layer === "spacewx" || layer === "lightning" || layer === "alerts"
        || layer === "argo" || layer === "gnss" || layer === "iot" || layer === "flood"
        || layer === "effis" || layer === "volcano" || layer === "ais" || layer === "tsunami"
        || layer === "cyclone" || layer === "adsb")) {
      return false;
    }
    return !s.parent_id && !s.has_reading && Math.abs(s.lat) < 1e-6 && Math.abs(s.lon) < 1e-6;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    if (value == null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeColor(value, fallback) {
    const fb = fallback || "#3dd6c6";
    const s = String(value == null ? "" : value).trim();
    if (!s) return fb;
    return /^(#[0-9a-f]{3,8}|rgba?\([0-9.,\s%]+\)|[a-z]{3,20})$/i.test(s) ? s : fb;
  }

  function wrapLon(lon) {
    if (lon >= -180 && lon <= 180) return lon;
    return ((((lon + 180) % 360) + 360) % 360) - 180;
  }

  function normalizeBbox(map) {
    const b = map.getBounds();
    const south = Math.max(-90, Math.min(90, b.getSouth()));
    const north = Math.max(-90, Math.min(90, b.getNorth()));
    let west = b.getWest();
    let east = b.getEast();
    if (east - west >= 360) {
      west = -180;
      east = 180;
    } else {
      west = wrapLon(west);
      east = wrapLon(east);
    }
    return {
      west,
      south: Math.min(south, north),
      east,
      north: Math.max(south, north),
    };
  }

  function debounce(fn, ms) {
    let t = null;
    return function debounced() {
      const args = arguments;
      const ctx = this;
      clearTimeout(t);
      t = setTimeout(() => fn.apply(ctx, args), ms);
    };
  }

  function readProjection(fallback) {
    try {
      const v = localStorage.getItem(PROJECTION_KEY);
      if (v === "globe" || v === "mercator") return v;
    } catch (_) { /* private */ }
    return fallback === "mercator" ? "mercator" : "globe";
  }

  function writeProjection(mode) {
    try {
      localStorage.setItem(PROJECTION_KEY, mode === "globe" ? "globe" : "mercator");
    } catch (_) { /* ignore */ }
  }

  // Blend a hex colour toward the map background so an offline tower reads as dimmed
  // while keeping its layer identity (a flat grey would lose which layer it belongs to).
  function dimColor(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!m) return "#3a4a5a";
    const v = parseInt(m[1], 16);
    const f = 0.42; // keep 42% of the hue, the rest fades to the deep-space backdrop
    const r = Math.round(((v >> 16) & 255) * f);
    const g = Math.round(((v >> 8) & 255) * f);
    const b = Math.round((v & 255) * f);
    return "#" + [r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("");
  }

  function stationFeatureProps(s) {
    const values = s && s.values && typeof s.values === "object" ? s.values : {};
    const aurora = Number(values.aurora_pct);
    const gnssScore = Number(values.degradation_score);
    const gnssState = String(s.state || (Number.isFinite(gnssScore)
      ? (gnssScore >= 75 ? "severe_degradation" : gnssScore >= 50 ? "degraded" : gnssScore >= 25 ? "mild_degradation" : "normal")
      : "unknown"));
    const layerColor = s.layer === "gnss"
      ? (gnssState === "severe_degradation" ? "#ff4d67" : gnssState === "degraded" ? "#ff7a66" : (gnssState === "mild_degradation" || gnssState === "watch") ? "#f6c453" : (gnssState === "normal" || gnssState === "nominal") ? "#34d399" : "#64748b")
      : (s.color || "#3dd6c6");
    return {
      id: s.id,
      parent_id: s.parent_id || "",
      cluster_parent: !!s.cluster_parent,
      layer: s.layer,
      label: s.label,
      place: s.place,
      headline: s.headline || "—",
      color: layerColor,
      // Precomputed dim variant for offline towers. Needed because
      // fill-extrusion-opacity cannot take a data expression, so the online/offline
      // distinction has to ride on the colour instead.
      dim_color: dimColor(layerColor),
      online: !!s.online,
      kind: s.kind || "point",
      mode: s.mode || (s.live ? "live" : "sim"),
      live: !!s.live,
      has_reading: !!s.has_reading,
      // Space-weather grid intensity drives point size while every cell stays
      // a normal clickable feature. Other layers use their default geometry.
      intensity: Number.isFinite(aurora) ? Math.max(0, Math.min(100, aurora)) : 0,
      gnss_score: Number.isFinite(gnssScore) ? Math.max(0, Math.min(100, gnssScore)) : 0,
      gnss_state: gnssState,
      height: towerHeight(s),
    };
  }

  function towerHeight(s) {
    if (s.kind === "region") return 280000;
    if (s.live) return 160000;
    if (s.mode === "sim" || s.mode === "simulated") return 90000;
    if (s.has_reading) return 110000;
    return 55000;
  }

  function stationsToGeoJSON(stations, enabled) {
    return {
      type: "FeatureCollection",
      features: (stations || [])
        .filter((s) => enabled[s.layer] !== false)
        .filter((s) => !String(s.id || "").startsWith("gnss-cell:"))
        .filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lon))
        .filter((s) => !(isUnsetEventPin(s)))
        .map((s) => ({
          type: "Feature",
          properties: stationFeatureProps(s),
          geometry: { type: "Point", coordinates: [s.lon, s.lat] },
        })),
    };
  }

  function gnssCellsToGeoJSON(stations, enabled) {
    if (enabled.gnss === false) return { type: "FeatureCollection", features: [] };
    const features = [];
    for (const s of stations || []) {
      if (!s || !String(s.id || "").startsWith("gnss-cell:")) continue;
      if (!Array.isArray(s.boundary) || s.boundary.length < 4) continue;
      const ring = s.boundary
        .filter((p) => Array.isArray(p) && p.length >= 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])))
        .map((p) => [Number(p[0]), Number(p[1])]);
      if (ring.length < 4) continue;
      if (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1]) {
        ring.push([ring[0][0], ring[0][1]]);
      }
      features.push({
        type: "Feature",
        properties: stationFeatureProps(s),
        geometry: { type: "Polygon", coordinates: [ring] },
      });
    }
    return { type: "FeatureCollection", features };
  }

  /** Small ground footprints for fill-extrusion sensor towers. */
  function stationsToTowerGeoJSON(stations, enabled) {
    const features = [];
    for (const s of stations || []) {
      if (enabled[s.layer] === false) continue;
      if (!Number.isFinite(s.lat) || !Number.isFinite(s.lon)) continue;
      if (isUnsetEventPin(s)) continue;
      const d = s.kind === "region" ? 0.22 : s.kind === "event" ? 0.12 : 0.08;
      const lon = s.lon;
      const lat = s.lat;
      features.push({
        type: "Feature",
        properties: stationFeatureProps(s),
        geometry: {
          type: "Polygon",
          coordinates: [[
            [lon - d, lat - d],
            [lon + d, lat - d],
            [lon + d, lat + d],
            [lon - d, lat + d],
            [lon - d, lat - d],
          ]],
        },
      });
    }
    return { type: "FeatureCollection", features };
  }

  function toRad(d) { return (d * Math.PI) / 180; }
  function toDeg(r) { return (r * 180) / Math.PI; }

  function greatCircleLine(a, b, steps) {
    const n = Math.max(8, steps | 0);
    const lat1 = toRad(a[1]);
    const lon1 = toRad(a[0]);
    const lat2 = toRad(b[1]);
    const lon2 = toRad(b[0]);
    const d =
      2 *
      Math.asin(
        Math.sqrt(
          Math.pow(Math.sin((lat2 - lat1) / 2), 2) +
            Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin((lon2 - lon1) / 2), 2)
        )
      );
    if (!Number.isFinite(d) || d < 1e-6) return [a, b];
    const coords = [];
    for (let i = 0; i <= n; i++) {
      const f = i / n;
      const A = Math.sin((1 - f) * d) / Math.sin(d);
      const B = Math.sin(f * d) / Math.sin(d);
      const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
      const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
      const z = A * Math.sin(lat1) + B * Math.sin(lat2);
      const lat = Math.atan2(z, Math.sqrt(x * x + y * y));
      const lon = Math.atan2(y, x);
      coords.push([toDeg(lon), toDeg(lat)]);
    }
    return coords;
  }

  function haversineKm(a, b) {
    const R = 6371;
    const dLat = toRad(b[1] - a[1]);
    const dLon = toRad(b[0] - a[0]);
    const lat1 = toRad(a[1]);
    const lat2 = toRad(b[1]);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  /** Mesh arcs between LIVE / reading sensors (capped for GPU budget). */
  function stationsToArcGeoJSON(stations, enabled) {
    const pts = (stations || [])
      .filter((s) => enabled[s.layer] !== false)
      .filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lon))
      .filter((s) => s.live || s.has_reading)
      .slice(0, 48);
    const features = [];
    const used = new Set();
    for (let i = 0; i < pts.length; i++) {
      let best = -1;
      let bestKm = 1e12;
      for (let j = 0; j < pts.length; j++) {
        if (i === j) continue;
        const key = i < j ? `${i}-${j}` : `${j}-${i}`;
        if (used.has(key)) continue;
        const km = haversineKm([pts[i].lon, pts[i].lat], [pts[j].lon, pts[j].lat]);
        if (km < 400 || km > 9000) continue;
        if (km < bestKm) {
          bestKm = km;
          best = j;
        }
      }
      if (best < 0) continue;
      const key = i < best ? `${i}-${best}` : `${best}-${i}`;
      if (used.has(key)) continue;
      used.add(key);
      const a = pts[i];
      const b = pts[best];
      features.push({
        type: "Feature",
        properties: {
          color: a.color || "#3dd6c6",
          live: !!(a.live && b.live),
        },
        geometry: {
          type: "LineString",
          coordinates: greatCircleLine([a.lon, a.lat], [b.lon, b.lat], 40),
        },
      });
      if (features.length >= 36) break;
    }
    return { type: "FeatureCollection", features };
  }

  function quakesToGeoJSON(quakes, enabled) {
    if (enabled.quake === false) {
      return { type: "FeatureCollection", features: [] };
    }
    return {
      type: "FeatureCollection",
      features: (quakes || []).map((q) => ({
        type: "Feature",
        properties: {
          id: q.id,
          magnitude: q.magnitude,
          depth_km: q.depth_km,
          at: q.at,
        },
        geometry: { type: "Point", coordinates: [q.lon, q.lat] },
      })),
    };
  }

  function inBbox(s, b) {
    if (!Number.isFinite(s.lat) || !Number.isFinite(s.lon)) return false;
    if (s.lat < b.south || s.lat > b.north) return false;
    if (b.west <= b.east) return s.lon >= b.west && s.lon <= b.east;
    return s.lon >= b.west || s.lon <= b.east;
  }

  function ensureSources(map) {
    if (!map.getSource("sensor-arcs")) {
      map.addSource("sensor-arcs", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "sensor-arcs-halo",
        type: "line",
        source: "sensor-arcs",
        paint: {
          "line-color": "#041018",
          "line-width": 4.5,
          "line-opacity": 0.55,
          "line-blur": 0.4,
        },
      });
      map.addLayer({
        id: "sensor-arcs-glow",
        type: "line",
        source: "sensor-arcs",
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#3dd6c6"],
          "line-width": 3.2,
          "line-opacity": 0.35,
          "line-blur": 1.1,
        },
      });
      map.addLayer({
        id: "sensor-arcs-core",
        type: "line",
        source: "sensor-arcs",
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#5ffbf1"],
          "line-width": [
            "case",
            ["get", "live"], 1.8,
            1.15,
          ],
          "line-opacity": [
            "case",
            ["get", "live"], 0.95,
            0.7,
          ],
        },
      });
    }

    if (!map.getSource("gnss-cells")) {
      map.addSource("gnss-cells", {
        type: "geojson",
        data: gnssCellsToGeoJSON([], DEFAULT_LAYERS),
      });
      map.addLayer({
        id: "gnss-cells-fill",
        type: "fill",
        source: "gnss-cells",
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": [
            "case",
            ["==", ["get", "gnss_state"], "unknown"], 0.055,
            ["==", ["get", "gnss_state"], "normal"], 0.08,
            ["==", ["get", "gnss_state"], "mild_degradation"], 0.13,
            ["==", ["get", "gnss_state"], "degraded"], 0.2,
            0.27,
          ],
        },
      });
      map.addLayer({
        id: "gnss-cells-outline",
        type: "line",
        source: "gnss-cells",
        paint: {
          "line-color": ["get", "color"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 0, 0.45, 7, 1.2],
          "line-opacity": [
            "case", ["==", ["get", "gnss_state"], "unknown"], 0.2, 0.72,
          ],
        },
      });
    }

    if (!map.getSource("stations")) {
      // No MapLibre clustering — paint every in-view pin from the client cache.
      map.addSource("stations", {
        type: "geojson",
        data: stationsToGeoJSON([], DEFAULT_LAYERS),
      });
      map.addLayer({
        id: "stations-glow",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, ["case", ["==", ["get", "kind"], "region"], 26, 18],
            4, ["case", ["==", ["get", "kind"], "region"], 20, 15],
            8, ["case", ["==", ["get", "kind"], "region"], 14, 11],
          ],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.38,
          "circle-blur": 0.75,
          "circle-pitch-alignment": "map",
        },
      });
      // Continuous, calm integrity field: larger translucent halos express a
      // degradation score without the attention-fatiguing blinking used by alerts.
      map.addLayer({
        id: "gnss-integrity-field",
        type: "circle",
        source: "stations",
        filter: ["==", ["get", "layer"], "gnss"],
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["get", "gnss_score"],
            0, 12, 25, 17, 50, 27, 100, 42,
          ],
          "circle-color": ["get", "color"],
          "circle-opacity": [
            "case", ["==", ["get", "gnss_state"], "unknown"], 0.08, 0.2,
          ],
          "circle-blur": 0.72,
          "circle-pitch-alignment": "map",
        },
      });
      map.addLayer({
        id: "stations-halo",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": [
            "case",
            ["==", ["get", "kind"], "region"], 11,
            ["==", ["get", "kind"], "event"], 9,
            8,
          ],
          "circle-color": "#041018",
          "circle-opacity": 0.72,
          "circle-pitch-alignment": "map",
        },
      });
      map.addLayer({
        id: "stations-core",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": [
            "case",
            ["==", ["get", "layer"], "spacewx"],
            ["interpolate", ["linear"], ["get", "intensity"], 0, 3, 100, 9],
            ["==", ["get", "layer"], "gnss"],
            ["interpolate", ["linear"], ["get", "gnss_score"], 0, 4, 100, 8],
            ["==", ["get", "kind"], "region"], 7.5,
            ["==", ["get", "kind"], "event"], 6,
            5.2,
          ],
          "circle-color": ["get", "color"],
          "circle-stroke-width": [
            "case",
            ["get", "live"], 2.8,
            ["==", ["get", "mode"], "sim"], 2.4,
            ["get", "has_reading"], 2.2,
            1.6,
          ],
          "circle-stroke-color": [
            "case",
            ["get", "live"],
            "#e8fffb",
            ["==", ["get", "mode"], "sim"],
            "#fff4d6",
            ["get", "has_reading"],
            "#ffffff",
            "rgba(255,255,255,0.75)",
          ],
          "circle-opacity": ["case", ["get", "online"], 1, 0.45],
          "circle-pitch-alignment": "map",
        },
      });
    }

    if (!map.getSource("station-towers")) {
      map.addSource("station-towers", {
        type: "geojson",
        data: stationsToTowerGeoJSON([], DEFAULT_LAYERS),
      });
      map.addLayer({
        id: "station-towers",
        type: "fill-extrusion",
        source: "station-towers",
        paint: {
          // Offline dimming lives in the COLOR, not the opacity. MapLibre rejects a data
          // expression on fill-extrusion-opacity ("data expressions not supported"), and
          // ONE invalid paint property invalidates the WHOLE layer spec — so the previous
          // ["case", ["get","online"], ...] cost us every station tower on the map, not
          // just the dimming. Colour does accept data expressions; dim_color is
          // precomputed per feature so the online/offline distinction survives.
          "fill-extrusion-color": [
            "case",
            ["get", "online"], ["get", "color"],
            ["get", "dim_color"],
          ],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.88,
          "fill-extrusion-vertical-gradient": true,
        },
      });
    }

    if (!map.getSource("quakes")) {
      map.addSource("quakes", { type: "geojson", data: quakesToGeoJSON([], DEFAULT_LAYERS) });
      map.addLayer({
        id: "quakes-pulse",
        type: "circle",
        source: "quakes",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["get", "magnitude"],
            2, 10, 5, 22, 7, 36,
          ],
          "circle-color": "#ff6b4a",
          "circle-opacity": 0.32,
          "circle-blur": 0.55,
          "circle-pitch-alignment": "map",
        },
      });
      map.addLayer({
        id: "quakes-core",
        type: "circle",
        source: "quakes",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["get", "magnitude"],
            2, 3.5, 5, 6.5, 7, 11,
          ],
          "circle-color": "#ff8f75",
          "circle-stroke-color": "#041018",
          "circle-stroke-width": 2,
          "circle-pitch-alignment": "map",
        },
      });
    }
  }

  function setSensorData(map, stations, quakes, enabled) {
    ensureSources(map);
    const st = map.getSource("stations");
    const gnssCells = map.getSource("gnss-cells");
    const tw = map.getSource("station-towers");
    const arcs = map.getSource("sensor-arcs");
    const q = map.getSource("quakes");
    if (st) st.setData(stationsToGeoJSON(stations, enabled));
    if (gnssCells) gnssCells.setData(gnssCellsToGeoJSON(stations, enabled));
    // Towers / arcs only for real catalog endpoints. Dense map objects carry a
    // parent_id (fires, Argo floats, alert cells, etc.); connecting neighbours
    // in those datasets would invent a network relationship that the source
    // never asserted.
    const catalog = (stations || []).filter(
      (s) => s && s.kind !== "event" && !s.parent_id && !String(s.id || "").startsWith("gnss-cell:")
    );
    if (tw) tw.setData(stationsToTowerGeoJSON(catalog, enabled));
    if (arcs) arcs.setData(stationsToArcGeoJSON(catalog, enabled));
    if (q) q.setData(quakesToGeoJSON(quakes, enabled));
  }

  function applySky(map, basemapKind, projection) {
    if (!map || typeof map.setSky !== "function") return;
    const ui = basemapKind === "light" ? "light" : "dark";
    const proj = projection === "globe" ? "globe" : "mercator";
    try {
      map.setSky(skyForBasemap(ui, proj));
    } catch (_) { /* older builds */ }
    try {
      if (typeof map.setLight === "function") {
        map.setLight(lightForProjection(proj, ui));
      }
    } catch (_) { /* ignore */ }
  }

  function applyProjection(map, mode, opts) {
    const globe = mode === "globe";
    const animate = !(opts && opts.animate === false);
    const hero = !!(opts && opts.hero);
    const basemap = (opts && opts.basemap) || "dark";
    try {
      if (typeof map.setProjection === "function") {
        map.setProjection({ type: globe ? "globe" : "mercator" });
      }
    } catch (_) { /* ignore */ }
    applySky(map, basemap, globe ? "globe" : "mercator");
    const target = globe
      ? {
          pitch: hero ? 56 : 48,
          zoom: hero ? 2.22 : Math.min(Math.max(map.getZoom(), 1.8), 2.4),
          duration: animate ? 1400 : 0,
        }
      : { pitch: 0, bearing: 0, duration: animate ? 900 : 0 };
    if (animate) {
      map.easeTo(target);
    } else {
      map.jumpTo({
        pitch: target.pitch || 0,
        bearing: globe ? map.getBearing() : 0,
        zoom: target.zoom != null ? target.zoom : map.getZoom(),
      });
    }
    writeProjection(globe ? "globe" : "mercator");
    try {
      document.documentElement.dataset.projection = globe ? "globe" : "mercator";
    } catch (_) { /* ignore */ }
  }

  global.AtlasMapLib = {
    STYLE,
    styleForBasemap,
    skyForBasemap,
    DEFAULT_LAYERS,
    PROJECTION_KEY,
    SURFACE_KEY,
    el,
    esc,
    safeColor,
    wrapLon,
    normalizeBbox,
    debounce,
    readProjection,
    writeProjection,
    readGlobeSurface,
    writeGlobeSurface,
    stationsToGeoJSON,
    gnssCellsToGeoJSON,
    stationsToTowerGeoJSON,
    stationsToArcGeoJSON,
    quakesToGeoJSON,
    inBbox,
    ensureSources,
    setSensorData,
    applySky,
    applyProjection,
  };
})(window);
