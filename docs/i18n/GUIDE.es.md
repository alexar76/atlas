# ATLAS — guía de operador y desarrollador

**Idiomas:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS es el **mapa de sensores** del ecosistema: clima, aire, mareas, ríos, marino, carbono de la red británica, terremotos, **incendios**, **radiación**, **interferencia GNSS**, AIS público finlandés, alertas tsunami NWS y ADS-B/AIS de borde propio opcional — sobre los relés de [GAIA](https://iot.modelmarket.dev). **Los dispositivos open-data nuevos viven en GAIA; capas del mapa, pines y watchboxes son superficies ATLAS** (no hay UI de producto separada en GAIA). Aparece como nodo **ATLAS** en [Alien Monitor](https://magic-ai-factory.com/monitor/) e incluye **ATLAS Analyst** (DeepSeek por defecto). Términos: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH). Catálogo GAIA: [LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). **Casos de uso del operador** (mapa + ATLAS Analyst): [`OPERATOR-USE-CASES.es.md`](OPERATOR-USE-CASES.es.md).

## Superficies

| URL | Rol |
|-----|-----|
| `/` | Mapa MapLibre completo + capas + lista en vista + AI |
| `/embed` | Mapa compacto para iframe del Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, ficha de estación, SSE, **watchboxes** |
| `/api/ai/*` | Proveedores + chat anclado a datos live |

## Modelo de carga

- Fondo: solo **fleet** barato (pins), sin lecturas masivas.
- `POST /api/v1/viewport` — lecturas del **bbox visible** al instante; vecinos y el resto del catálogo se calientan en segundo plano (TTL ~45 s), single-flight.
- Clic → `GET /api/v1/stations/{id}` — ficha legible (refresco si > ~20 s).
- **ATLAS Analyst:** LIVE SNAPSHOT de **toda** la flota en caché + brief del ecosistema.
- Badges **LIVE** / **SIM** no se traducen.

**Aprendizaje automático del Analyst:** ATLAS SURFACES y `snapshot.capabilities` se generan desde `STATION_CATALOG` / `LAYER_META` / watchboxes — un device nuevo en el catálogo entra al prompt sin editar el rol a mano.

El comprador **no** pasa lat/lon a GAIA invoke — anclajes del operador GAIA. Terremotos / fuego / jamming llevan lat/lon en la lectura.

## Capas

GAIA vende **lecturas** (`gaia.*.read@v1`). ATLAS es el **mapa** (capas/pines) y los **watchboxes**.

| Capa | device_id típicos | Notas |
|------|-------------------|-------|
| Clima | `om-wx-01`, `nws-01`, mesh | + sims |
| Aire | `om-aq-01`, `osm-01`, `sta-01`, mesh | |
| Marea | `noaa-tide-01` | |
| Río | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS / ECCC / SMHI |
| Marino | `ndbc-01`, `om-marine-01` | |
| Red | `uk-grid-01` | región |
| Sísmica | `usgs-quake-01` | event lat/lon |
| Energía | `em-01` | simulador |
| Fuego | `firms-fire-01` | NASA FIRMS — citar NASA |
| Radiación | `safecast-01` + anclas | Safecast **CC0** · Hub = 30 días; Melbourne/Adelaide archivo (malla AU 2014, `captured_at`) |
| Interferencia | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| Tráfico | `feeder-adsb-01`, `feeder-ais-01` | edge propio (`GAIA_FEEDER_*`) |
| AIS público | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic CC BY 4.0 (FI) · Kystverket NLOD (NO) — no un «AIS europeo» |
| ADS-B público | `adsb-lol-01` | ADSB.lol ODbL 1.0 — no edge propio, no OpenSky/ADSBx |
| Tsunami | `nws-tsunami-01`, `ptwc-01` | NWS CAP + PTWC Atom (no un mareógrafo; vacío ≠ todo despejado) |
| Ciclones tropicales | `nhc-cyclone-01` | NHC/CPHC AL+EP+CP — no JTWC |

En total **~80 pines / 24 capas**: anclas nombradas (open-data + feeder) + malla Open-Meteo de 20 ciudades (`om-wx-{slug}` / `om-aq-{slug}`).

## Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

Un **watchbox** es un “marco de vigilancia” guardado: bbox (west/south/east/north) +
filtro de capas del mapa. Idea: “avísame cuando haya algo LIVE en este rectángulo
en estas capas” — no es una lectura de dispositivo GAIA.

- **Subscribe** (REST / `atlas.watchbox.subscribe@v1`) — crear/listar/borrar el marco
  (plumbing; no es el SKU de pago del Hub).
- **Check** (`atlas.watchbox.check@v1`) — evaluar el marco contra el snapshot de la
  flota: matches + content receipt. Producto facturable en Hub (también bbox
  efímero + capas sin id guardado).

Solo capas libremente comercializables (`ALLOWED_WATCHBOX_LAYERS`). Peer:
`/.well-known/ai-market.json`.

- `GET`/`POST /api/v1/watchboxes`
- `GET`/`DELETE /api/v1/watchboxes/{id}`
- `POST /api/v1/watchboxes/{id}/check`

Ejemplos curl: [EN](../GUIDE.md#watchboxes-atlaswatchboxsubscribev1--atlaswatchboxcheckv1).

## Productos compuestos (ATLAS > partes)

| SKU | Qué hace | Convenience | Hub invoke |
|-----|----------|-------------|------------|
| `atlas.situation.brief@v1` | Brief multi-capa con score para un bbox — por defecto capas del mapa (flood, EFFIS, lightning, volcano, AIS público, tsunami…); refuse si vacío | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS **y/o** Copernicus EFFIS en bbox + clima LIVE cercano (dos listas; no pronóstico) | `POST /api/v1/products/fire-weather` | same |
| `atlas.nearest.read@v1` | Pin LIVE más cercano a `lat`/`lon` del comprador (capa, `max_km`, recibo) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Evalúa watchbox guardado o efímero → matches + recibo | watchbox `…/check` | same |

Fail-closed sin LIVE. FIRMS: citar NASA. **Nearest** usa el índice de mapa ATLAS
(lecturas GAIA siguen con `device_id`). Textos UI Hub:
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Catálogo tras
federation crawl.

## API (breve)

- `GET /api/v1/snapshot` — pins + caché
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — análisis e **informe** (`report: true`)

Prod LLM: **`DEEPSEEK_API_KEY`**, modelo `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (por defecto `https://atlas.modelmarket.dev`). Panel: sensores + iframe `/embed` + «Open full map».

## Despliegue

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

Solo loopback `127.0.0.1:9330` — TLS vía nginx (`deploy/nginx/atlas.modelmarket.dev.conf`).

## Pruebas

```bash
cd atlas && pip install -e ".[dev]"
pytest -q
```

Sin GAIA en vivo (mocks). Tablas env y API: [EN](../GUIDE.md).

## Honestidad

ATLAS es mapa + **ATLAS Analyst** + watchboxes sobre relés GAIA. Open-Meteo: CC BY 4.0; NWS/USGS/NOAA: dominio público EE. UU.; FIRMS: citar NASA; Safecast: CC0; CyberNews: CC BY 4.0.
