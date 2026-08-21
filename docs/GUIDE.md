# ATLAS — operator & developer guide

**Languages:** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)

ATLAS is the ecosystem **physical sensor map**: live weather, air quality, tides, rivers, marine, UK grid carbon, earthquakes, wildfire, radiation, GNSS jamming, NASA EONET events, NOAA space weather, GOES lightning, NWS alerts, Argo floats, USGS geomag, floods, Copernicus EFFIS, volcanoes, public AIS (Finland / Norway), NWS/PTWC tsunami CAP, NHC tropical cyclones, public ADS-B, and optional own-edge ADS-B/AIS/IoT traffic — all plotted from [GAIA](https://iot.modelmarket.dev) relays. **New open-data devices live on GAIA; their map layers, pins, and watchboxes are ATLAS surfaces** (not a separate GAIA product UI). It appears as the **ATLAS** node on [Alien Monitor](https://magic-ai-factory.com/monitor/) (mini-map embed + full-map link) and ships with **ATLAS Analyst** (DeepSeek by default) — grounded on the live fleet snapshot, auto-discovered ATLAS SURFACES, a **live Hub federation** capability slice, and an embedded **AICOM / AIMarket ecosystem brief**, with mandatory **cross-layer** reasoning when evidence spans layers. Terminology: [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md) (EN · RU · ES · FR · ZH).

**Add a sensor / pin:** [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH) — Open-Meteo **mesh** city YAML + new LIVE **relay** checklist. GAIA device catalog / licenses: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). **Operator use cases** (map + ATLAS Analyst, live vs proposed vs hold): [`OPERATOR-USE-CASES.md`](OPERATOR-USE-CASES.md) (EN · RU · ES · FR · ZH).

## Surfaces

| URL | Role |
|-----|------|
| `/` | Full MapLibre map + layers + in-view list + AI |
| `/embed` | Compact map for Alien Monitor iframe |
| `/health` | Liveness JSON |
| `/api/v1/*` | Snapshot, viewport, station detail, SSE, **watchboxes** |
| `/api/ai/*` | Providers + grounded analyst chat |

## Architecture (load model)

```
Browser ──► ATLAS (single uvicorn worker)
              │
              ├─ fleet poll (cheap) ──► GAIA gaia.fleet.status@v1
              ├─ viewport / click ────► GAIA device reads (TTL cache + single-flight)
              └─ AI ask ──────────────► DeepSeek (+ LIVE snapshot in system prompt)
```

| Mechanism | Behaviour |
|-----------|-----------|
| Fleet poll | Pins only — no stampede of per-device invokes |
| `POST /api/v1/viewport` | Refresh readings for sensors **inside the visible bbox** |
| `GET /api/v1/stations/{id}` | Human-readable card; refresh if older than detail TTL |
| Reading TTL | Default **45s** shared cache |
| Prefetch | Viewport loads **visible** first; padded neighbors + rest of catalog warm in background |
| Analyst context | Full cached fleet (not only visible bbox) + ecosystem brief only |
| Map actions | Analyst can **flyTo** places and **open** station panels (`actions[]` on `/api/ai/ask`) |
| Detail freshness | Click refreshes if older than **20s** |
| Single-flight | Concurrent clients for the same `device_id` share one GAIA call |
| SSE | Fleet snapshot fan-out to browsers (poll only as fallback) |
| Rate limit | In-app soft IP limit + nginx edge |
| Cache bypass | `force` / `fresh` / `POST /api/v1/refresh` have their own tight per-IP budget (429 when spent) — they multiply into GAIA invokes |
| AI budget | `POST /api/ai/*` has a separate per-IP budget (LLM calls cost money) |
| Viewport contract | bbox must be lat ±90 / lon ±180; the map client wraps MapLibre bounds before sending (world spans collapse to −180/180) |

Buyers **cannot** pass lat/lon into GAIA invoke — anchors are operator env on GAIA. ATLAS maps documented defaults; quake events carry real lat/lon in the reading.

## Layers & stations

**~80 pins / 24 layers**: named anchors (incl. open-data + edge feeders) + a
20-city Open-Meteo mesh (weather + air per city, ids `om-wx-{slug}` /
`om-aq-{slug}` — kept in sync with `gaia/gaia/devices/om_mesh.py`).

GAIA sells the **readings** (`gaia.*.read@v1`). ATLAS is where those devices
appear as **map layers / pins** and where **watchboxes** run.

| Layer | Devices | Notes |
|-------|---------|-------|
| Weather | `om-wx-01`, `nws-01`, `om-wx-{slug}` ×20, `ws-01`, `ws-02` | Berlin Open-Meteo · NYC NWS · city mesh · 2 sims |
| Air | `om-aq-01`, `osm-01`, `sta-01`, `om-aq-{slug}` ×20, `aq-01` | PM / CO₂ / senseBox · city mesh · 1 sim |
| Tide | `noaa-tide-01` | Battery, NYC gauge |
| River | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS NWIS Potomac · ECCC Humber (End-use Licence) · SMHI Abisko (CC BY 4.0) |
| Marine | `ndbc-01`, `om-marine-01` | NDBC NY Bight buoy · Open-Meteo NYC Harbor |
| Grid | `uk-grid-01` | UK carbon intensity (region) |
| Quake | `usgs-quake-01`, `geonet-01`, `emsc-01` | USGS · GeoNet NZ · EMSC FDSN (CC BY 4.0 — cite EMSC; not a USGS replacement) |
| Energy | `em-01` | Household meter simulator (no public API) |
| Fire | `firms-fire-01` | NASA FIRMS VIIRS — cite NASA FIRMS · map expands `hotspots[]` into many Wildfire pins (`firms-hs-*`); toggle other layers off to focus |
| Radiation | `safecast-01` + city anchors | Safecast **CC0** · Hub SKU = 30-day CPM; Melbourne/Adelaide archive so 2014 AU drive-grids stay on the map (`captured_at`) |
| Jamming | `cybernews-jam-01` | CyberNews GNSS — **CC BY 4.0** · event lat/lon |
| Traffic | `feeder-adsb-01`, `feeder-ais-01` | Own-edge ingest on GAIA (`GAIA_FEEDER_*`); offline until push |
| Public AIS | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic (CC BY 4.0, Finnish waters) · Kystverket/BarentsWatch (NLOD, Norwegian waters, token). **Not** one Europe blob; **not** own-edge `gaia.ais.read@v1` |
| Public ADS-B | `adsb-lol-01` | ADSB.lol ODbL 1.0 area query (default LHR). **Not** own-edge `gaia.adsb.read@v1`, not OpenSky/ADSBx |
| Natural events | `eonet-01` | NASA EONET — cite NASA EONET · map expands hotspots |
| Space weather | `swpc-01` | NOAA SWPC Kp (Boulder) + OVATION aurora cells |
| Lightning | `glm-01` | GOES-19/18 GLM via NOAA NODD (not Blitzortung) |
| Weather alerts | `nws-alerts-01` | NWS CAP centroids |
| Argo | `argo-01` → `argo-wmo-{WMO}` | Official GDAC active-float network (30-day rule); click a WMO for its latest QC-gated profile — cite DOI 10.17882/42182 |
| Geomag | `usgs-geomag-01`, `usgs-geomag-*` | All 14 official USGS observatories as separate LIVE pins; total field F (nT), source coordinates, observation age — not INTERMAGNET |
| Edge IoT | `feeder-iot-01` | Own Tasmota/TTN/SenML ingest |
| Flood | `nws-flood-01`, `ea-flood-01` | NWS CAP US · EA OGL England only (not SEPA/NRW; GloFAS WMS not scraped) |
| EFFIS | `effis-01` | Copernicus EFFIS current fires — CC BY 4.0 |
| Volcanoes | `usgs-volcano-01` | USGS elevated volcanoes |
| Tsunami alerts | `nws-tsunami-01`, `ptwc-01` | NWS CAP US · PTWC Atom Pacific — often empty; not a tide gauge; empty ≠ all-clear |
| Tropical cyclones | `nhc-cyclone-01` | NHC/CPHC CurrentStorms (U.S. PD) — Atlantic + EPac + CPac; not JTWC; empty season → offline |

Mesh cities: Ottawa · New Delhi · Tokyo · Sydney · São Paulo · Lagos · Cairo ·
Cape Town · Singapore · Dubai · Los Angeles · Mexico City · Moscow · Paris ·
Reykjavík · Anchorage · Buenos Aires · Jakarta · Nairobi · Vancouver.

## HTTP API

### `GET /api/v1/snapshot`

Pins + any cached headlines / values.

### `POST /api/v1/viewport`

```json
{ "west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7, "force": false }
```

Returns `requested`, `cache_hits`, `stations`, and a full `snapshot`.

### `GET /api/v1/stations/{device_id}?fresh=0`

Human-readable detail: `title`, `summary`, `metrics[]` (`label` / `value` / `hint`), `status_line`.

### `GET /api/v1/stream`

SSE `event: snapshot` fan-out.

### Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

A **watchbox** is a saved geographic “watch frame”: a bbox (west/south/east/north)
plus a filter of map layers. Think “alert me when something LIVE appears in this
rectangle on these layers” — not a GAIA device read.

- **Subscribe** (`atlas.watchbox.subscribe@v1` / REST) — create/list/unsubscribe the
  saved frame. Free plumbing; not the billable Hub SKU.
- **Check** (`atlas.watchbox.check@v1`) — evaluate the frame against the current
  fleet snapshot; returns matches + a content receipt. This is the Hub-billable
  product (also callable with an ephemeral bbox + layers, no saved id).

Only **free-to-commercialize** catalog layers (`ALLOWED_WATCHBOX_LAYERS`). NC feeds
are not on ATLAS at all.

**Ownership.** The registry is not public. Every watchbox gets an **owner token**,
returned exactly once in the create response (like `webhook_secret`) and stored only as
a SHA-256 digest — list/get never echo it and it cannot be recovered later. Send it as
`X-Atlas-Watchbox-Token: <token>` (or `Authorization: Bearer <token>`); the operator
token `X-Atlas-Token` works everywhere the owner token does. Anonymous callers get
`401`; a wrong token gets the same `404` as an id that never existed, so the registry
cannot be enumerated.

Creation is operator-only unless `ATLAS_WATCHBOX_OPEN_SIGNUP=1` enables self-serve
(bounded by `ATLAS_WATCHBOX_SELF_SERVE_MAX`, default 200 live boxes).

| Method | Path | Who |
|--------|------|-----|
| `GET` | `/api/v1/watchboxes` | owner (own boxes only) or operator (all) |
| `POST` | `/api/v1/watchboxes` | operator, or anyone when self-serve is on |
| `GET` / `DELETE` | `/api/v1/watchboxes/{id}` | owner or operator |
| `GET` | `/api/v1/watchboxes/{id}/log` | owner or operator |
| `POST` | `/api/v1/watchboxes/{id}/check` | owner or operator |

**`DELETE` is an unsubscribe, not a purge.** Monitoring stops; the registry row and the
signed monitor log stay readable with the owner token. Dropping the row would orphan the
log — the checks would still be in SQLite but `…/log` resolves the registry first, so
the evidence would be unreachable while the delete reported success. `?purge=true`
destroys the row and is operator-only.

```bash
# create — save the owner_token from this response, it is shown once
curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes \
  -H 'Content-Type: application/json' -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" \
  -d '{"west":-10,"south":35,"east":40,"north":60,"layers":["fire","jamming"],"label":"EU hazards"}'

curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes/<id>/check \
  -H "X-Atlas-Watchbox-Token: $OWNER_TOKEN"

# the monitoring evidence — still readable after unsubscribing
curl -s https://atlas.modelmarket.dev/api/v1/watchboxes/<id>/log \
  -H "X-Atlas-Watchbox-Token: $OWNER_TOKEN"
```

Through the Hub the token travels in the invoke body, since the hub forwards the input
rather than our headers — `{"capability_id":"atlas.watchbox.check@v1","input":
{"watchbox_id":"<id>","owner_token":"<token>"}}`. Ephemeral bbox+layers checks need no
token.

### Composite products (ATLAS &gt; parts)

| SKU | What it does | Convenience | Hub invoke |
|-----|--------------|-------------|------------|
| `atlas.situation.brief@v1` | Cross-layer scored brief for a bbox — defaults include flood, EFFIS, lightning, volcano, alerts, events, public AIS, tsunami (not spacewx/geomag/argo); refuse if empty | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS **and/or** Copernicus EFFIS in bbox + nearest LIVE weather (two lists, dual attribution; not a forecast) | `POST /api/v1/products/fire-weather` | same |
| `atlas.nearest.read@v1` | Nearest LIVE pin to buyer `lat`/`lon` (layer filter, `max_km`, receipt) | `POST /api/v1/products/nearest` | same |
| `atlas.point.read@v1` | Exact clickable `point_id` → values, provenance, parent GAIA rail, signed ATLAS receipt | `POST /api/v1/products/point` | same |
| `atlas.watchbox.check@v1` | Evaluate saved or ephemeral watchbox → matches + receipt | watchbox `…/check` | same |

Hub UI blurbs (EN · RU · ES · FR · ZH): `aimarket-hub/cap-descriptions-i18n.json`.

```bash
curl -s https://atlas.modelmarket.dev/.well-known/ai-market.json
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/fire-weather \
  -H 'Content-Type: application/json' \
  -d '{"west":-125,"south":32,"east":-114,"north":42,"limit":24}'
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/nearest \
  -H 'Content-Type: application/json' \
  -d '{"lat":52.52,"lon":13.41,"layer":"weather"}'
curl -s -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.point.read@v1","input":{"point_id":"argo-wmo-1901760","fresh":true}}'
```

Fail-closed when the bbox has no LIVE readings — never pad with SIM. Fire product
requires NASA FIRMS attribution. **Nearest** takes buyer `lat`/`lon` (ATLAS map
index); GAIA device reads stay `device_id`-anchored.
Every interactive sensor/event/observation exposes the same exact `point_id` to
the UI and agents. Catalog sensors and Argo WMO platforms refresh directly;
dense event pixels are selected from the latest parent snapshot and state that
evidence boundary in the response rather than pretending the upstream accepts
an individual-pixel query.

### `GET /api/ai/providers`

Default: `deepseek_api` / `deepseek-v4-pro`.

### `POST /api/ai/ask`

```json
{
  "question": "Write a situation report for sensors in view",
  "locale": "en",
  "report": true,
  "bbox": { "west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7 }
}
```

Server injects the LIVE ATLAS snapshot into the system prompt (clients cannot forge numbers). Optional `station_ids`, `provider`, `model_role` (`heavy`|`light`).

With **no** provider configured (no cloud key and `ATLAS_LOCAL_LLM_ENABLED` off) an offline stub answers from the reading cache instead of failing. Local backends (Ollama / LM Studio) only count as available behind that opt-in — otherwise a keyless server would "have" a provider it cannot reach.

**Auto-learning:** ATLAS Analyst builds `ATLAS SURFACES` + `snapshot.capabilities` from `STATION_CATALOG` / `LAYER_META` / watchboxes (`atlas/atlas/capability_awareness.py`). Adding a mirrored GAIA device to the catalog is enough — no hard-coded prompt edit per SKU. Topic-scope markers are derived the same way.

## Alien Monitor

Hardwired node `atlas` (`group: physical`):

- Poll: `ALIEN_ATLAS_URL` → `/health` + `/api/v1/monitor`
- Panel: stations + iframe `/embed` + **Open full map**
- Env: `ALIEN_PUBLIC_ATLAS_URL` (default `https://atlas.modelmarket.dev`)

## Deploy

```bash
# PyPI package (map UI bundled in the wheel)
pip install aimarket-atlas
export ATLAS_GAIA_URL=https://iot.modelmarket.dev
atlas --host 127.0.0.1 --port 9330

# local Docker
docker compose -f atlas/docker-compose.local.yml up -d --build
# → http://127.0.0.1:9330/

# production (ecosystem network + nginx)
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
# nginx: deploy/nginx/atlas.modelmarket.dev.conf
# or: sudo ./scripts/deploy_atlas.sh
```

Loopback bind `127.0.0.1:9330` — TLS only via nginx.

## Environment (`ATLAS_` prefix + LLM)

All ATLAS settings carry the `ATLAS_` prefix (`ATLAS_PUBLIC_URL`, …); provider
API keys use their vendor names (`DEEPSEEK_API_KEY`, …).

| Variable | Default | Purpose |
|----------|---------|---------|
| `ATLAS_PUBLIC_URL` | `https://atlas.modelmarket.dev` | Links in monitor payload |
| `ATLAS_GAIA_URL` | `https://iot.modelmarket.dev` | Upstream gateway |
| `ATLAS_HUB_URL` | `https://modelmarket.dev` | Live federation catalog for Analyst |
| `ATLAS_FEDERATION_CACHE_TTL_S` | `120` | Hub manifest/peers cache |
| `ATLAS_ANALYST_FIRE_PIN_LIMIT` | `24` | Max FIRMS hotspots in Analyst prompt (map keeps all) |
| `ATLAS_FLEET_POLL_INTERVAL_S` | `30` | Pin/fleet cadence |
| `ATLAS_READING_TTL_S` | `45` | Reading cache TTL |
| `ATLAS_VIEWPORT_PAD_DEG` | `25` | Lazy neighbor prefetch pad (degrees) |
| `ATLAS_WARM_ALL_ON_FLEET` | `true` | Background-warm full catalog after fleet poll |
| `ATLAS_ANALYST_WARM_ALL` | `true` | Analyst gets full cached fleet, not only bbox |
| `ATLAS_DETAIL_FRESH_S` | `20` | Click refresh threshold |
| `ATLAS_RATE_LIMIT_PER_MIN` | `180` | Soft per-IP limit (all `/api/*`) |
| `ATLAS_RATE_LIMIT_AI_PER_MIN` | `12` | Per-IP budget for `POST /api/ai/*` |
| `ATLAS_RATE_LIMIT_FORCE_PER_MIN` | `6` | Per-IP budget for `force` / `fresh` / `/refresh` |
| `ATLAS_OPERATOR_TOKEN` | — | When set, `X-ATLAS-Token` holders skip the cache-bypass budget |
| `ATLAS_TRUSTED_PROXY_HOPS` | `1` | Proxies in front of ATLAS. The budget key comes from `X-Real-IP` (nginx overwrites it), else this far from the **right** of `X-Forwarded-For`; `0` ignores both headers (no proxy) |
| `ATLAS_MONITOR_STATION_LIMIT` | `24` | Stations in the Alien Monitor payload (ranked) |
| `ATLAS_GAIA_CONCURRENCY` | `4` | Parallel GAIA invokes |
| `ATLAS_LOCAL_LLM_ENABLED` | `false` | Count Ollama / LM Studio as available providers |
| `ATLAS_LLM_MAX_RETRIES` | `3` | LLM retries on 429/5xx/timeout |
| `DEEPSEEK_API_KEY` | — | **Production LLM key** |
| `ATLAS_LLM_PROVIDER` | `deepseek_api` | Default provider |
| `ATLAS_LLM_MODEL` | `deepseek-v4-pro` | Heavy model |
| `ATLAS_LLM_MODEL_LIGHT` | `deepseek-v4-flash` | Light model |
| `ATLAS_LLM_CONFIG` | `/app/config/model_providers.yaml` | Optional YAML |

## Tests

```bash
cd atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

**101 tests.** Coverage areas: formatters, catalog/bbox + viewport normalization,
aggregator cache & single-flight, HTTP API + edge guards (cache-bypass / AI
budgets, operator token), map actions & place aliases, prompt firewall, AI
grounding / DeepSeek defaults / offline stub. **No live GAIA** required —
invokes are mocked.

## Honesty & attribution

- ATLAS is a **map + analyst + watchboxes** over GAIA relays; it does not own sensors.
- Open-Meteo: CC BY 4.0 · NWS / USGS / NOAA: U.S. Government public domain · UK Carbon Intensity: National Grid ESO open data · FIRMS: cite NASA · Safecast: CC0 · CyberNews GNSS: CC BY 4.0.
- Live keys on GAIA prove **relay custody**, not hardware ownership.
- Edge traffic pins stay offline until **your** feeder pushes — never third-party NC aggregators.
