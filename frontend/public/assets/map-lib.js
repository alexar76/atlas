/* ATLAS map primitives — style, geojson, layer sources. */
(function (global) {
  "use strict";

  const STYLE = {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      carto: {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      },
    },
    layers: [{ id: "carto", type: "raster", source: "carto" }],
  };

  const DEFAULT_LAYERS = {
    weather: true,
    air: true,
    tide: true,
    grid: true,
    quake: true,
  };

  function el(id) {
    return document.getElementById(id);
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

  function stationsToGeoJSON(stations, enabled) {
    return {
      type: "FeatureCollection",
      features: (stations || [])
        .filter((s) => enabled[s.layer] !== false)
        .filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lon))
        .filter((s) => !(s.layer === "quake" && Math.abs(s.lat) < 1e-6 && Math.abs(s.lon) < 1e-6))
        .map((s) => ({
          type: "Feature",
          properties: {
            id: s.id,
            layer: s.layer,
            label: s.label,
            place: s.place,
            headline: s.headline || "—",
            color: s.color || "#3dd6c6",
            online: !!s.online,
            kind: s.kind || "point",
            has_reading: !!s.has_reading,
          },
          geometry: { type: "Point", coordinates: [s.lon, s.lat] },
        })),
    };
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
    if (!map.getSource("stations")) {
      map.addSource("stations", { type: "geojson", data: stationsToGeoJSON([], DEFAULT_LAYERS) });
      map.addLayer({
        id: "stations-glow",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": ["case", ["==", ["get", "kind"], "region"], 18, 14],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.18,
          "circle-blur": 0.7,
        },
      });
      map.addLayer({
        id: "stations-core",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": [
            "case",
            ["==", ["get", "kind"], "region"], 9,
            ["==", ["get", "kind"], "event"], 7,
            6,
          ],
          "circle-color": ["get", "color"],
          "circle-stroke-width": ["case", ["get", "has_reading"], 2, 1],
          "circle-stroke-color": [
            "case",
            ["get", "has_reading"],
            "rgba(255,255,255,0.85)",
            "rgba(255,255,255,0.4)",
          ],
          "circle-opacity": ["case", ["get", "online"], 0.95, 0.35],
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
            2, 8, 5, 18, 7, 32,
          ],
          "circle-color": "#ff6b4a",
          "circle-opacity": 0.22,
          "circle-blur": 0.6,
        },
      });
      map.addLayer({
        id: "quakes-core",
        type: "circle",
        source: "quakes",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["get", "magnitude"],
            2, 3, 5, 6, 7, 10,
          ],
          "circle-color": "#ff8f75",
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1,
        },
      });
    }
  }

  global.AtlasMapLib = {
    STYLE,
    DEFAULT_LAYERS,
    el,
    debounce,
    stationsToGeoJSON,
    quakesToGeoJSON,
    inBbox,
    ensureSources,
  };
})(window);
