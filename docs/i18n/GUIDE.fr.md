# ATLAS — guide opérateur et développeur

**Langues :** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS est la **carte des capteurs physiques** de l’écosystème : météo, air, marées, carbone du réseau britannique et séismes via les relais [GAIA](https://iot.modelmarket.dev). Nœud **ATLAS** sur [Alien Monitor](https://magic-ai-factory.com/monitor/) (mini-carte + lien carte complète) et **ATLAS Analyst** (DeepSeek par défaut).

## Surfaces

| URL | Rôle |
|-----|------|
| `/` | Carte MapLibre + couches + liste « dans la vue » + AI |
| `/embed` | Carte compacte pour iframe Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, fiche station, SSE |
| `/api/ai/*` | Fournisseurs + chat ancré sur les données live |

## Modèle de charge

- Arrière-plan : **fleet** léger (épingles) uniquement.
- `POST /api/v1/viewport` — lectures **dans le bbox visible**, cache TTL (~45 s), single-flight.
- Clic → `GET /api/v1/stations/{id}` — fiche lisible (rafraîchir si > ~20 s).
- AI : le serveur injecte le LIVE SNAPSHOT (pas de chiffres forgés côté client).

L’acheteur **ne** passe **pas** lat/lon à l’invoke GAIA — ancrages opérateur. Les séismes portent lat/lon dans le reading.

## Couches

| Couche | device_id typiques |
|--------|-------------------|
| Météo | `om-wx-01`, `nws-01` |
| Air | `om-aq-01`, `osm-01`, `sta-01` |
| Marée | `noaa-tide-01` |
| Réseau | `uk-grid-01` (région) |
| Séismes | `usgs-quake-01` |

## API (aperçu)

- `GET /api/v1/snapshot` — épingles + cache
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — analyse et **rapport de situation** (`report: true`)

LLM prod : **`DEEPSEEK_API_KEY`**, modèle `deepseek-v4-pro`.

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
cd atlas && pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

Sans GAIA live (mocks). Détail env/API : [version EN](../GUIDE.md).

## Honnêteté

ATLAS = carte + analyste sur relais GAIA, pas propriétaire du matériel. Open-Meteo : CC BY 4.0 ; NWS/USGS/NOAA : domaine public US.
