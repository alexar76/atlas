# ATLAS — руководство оператора и разработчика

**Языки:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS — **карта датчиков** экосистемы: погода, воздух, приливы, реки, море, углерод UK-сети, землетрясения, **пожары**, **радиация**, **GNSS-глушение** и опциональный свой edge ADS-B/AIS — поверх ретрансляторов [GAIA](https://iot.modelmarket.dev). **Новые открытые устройства живут на GAIA; слои карты, пины и watchbox — поверхность ATLAS** (отдельного продукта/UI на GAIA для них нет). Узел **ATLAS** в [Alien Monitor](https://magic-ai-factory.com/monitor/) (мини-карта + переход на полную) и встроенный **ATLAS Analyst** (по умолчанию DeepSeek). Термины: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH). Каталог устройств GAIA: [LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md).

## Поверхности

| URL | Назначение |
|-----|------------|
| `/` | Полная карта MapLibre + слои + список «в кадре» + AI |
| `/embed` | Компактная карта для iframe Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, карточка станции, SSE, **watchboxes** |
| `/api/ai/*` | Провайдеры + чат с опорой на live-данные |

## Модель нагрузки

- Фон: только дешёвый **fleet** (пины), без массовых показаний.
- `POST /api/v1/viewport` — показания **в видимом bbox** сразу; соседи (`viewport_pad`) и остальной каталог греются в фоне в общий TTL-кэш (~45 с), single-flight.
- Клик → `GET /api/v1/stations/{id}` — человекочитаемая карточка (обновление, если старше ~20 с).
- **ATLAS Analyst:** сервер вставляет LIVE SNAPSHOT **всего** закэшированного флота + бриф экосистемы (только датчики + AICOM/AIMarket; клиент не подделает цифры).
- Бейджи **LIVE** / **SIM** не переводятся (см. глоссарий).

**Автообучение Analyst:** блок ATLAS SURFACES и `snapshot.capabilities` строятся из `STATION_CATALOG` / `LAYER_META` / watchboxes — новый device в каталоге сразу в промпте (без ручного SKU в тексте роли).

Покупатель **не** передаёт lat/lon в GAIA invoke — якоря задаёт оператор GAIA. У землетрясений / пожаров / глушения координаты приходят в показании (reading).

## Слои

Показания продаёт **GAIA** (`gaia.*.read@v1`). **ATLAS** — карта (слои/пины) и **watchboxes**.

| Слой | Типичные device_id | Заметки |
|------|-------------------|---------|
| Погода | `om-wx-01`, `nws-01`, mesh | + sims |
| Воздух | `om-aq-01`, `osm-01`, `sta-01`, mesh | |
| Прилив | `noaa-tide-01` | |
| Река | `usgs-river-01` | Potomac / USGS NWIS |
| Море | `ndbc-01`, `om-marine-01` | |
| Сеть | `uk-grid-01` | регион |
| Сейсмика | `usgs-quake-01` | event lat/lon |
| Энергия | `em-01` | симулятор |
| Пожар | `firms-fire-01` | NASA FIRMS — цитировать NASA |
| Радиация | `safecast-01` | Safecast **CC0** |
| Глушение | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| Трафик | `feeder-adsb-01`, `feeder-ais-01` | свой edge (`GAIA_FEEDER_*`) |

Всего **~60 пинов / 12 слоёв**: именованные якоря (в т.ч. open-data + feeder) + меш Open-Meteo по 20 городам (`om-wx-{slug}` / `om-aq-{slug}`; синхронизирован с `gaia/gaia/devices/om_mesh.py`).

## Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

**Watchbox** — сохранённая «рамка наблюдения»: bbox (west/south/east/north) + фильтр
слоёв карты. Смысл: «скажи, когда в этом прямоугольнике на этих слоях появится LIVE» —
это не чтение GAIA-устройства.

- **Subscribe** (REST / `atlas.watchbox.subscribe@v1`) — создать/список/удалить рамку
  (plumbing, не billable Hub SKU).
- **Check** (`atlas.watchbox.check@v1`) — сверить рамку с текущим снимком флота:
  совпадения + content receipt. Это billable продукт Hub (можно и ephemeral bbox +
  layers без сохранённого id).

Только свободно коммерциализируемые слои (`ALLOWED_WATCHBOX_LAYERS`). Peer:
`/.well-known/ai-market.json`.

- `GET`/`POST /api/v1/watchboxes`
- `GET`/`DELETE /api/v1/watchboxes/{id}`
- `POST /api/v1/watchboxes/{id}/check`

Примеры curl — в [EN](../GUIDE.md#watchboxes-atlaswatchboxsubscribev1--atlaswatchboxcheckv1).

## Composite products (ATLAS > частей)

| SKU | Что делает | Convenience | Hub invoke |
|-----|------------|-------------|------------|
| `atlas.situation.brief@v1` | Кросс-слойный scored brief по bbox — drivers + цитаты LIVE; refuse если пусто | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS hotspots в bbox + ближайший LIVE weather (цитировать NASA) | `POST /api/v1/products/fire-weather` | same |
| `atlas.nearest.read@v1` | Ближайший LIVE-пин к buyer `lat`/`lon` (слой, `max_km`, receipt) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Оценка сохранённого или ephemeral watchbox → matches + receipt | watchbox `…/check` | same |

Fail-closed без LIVE. FIRMS — цитировать NASA. **Nearest** — buyer `lat`/`lon` на
индексе ATLAS (GAIA reads остаются `device_id`). Описания в UI Hub:
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Каталог:
`modelmarket.dev` после federation crawl.

## API (кратко)

- `GET /api/v1/snapshot` — пины + кэш
- `POST /api/v1/viewport` — `{west,south,east,north,force?}` (+ фоновый prefetch)
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — анализ и **ситуационный отчёт** (`report: true`); только датчики + экосистема

Прод LLM: **`DEEPSEEK_API_KEY`**, модель `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (по умолчанию `https://atlas.modelmarket.dev`). Панель: датчики + iframe `/embed` + «Open full map».

## Деплой

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build   # локально :9330
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build         # прод
# nginx: deploy/nginx/atlas.modelmarket.dev.conf
```

Только loopback `127.0.0.1:9330` — TLS через nginx.

## Тесты

```bash
cd atlas && pip install -e ".[dev]"
pytest -q
```

Без живого GAIA (моки). Полные таблицы env и детали API — в [английской версии](../GUIDE.md).

## Честность

ATLAS — карта, **ATLAS Analyst** и watchboxes над ретрансляторами GAIA, не владелец железа. Open-Meteo — CC BY 4.0; NWS/USGS/NOAA — public domain США; FIRMS — цитировать NASA; Safecast — CC0; CyberNews — CC BY 4.0.
