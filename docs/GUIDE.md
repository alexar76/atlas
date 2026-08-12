# ATLAS — operator & developer guide

**Languages:** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)

ATLAS is the ecosystem **physical sensor map**: live weather, air quality, tides, rivers, marine, UK grid carbon, earthquakes, wildfire, radiation, GNSS jamming, and optional own-edge ADS-B/AIS traffic — all plotted from [GAIA](https://iot.modelmarket.dev) relays. **New open-data devices live on GAIA; their map layers, pins, and watchboxes are ATLAS surfaces** (not a separate GAIA product UI). It appears as the **ATLAS** node on [Alien Monitor](https://magic-ai-factory.com/monitor/) (mini-map embed + full-map link) and ships with **ATLAS Analyst** (DeepSeek by default) — grounded on the live fleet snapshot, auto-discovered ATLAS SURFACES, a **live Hub federation** capability slice, and an embedded **AICOM / AIMarket ecosystem brief**, with mandatory **cross-layer** reasoning when evidence spans layers. Terminology: [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md) (EN · RU · ES · FR · ZH).

**Add a sensor / pin:** [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH) — Open-Meteo **mesh** city YAML + new LIVE **relay** checklist. GAIA device catalog / licenses: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md).

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

**~60 pins / 12 layers**: named anchors (incl. open-data + edge feeders) + a
20-city Open-Meteo mesh (weather + air per city, ids `om-wx-{slug}` /
`om-aq-{slug}` — kept in sync with `gaia/gaia/devices/om_mesh.py`).

GAIA sells the **readings** (`gaia.*.read@v1`). ATLAS is where those devices
appear as **map layers / pins** and where **watchboxes** run.

| Layer | Devices | Notes |
|-------|---------|-------|
| Weather | `om-wx-01`, `nws-01`, `om-wx-{slug}` ×20, `ws-01`, `ws-02` | Berlin Open-Meteo · NYC NWS · city mesh · 2 sims |
| Air | `om-aq-01`, `osm-01`, `sta-01`, `om-aq-{slug}` ×20, `aq-01` | PM / CO₂ / senseBox · city mesh · 1 sim |
| Tide | `noaa-tide-01` | Battery, NYC gauge |
| River | `usgs-river-01` | USGS NWIS Potomac at Little Falls |
| Marine | `ndbc-01`, `om-marine-01` | NDBC NY Bight buoy · Open-Meteo NYC Harbor |
| Grid | `uk-grid-01` | UK carbon intensity (region) |
| Quake | `usgs-quake-01` | Event lat/lon in values |
| Energy | `em-01` | Household meter simulator (no public API) |
| Fire | `firms-fire-01` | NASA FIRMS VIIRS — cite NASA FIRMS · map expands `hotspots[]` into many Wildfire pins (`firms-hs-*`); toggle other layers off to focus |
| Radiation | `safecast-01` | Safecast measurements — **CC0** |
| Jamming | `cybernews-jam-01` | CyberNews GNSS — **CC BY 4.0** · event lat/lon |
| Traffic | `feeder-adsb-01`, `feeder-ais-01` | Own-edge ingest on GAIA (`GAIA_FEEDER_*`); offline until push |

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

- **Subscribe** (`atlas.watchbox.subscribe@v1` / REST) — create/list/delete the
  saved frame. Free plumbing; not the billable Hub SKU.
- **Check** (`atlas.watchbox.check@v1`) — evaluate the frame against the current
  fleet snapshot; returns matches + a content receipt. This is the Hub-billable
  product (also callable with an ephemeral bbox + layers, no saved id).

Only **free-to-commercialize** catalog layers (`ALLOWED_WATCHBOX_LAYERS`). NC feeds
are not on ATLAS at all.

| Method | Path |
|--------|------|
| `GET` / `POST` | `/api/v1/watchboxes` |
| `GET` / `DELETE` | `/api/v1/watchboxes/{id}` |
| `POST` | `/api/v1/watchboxes/{id}/check` |

```bash
curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes \
  -H 'Content-Type: application/json' \
  -d '{"west":-10,"south":35,"east":40,"north":60,"layers":["fire","jamming"],"label":"EU hazards"}'

curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes/<id>/check
```

### Composite products (ATLAS &gt; parts)

| SKU | What it does | Convenience | Hub invoke |
|-----|--------------|-------------|------------|
| `atlas.situation.brief@v1` | Cross-layer scored brief for a bbox — drivers + cited LIVE pins; refuse if empty | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS hotspots in bbox + nearest LIVE weather context (cite NASA) | `POST /api/v1/products/fire-weather` | same |
| `atlas.nearest.read@v1` | Nearest LIVE pin to buyer `lat`/`lon` (layer filter, `max_km`, receipt) | `POST /api/v1/products/nearest` | same |
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
```

Fail-closed when the bbox has no LIVE readings — never pad with SIM. Fire product
requires NASA FIRMS attribution. **Nearest** takes buyer `lat`/`lon` (ATLAS map
index); GAIA device reads stay `device_id`-anchored.

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
