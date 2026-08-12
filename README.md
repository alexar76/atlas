<!-- aicom-mirror-notice -->
> **📖 Read-only mirror.** `atlas` is published from the canonical AI-Factory monorepo.
> **Pull requests are not accepted** — any commit pushed here is overwritten by
> `scripts/mirror_satellites.sh` on the next sync.
> 🐞 Found a bug or have a request? Please **[open an issue](https://github.com/alexar76/atlas/issues)**.

# ATLAS

<!-- aicom-readme-badges -->
<p align="center">
  <a href="https://github.com/alexar76/atlas/actions/workflows/ci.yml"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/ci.svg" alt="CI" /></a>
  <a href="https://github.com/alexar76/atlas/actions/workflows/pages.yml"><img src="https://github.com/alexar76/atlas/actions/workflows/pages.yml/badge.svg" alt="Pages deploy" /></a>
  <a href="https://atlas.modelmarket.dev/"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/demo.svg" alt="Live demo status" /></a>
  <a href="https://alexar76.github.io/atlas/"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/landing.svg" alt="Landing" /></a>
  <a href="https://pypi.org/project/aimarket-atlas/"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/pypi.svg" alt="PyPI" /></a>
  <a href="https://iot.modelmarket.dev/"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/gaia.svg" alt="GAIA relays" /></a>
  <img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/python.svg" alt="Python >=3.11" />
  <img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/tests.svg" alt="101 tests passed" />
  <img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/docker.svg" alt="Docker ready" />
  <img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/maplibre.svg" alt="MapLibre SPA" />
  <img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/deepseek.svg" alt="DeepSeek default" />
  <a href="https://github.com/alexar76/atlas/blob/main/LICENSE"><img src="https://raw.githubusercontent.com/alexar76/atlas/main/docs/badges/license.svg" alt="License: MIT" /></a>
</p>
<!-- /aicom-readme-badges -->




<p align="center">
  <strong>ATLAS</strong> — planetary physical-sensor map over <a href="https://iot.modelmarket.dev/">GAIA</a> relays<br/>
  Honest <strong>LIVE</strong> vs <strong>SIM</strong> pins · optional <strong>3D globe</strong> with sensor towers · part of the <a href="https://github.com/alexar76">alexar76</a> AI agent economy
</p>

<p align="center">
  <a href="https://atlas.modelmarket.dev/">
    <img src="docs/screenshots/readme/hero-orbit.png" alt="ATLAS — Earth from orbit with live sensor constellation" width="820">
  </a>
  <br>
  <sub>Weather · air · fire · radiation · jamming · traffic · quake · more — <a href="https://atlas.modelmarket.dev/"><b>live map →</b></a> · <a href="https://alexar76.github.io/atlas/"><b>landing →</b></a> · <a href="#quick-start"><b>run locally →</b></a></sub>
</p>

<p align="center">
  <strong><a href="https://atlas.modelmarket.dev/">Live map</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/atlas/">Landing</a></strong>
  ·
  <strong><a href="docs/GUIDE.md">Guide (EN)</a></strong>
  ·
  <strong><a href="https://iot.modelmarket.dev/">GAIA</a></strong>
  ·
  <strong><a href="https://magic-ai-factory.com/monitor/">Alien Monitor</a></strong>
</p>

**Docs:** [EN](docs/GUIDE.md) · [RU](docs/i18n/GUIDE.ru.md) · [ES](docs/i18n/GUIDE.es.md) · [FR](docs/i18n/GUIDE.fr.md) · [ZH](docs/i18n/GUIDE.zh.md)
**Add a sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH)

ATLAS is the ecosystem **physical sensor map**: weather, air quality, tides, rivers, marine, UK grid carbon, earthquakes, **wildfire**, **radiation**, **GNSS jamming**, optional own-edge **ADS-B/AIS**, and energy — plotted from [GAIA](https://iot.modelmarket.dev/) relays. **New open-data devices are registered on GAIA; map layers, pins, and watchboxes are ATLAS** (no separate GAIA product UI for those surfaces). Pins are labelled **LIVE** only when GAIA exposes an upstream provenance `source` URL; simulators are **SIM**. It ships as the **`atlas`** node on [Alien Monitor](https://magic-ai-factory.com/monitor/) (`/embed` preview + full-map CTA) and includes **ATLAS Analyst** (DeepSeek `deepseek-v4-pro` by default) with prompt-injection firewall, LLM retries, reply language matching the question (fallback: UI locale), and a full **AICOM / AIMarket ecosystem brief** so the assistant can answer Hub / ARGUS / Metis / GAIA questions — not only sensor readings.

## Gallery

<p align="center">
  <img src="docs/screenshots/readme/map.png" alt="ATLAS full map" width="820"><br>
  <sub>Full map · 12 layers (incl. fire / radiation / jamming / traffic) · LIVE/SIM · in-view list</sub>
</p>

<p align="center">
  <img src="docs/screenshots/readme/analyst.png" alt="ATLAS Analyst" width="400">
  &nbsp;
  <img src="docs/screenshots/readme/embed.png" alt="ATLAS embed" width="400"><br>
  <sub>ATLAS Analyst · Alien Monitor embed</sub>
</p>

## Surfaces

| Surface | URL / path |
|---------|------------|
| **Public map** | https://atlas.modelmarket.dev/ |
| Landing (Pages) | https://alexar76.github.io/atlas/ |
| Alien Monitor embed | `/embed` |
| Health | `/health` |
| Snapshot / viewport / station / watchboxes | `/api/v1/*` |
| Monitor payload | `/api/v1/monitor` |
| Analyst chat | `/api/ai/ask` |

## Quick start

```bash
pip install aimarket-atlas
export DEEPSEEK_API_KEY=sk-…   # optional Analyst
export ATLAS_GAIA_URL=https://iot.modelmarket.dev
atlas --host 127.0.0.1 --port 9330
open http://127.0.0.1:9330/
```

Docker:

```bash
docker compose -f docker-compose.local.yml up -d --build
open http://127.0.0.1:9330/
```

From a monorepo checkout (editable):

```bash
cd atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
atlas --reload --host 127.0.0.1 --port 9330
```

## Production

```bash
# From monorepo root (factory host):
./scripts/deploy_atlas.sh --remote root@<host>
# Public UI (no password): https://atlas.modelmarket.dev/
```

## Load model

| Mechanism | Role |
|-----------|------|
| Cheap fleet poll | Pins only |
| Viewport readings | Sensors **in the visible bbox** |
| Click detail | Human-readable card + shared TTL cache |
| LIVE vs SIM | `source` present ⇒ LIVE; else SIM (GAIA rule) |
| Single-flight | One GAIA call per sensor under concurrency |
| SSE | Fleet snapshot fan-out |
| Analyst | Server snapshot + firewall + retries; language = question ∥ UI locale |

Buyers **cannot** pass lat/lon into GAIA invoke — anchors are operator env on GAIA.

## Tests

```bash
pip install -e ".[dev]"
# or: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

Mocked GAIA — no network required. **101** tests.

## Alien Monitor

Node id `atlas` · env `ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` · panel: LIVE/SIM sensors + `/embed` iframe + full map CTA.

## License / attribution

MIT — see [LICENSE](LICENSE).

Map UI + watchboxes over GAIA relays. Open-Meteo CC BY 4.0; NWS/USGS/NOAA U.S. public domain; UK Carbon Intensity open data; FIRMS cite NASA; Safecast CC0; CyberNews GNSS CC BY 4.0.