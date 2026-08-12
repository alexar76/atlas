# ATLAS — guide opérateur et développeur

**Langues :** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS est la **carte de capteurs** de l’écosystème : météo, air, marées, rivières, marin, carbone du réseau britannique, séismes, **incendies**, **radiation**, **brouillage GNSS** et ADS-B/AIS edge opérateur optionnel — via les relais [GAIA](https://iot.modelmarket.dev). **Les nouveaux dispositifs open-data vivent sur GAIA ; couches carte, pins et watchboxes sont des surfaces ATLAS** (pas d’UI produit séparée côté GAIA). Nœud **ATLAS** sur [Alien Monitor](https://magic-ai-factory.com/monitor/) et **ATLAS Analyst** (DeepSeek par défaut). Termes : [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH). Catalogue GAIA : [LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md).

## Surfaces

| URL | Rôle |
|-----|------|
| `/` | Carte MapLibre + couches + liste visible + AI |
| `/embed` | Carte compacte pour iframe Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, fiche station, SSE, **watchboxes** |
| `/api/ai/*` | Fournisseurs + chat ancré sur les données live |

## Modèle de charge

- Fond : **fleet** léger (pins) seulement.
- `POST /api/v1/viewport` — lectures du **bbox visible** ; voisins et catalogue chauffés en arrière-plan (TTL ~45 s), single-flight.
- Clic → `GET /api/v1/stations/{id}` — fiche lisible.
- **ATLAS Analyst :** LIVE SNAPSHOT de **toute** la flotte en cache + brief écosystème.
- Badges **LIVE** / **SIM** non traduits.

**Auto-apprentissage Analyst :** ATLAS SURFACES et `snapshot.capabilities` sont dérivés de `STATION_CATALOG` / `LAYER_META` / watchboxes — un nouvel appareil catalogue entre dans le prompt sans éditer le rôle.

L’acheteur **ne** passe pas lat/lon à GAIA invoke. Séismes / feu / brouillage portent lat/lon dans la lecture.

## Couches

GAIA vend les **lectures** (`gaia.*.read@v1`). ATLAS = **carte** (couches/pins) + **watchboxes**.

| Couche | device_id typiques | Notes |
|--------|-------------------|-------|
| Météo | `om-wx-01`, `nws-01`, mesh | + sims |
| Air | `om-aq-01`, `osm-01`, `sta-01`, mesh | |
| Marée | `noaa-tide-01` | |
| Rivière | `usgs-river-01` | |
| Marin | `ndbc-01`, `om-marine-01` | |
| Réseau | `uk-grid-01` | région |
| Sismique | `usgs-quake-01` | event lat/lon |
| Énergie | `em-01` | simulateur |
| Feu | `firms-fire-01` | NASA FIRMS — citer NASA |
| Radiation | `safecast-01` | Safecast **CC0** |
| Brouillage | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| Trafic | `feeder-adsb-01`, `feeder-ais-01` | edge opérateur (`GAIA_FEEDER_*`) |

Au total **~60 pins / 12 couches** : ancres nommées (open-data + feeder) + maillage Open-Meteo de 20 villes.

## Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

Un **watchbox** est un « cadre de veille » enregistré : bbox (west/south/east/north)
+ filtre de couches carte. Idée : « préviens-moi quand quelque chose de LIVE apparaît
dans ce rectangle sur ces couches » — ce n’est pas une lecture device GAIA.

- **Subscribe** (REST / `atlas.watchbox.subscribe@v1`) — créer/lister/supprimer le
  cadre (plumbing ; pas le SKU facturable Hub).
- **Check** (`atlas.watchbox.check@v1`) — évaluer le cadre contre le snapshot de
  flotte : matches + content receipt. Produit facturable Hub (bbox éphémère +
  couches sans id sauvé aussi possible).

Uniquement couches librement commercialisables (`ALLOWED_WATCHBOX_LAYERS`). Peer :
`/.well-known/ai-market.json`.

- `GET`/`POST /api/v1/watchboxes`
- `GET`/`DELETE /api/v1/watchboxes/{id}`
- `POST /api/v1/watchboxes/{id}/check`

Exemples curl : [EN](../GUIDE.md#watchboxes-atlaswatchboxsubscribev1--atlaswatchboxcheckv1).

## Produits composites (ATLAS > parties)

| SKU | Rôle | Convenience | Hub invoke |
|-----|------|-------------|------------|
| `atlas.situation.brief@v1` | Brief multi-couches scoré pour un bbox — drivers + pins LIVE cités ; refuse si vide | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | Hotspots FIRMS dans le bbox + météo LIVE proche (citer NASA) | `POST /api/v1/products/fire-weather` | same |
| `atlas.nearest.read@v1` | Pin LIVE le plus proche du `lat`/`lon` acheteur (couche, `max_km`, reçu) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Évalue watchbox sauvé ou éphémère → matches + reçu | watchbox `…/check` | same |

Fail-closed sans LIVE. FIRMS : citer NASA. **Nearest** utilise l’index carte ATLAS
(lectures GAIA restent `device_id`). Textes UI Hub :
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Catalogue après
crawl fédération.

## API (court)

- `GET /api/v1/snapshot` — pins + cache
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — analyse et **rapport** (`report: true`)

Prod LLM : **`DEEPSEEK_API_KEY`**, modèle `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (défaut `https://atlas.modelmarket.dev`). Panneau : capteurs + iframe `/embed` + « Open full map ».

## Déploiement

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

Loopback seul `127.0.0.1:9330` — TLS via nginx.

## Tests

```bash
cd atlas && pip install -e ".[dev]"
pytest -q
```

Sans GAIA live (mocks). Détail env/API : [EN](../GUIDE.md).

## Honnêteté

ATLAS = carte + **ATLAS Analyst** + watchboxes sur relais GAIA. Open-Meteo : CC BY 4.0 ; NWS/USGS/NOAA : domaine public US ; FIRMS : citer NASA ; Safecast : CC0 ; CyberNews : CC BY 4.0.
