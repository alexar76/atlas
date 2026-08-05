# ATLAS — operator & developer guide

**Languages:** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)

ATLAS is the ecosystem **physical sensor map**: live weather, air quality, tides, UK grid carbon, and earthquakes plotted from [GAIA](https://iot.modelmarket.dev) relays. It appears as the **ATLAS** node on [Alien Monitor](https://magic-ai-factory.com/monitor/) (mini-map embed + full-map link) and ships with **ATLAS Analyst** (DeepSeek by default).

## Surfaces

| URL | Role |
|-----|------|
| `/` | Full MapLibre map + layers + in-view list + AI |
| `/embed` | Compact map for Alien Monitor iframe |
| `/health` | Liveness JSON |
| `/api/v1/*` | Snapshot, viewport, station detail, SSE |
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
| Detail freshness | Click refreshes if older than **20s** |
| Single-flight | Concurrent clients for the same `device_id` share one GAIA call |
| SSE | Fleet snapshot fan-out to browsers |
| Rate limit | In-app soft IP limit + nginx edge |

Buyers **cannot** pass lat/lon into GAIA invoke — anchors are operator env on GAIA. ATLAS maps documented defaults; quake events carry real lat/lon in the reading.

## Layers & stations

| Layer | Devices (typical) | Notes |
|-------|-------------------|-------|
| Weather | `om-wx-01`, `nws-01` | Berlin Open-Meteo · NYC NWS |
| Air | `om-aq-01`, `osm-01`, `sta-01` | PM / CO₂ / senseBox |
| Tide | `noaa-tide-01` | Battery, NYC gauge |
| Grid | `uk-grid-01` | UK carbon intensity (region) |
| Quake | `usgs-quake-01` | Event lat/lon in values |

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

Server injects the LIVE ATLAS snapshot into the system prompt (clients cannot forge numbers). Optional `station_ids`, `provider`, `model_role` (`heavy`|`light`). Without `DEEPSEEK_API_KEY`, an offline stub answers from cache.

## Alien Monitor

Hardwired node `atlas` (`group: physical`):

- Poll: `ALIEN_ATLAS_URL` → `/health` + `/api/v1/monitor`
- Panel: stations + iframe `/embed` + **Open full map**
- Env: `ALIEN_PUBLIC_ATLAS_URL` (default `https://atlas.modelmarket.dev`)

## Deploy

```bash
# local
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

| Variable | Default | Purpose |
|----------|---------|---------|
| `PUBLIC_URL` | `http://127.0.0.1:9330` | Links in monitor payload |
| `GAIA_URL` | `https://iot.modelmarket.dev` | Upstream gateway |
| `FLEET_POLL_INTERVAL_S` | `30` | Pin/fleet cadence |
| `READING_TTL_S` | `45` | Reading cache TTL |
| `DETAIL_FRESH_S` | `20` | Click refresh threshold |
| `RATE_LIMIT_PER_MIN` | `180` | Soft per-IP limit |
| `GAIA_CONCURRENCY` | `4` | Parallel GAIA invokes |
| `DEEPSEEK_API_KEY` | — | **Production LLM key** |
| `LLM_PROVIDER` | `deepseek_api` | Default provider |
| `LLM_MODEL` | `deepseek-v4-pro` | Heavy model |
| `LLM_MODEL_LIGHT` | `deepseek-v4-flash` | Light model |
| `LLM_CONFIG` | `/app/config/model_providers.yaml` | Optional YAML |

## Tests

```bash
cd atlas
python -m venv backend/.venv && source backend/.venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

Coverage areas: formatters, catalog/bbox, aggregator cache & single-flight, HTTP API, AI grounding / DeepSeek defaults / offline stub. **No live GAIA** required — invokes are mocked.

## Honesty & attribution

- ATLAS is a **map + analyst** over GAIA relays; it does not own sensors.
- Open-Meteo: CC BY 4.0 · NWS / USGS / NOAA: U.S. Government public domain · UK Carbon Intensity: National Grid ESO open data.
- Live keys on GAIA prove **relay custody**, not hardware ownership.
