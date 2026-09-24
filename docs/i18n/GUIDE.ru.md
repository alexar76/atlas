# ATLAS — руководство оператора и разработчика

**Языки:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS — **карта датчиков** экосистемы: погода, воздух, приливы, реки, море, углерод UK-сети, землетрясения, **пожары**, **радиация**, **GNSS-глушение** и опциональный свой edge ADS-B/AIS — поверх ретрансляторов [GAIA](https://iot.modelmarket.dev). **Новые открытые устройства живут на GAIA; слои карты, пины и watchbox — поверхность ATLAS** (отдельного продукта/UI на GAIA для них нет). Узел **ATLAS** в [Alien Monitor](https://monitor.modelmarket.dev/) (мини-карта + переход на полную) и встроенный **ATLAS Analyst** (по умолчанию DeepSeek). Термины: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH). Каталог устройств GAIA: [LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). **Сценарии оператора** (карта + ATLAS Analyst): [`OPERATOR-USE-CASES.ru.md`](OPERATOR-USE-CASES.ru.md).

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

Покупатель обычно **не** передаёт lat/lon в GAIA invoke — якоря задаёт оператор. Исключения на том же SKU: `om-aq-*` и `sc-*` (Sensor.Community). У землетрясений / пожаров / глушения координаты приходят в показании (reading).

## Слои

Показания продаёт **GAIA** (`gaia.*.read@v1`). **ATLAS** — карта (слои/пины) и **watchboxes**.

Актуальный список всех **39 слоёв**, точные цвета, значения и примеры устройств:
[легенда карты ATLAS](LEGEND.ru.md). Она генерируется из того же runtime-каталога,
что и карта. В каталоге сейчас **369 настроенных устройств**; плотные и событийные
источники могут добавлять точки показаний во время работы.

| Слой | Типичные device_id | Заметки |
|------|-------------------|---------|
| Погода | `om-wx-01`, `nws-01`, mesh | + sims |
| Воздух | `om-aq-01`, `osm-01`, `sta-01`, `sc-01`, `sc-{slug}`, mesh | SC: buyer lat/lon; crowd ≠ станция |
| Прилив | `noaa-tide-01` | |
| Река | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS / ECCC / SMHI |
| Море | `ndbc-01`, `om-marine-01` | |
| Сеть | `uk-grid-01` | регион |
| Сейсмика | `usgs-quake-01` | event lat/lon |
| Энергия | `em-01` | симулятор |
| Пожар | `firms-fire-01` | NASA FIRMS — цитировать NASA |
| Радиация | `safecast-01` + якоря | Safecast **CC0** · Hub = 30 дней; Melbourne/Adelaide — архив (сетка AU 2014, `captured_at`) |
| Глушение | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| Трафик | `feeder-adsb-01`, `feeder-ais-01` | свой edge (`GAIA_FEEDER_*`) |
| Публичный AIS | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic CC BY 4.0 (FI) · Kystverket NLOD (NO) — не один «европейский AIS» |
| Публичный ADS-B | `adsb-lol-01` | ADSB.lol ODbL 1.0 — не own-edge, не OpenSky/ADSBx |
| Цунами | `nws-tsunami-01`, `ptwc-01` | NWS CAP + PTWC Atom (не мареограф; пусто ≠ все спокойно) |
| Тропические циклоны | `nhc-cyclone-01` | NHC/CPHC AL+EP+CP — не JTWC |
| Качество воды | `usgs-wq-01` | Свежие (48 ч) постраничные latest-continuous наблюдения с join к USGS monitoring-locations; только станции с нужными параметрами, одна станция = одна точка; Approved/Provisional + qualifiers; постоянная история и uptime по опросам |
| DART | `noaa-dart-01`, `dart-*` | Все 43 активные станции из зафиксированного официального каталога NDBC |
| EPA RadNet | `radnet-*` | Все 140 официальных координат мониторов EPA, а не три демо-города |
| Статус NEXRAD | `nexrad-status-01` | Каждая станция WSR-88D в собственной координате; статус, не отражаемость |
| Координатные сетки/модели | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | `lat`/`lon` покупателя; ATLAS использует возвращённую координату исходной/расчётной ячейки |

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
| `atlas.situation.brief@v1` | Кросс-слойный scored brief по bbox — по умолчанию слои карты (flood, EFFIS, lightning, volcano, публичный AIS, tsunami…); refuse если пусто | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS **и/или** Copernicus EFFIS в bbox + ближайший LIVE weather (два списка; не прогноз) | `POST /api/v1/products/fire-weather` | same |
| `atlas.smoke.operations@v1` | `lat`/`lon` объекта → **point-in-polygon** по полной подписанной геометрии дыма NOAA HMS (контуры **и** отверстия, корректно через 180-й меридиан) + PM2.5/AQI в той же точке; отказ при неполной выгрузке HMS или отсутствии данных о воздухе. Качественный анализ, не измеренный PM2.5 и не приказ об эвакуации | `POST /api/v1/products/smoke-operations` | same |
| `atlas.nearest.read@v1` | Ближайший LIVE-пин к buyer `lat`/`lon` (слой, `max_km`, receipt) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Оценка сохранённого или ephemeral watchbox → matches + receipt | watchbox `…/check` | same |
| `atlas.mesh.sample@v1` | Halton-выборка LIVE-пинов лицензированной in-situ сети (`ee-wx`, `pegel`, …). Sibling `lattice.sequence@v1`. Не ECVRF (Sortes — sibling hop), не Open-Meteo | `POST /api/v1/products/mesh-sample` | same |
| `atlas.field.consensus@v1` | Консенсус (Murmuration-equivalent) LIVE in-situ показаний (мин. 3). Не прогноз, не Open-Meteo-как-станция | `POST /api/v1/products/field-consensus` | same |
| `atlas.field.posterior@v1` | Пространственный RBF GP **текущего** LIVE-снимка. Интерполяция сейчас; не прогноз. Sibling `gauss.field@v1` | `POST /api/v1/products/field-posterior` | same |
| `atlas.field.shape@v1` | H0-персистентность LIVE-пинов (компоненты vs радиус). Не Betti-1, не AQI. Sibling `betti.homology@v1` | `POST /api/v1/products/field-shape` | same |

Fail-closed без LIVE. FIRMS — цитировать NASA. **Nearest** — buyer `lat`/`lon` на
индексе ATLAS (GAIA reads остаются `device_id`). Описания в UI Hub:
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Каталог:
`modelmarket.dev` после federation crawl.

## API (кратко)

- `GET /api/v1/snapshot` — пины + кэш
- `POST /api/v1/viewport` — `{west,south,east,north,force?}` (+ фоновый prefetch)
- `GET /api/v1/stations/{id}` — title / summary / metrics; пин исчезнувшей детекции отвечает карточкой «cleared from the live window», а не 404
- `POST /api/v1/refresh` — только с операторским токеном (`X-Atlas-Token`): один вызов перечитывает весь каталог
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
