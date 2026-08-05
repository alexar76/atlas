# ATLAS — руководство оператора и разработчика

**Языки:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS — **карта физических датчиков** экосистемы: погода, воздух, приливы, углерод UK-сети и землетрясения поверх релеев [GAIA](https://iot.modelmarket.dev). Узел **ATLAS** в [Alien Monitor](https://magic-ai-factory.com/monitor/) (мини-карта + переход на полную) и встроенный **ATLAS Analyst** (по умолчанию DeepSeek).

## Поверхности

| URL | Назначение |
|-----|------------|
| `/` | Полная карта MapLibre + слои + список «в кадре» + AI |
| `/embed` | Компактная карта для iframe Monitor |
| `/health` | Liveness |
| `/api/v1/*` | Snapshot, viewport, карточка станции, SSE |
| `/api/ai/*` | Провайдеры + чат с опорой на live-данные |

## Модель нагрузки

- Фон: только дешёвый **fleet** (пины), без массовых readings.
- `POST /api/v1/viewport` — readings **только в видимом bbox**, TTL-кэш (~45 с), single-flight.
- Клик → `GET /api/v1/stations/{id}` — человекочитаемая карточка (обновление, если старше ~20 с).
- AI: сервер сам вставляет LIVE SNAPSHOT в system prompt (клиент не подделает цифры).

Покупатель **не** передаёт lat/lon в GAIA invoke — якоря задаёт оператор GAIA. У землетрясений координаты приходят в reading.

## Слои

| Слой | Типичные device_id |
|------|-------------------|
| Погода | `om-wx-01`, `nws-01` |
| Воздух | `om-aq-01`, `osm-01`, `sta-01` |
| Прилив | `noaa-tide-01` |
| Сеть | `uk-grid-01` (регион) |
| Сейсмика | `usgs-quake-01` |

## API (кратко)

- `GET /api/v1/snapshot` — пины + кэш
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — анализ и **ситуационный отчёт** (`report: true`)

Прод LLM: **`DEEPSEEK_API_KEY`**, модель `deepseek-v4-pro`.

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` (по умолчанию `https://atlas.modelmarket.dev`). Панель: сенсоры + iframe `/embed` + «Open full map».

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
cd atlas && pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

Без живого GAIA (моки). Полные таблицы env и детали API — в [английской версии](../GUIDE.md).

## Честность

ATLAS — карта и аналитик над ретрансляцией GAIA, не владелец железа. Open-Meteo — CC BY 4.0; NWS/USGS/NOAA — public domain США.
