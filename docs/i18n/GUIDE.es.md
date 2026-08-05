# ATLAS — guía de operador y desarrollador

**Idiomas:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS es el **mapa de sensores físicos** del ecosistema: clima, aire, mareas, carbono de la red británica y terremotos sobre los relays de [GAIA](https://iot.modelmarket.dev). Aparece como nodo **ATLAS** en [Alien Monitor](https://magic-ai-factory.com/monitor/) (mini-mapa + enlace al mapa completo) e incluye **ATLAS Analyst** (DeepSeek por defecto).

## Superficies

| URL | Rol |
|-----|-----|
| `/` | Mapa MapLibre completo + capas + lista «en vista» + AI |
| `/embed` | Mapa compacto para iframe del Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, ficha de estación, SSE |
| `/api/ai/*` | Proveedores + chat anclado a datos en vivo |

## Modelo de carga

- Fondo: solo **fleet** barato (pines), sin lecturas masivas.
- `POST /api/v1/viewport` — lecturas **solo en el bbox visible**, caché TTL (~45 s), single-flight.
- Clic → `GET /api/v1/stations/{id}` — ficha legible (refresco si > ~20 s).
- AI: el servidor inyecta el LIVE SNAPSHOT (el cliente no puede falsificar cifras).

El comprador **no** envía lat/lon al invoke de GAIA — los anclajes los define el operador. Los terremotos traen coordenadas en el reading.

## Capas

| Capa | device_id típicos |
|------|-------------------|
| Clima | `om-wx-01`, `nws-01` |
| Aire | `om-aq-01`, `osm-01`, `sta-01` |
| Marea | `noaa-tide-01` |
| Red | `uk-grid-01` (región) |
| Sismos | `usgs-quake-01` |

## API (resumen)

- `GET /api/v1/snapshot` — pines + caché
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — análisis e **informe de situación** (`report: true`)

LLM de producción: **`DEEPSEEK_API_KEY`**, modelo `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (por defecto `https://atlas.modelmarket.dev`). Panel: sensores + iframe `/embed` + «Open full map».

## Despliegue

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

Solo loopback `127.0.0.1:9330` — TLS vía nginx (`deploy/nginx/atlas.modelmarket.dev.conf`).

## Tests

```bash
cd atlas && pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

Sin GAIA en vivo (mocks). Tablas env y API completa: [versión EN](../GUIDE.md).

## Honestidad

ATLAS es mapa + analista sobre relays GAIA, no dueño del hardware. Open-Meteo: CC BY 4.0; NWS/USGS/NOAA: dominio público de EE. UU.
