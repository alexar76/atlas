# ATLAS

> 🌐 [English](../README.md) · **Русский** · [Español](README.es.md) · [Français](README.fr.md) · [中文](README.zh.md) · [Глоссарий](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


<p align="center">
  <strong>ATLAS</strong> — планетарная <strong>карта датчиков</strong> поверх ретрансляторов <a href="https://iot.modelmarket.dev/">GAIA</a><br/>
  Честные пины <strong>LIVE</strong> vs <strong>SIM</strong> · опциональный <strong>3D-глобус</strong> с башнями датчиков · часть экономики AI-агентов <a href="https://github.com/alexar76">alexar76</a>
</p>

<p align="center">
  <a href="https://atlas.modelmarket.dev/">
    <img src="../docs/screenshots/readme/hero-orbit.png" alt="ATLAS" width="820">
  </a>
  <br>
  <sub>Погода · воздух · пожар · целостность GNSS · глушение · трафик · землетрясения · ещё — <a href="https://atlas.modelmarket.dev/"><b>живая карта →</b></a></sub>
</p>

<p align="center">
  <strong><a href="https://atlas.modelmarket.dev/">Живая карта</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/atlas/">Лендинг</a></strong>
  ·
  <strong><a href="GUIDE.md">Guide (EN)</a></strong>
  ·
  <strong><a href="https://iot.modelmarket.dev/">GAIA</a></strong>
  ·
  <strong><a href="https://magic-ai-factory.com/monitor/">Alien Monitor</a></strong>
</p>

**Документы:** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)  
**Сценарии оператора:** [EN](OPERATOR-USE-CASES.md) · [RU](i18n/OPERATOR-USE-CASES.ru.md) · …  
**Добавить датчик:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH)

ATLAS — **карта физических датчиков** экосистемы: погода, качество воздуха, приливы, реки, море, углерод UK grid, землетрясения, **пожары**, **радиация**, станции **целостности GNSS**, отдельно sourced отчёты о **глушении GNSS**, **публичный финский AIS**, **NWS tsunami CAP**, опциональный edge **ADS-B/AIS** и энергия — с ретрансляторов [GAIA](https://iot.modelmarket.dev/). Каждая GNSS-станция — стабильный кликабельный `point_id`; агенты запрашивают её через `atlas.point.read@v1` или подписанное поле point/bbox/route через `atlas.gnss.degradation.read@v1`. Инвентарь, derived degradation и reported interference — разные классы утверждений. **Новые open-data устройства регистрируются на GAIA; слои карты, пины и watchboxes — ATLAS**. Пины помечены **LIVE** только когда GAIA отдаёт upstream provenance `source` URL; симуляторы — **SIM**. Узел **`atlas`** на [Alien Monitor](https://magic-ai-factory.com/monitor/) и **ATLAS Analyst** (DeepSeek `deepseek-v4-pro` по умолчанию) с файрволом от prompt-injection, ретраями LLM, языком ответа по вопросу (fallback: UI locale) и полным **брифом экосистемы** AICOM / AIMarket.

## Галерея

<p align="center">
  <img src="../docs/screenshots/readme/map.png" alt="ATLAS full map" width="820"><br>
  <sub>Полная карта · 24 слоя · LIVE/SIM · список in-view</sub>
</p>

## Поверхности

| Поверхность | URL / path |
|---------|------------|
| **Публичная карта** | https://atlas.modelmarket.dev/ |
| Лендинг (Pages) | https://alexar76.github.io/atlas/ |
| Embed Alien Monitor | `/embed` |
| Health | `/health` |
| Snapshot / viewport / station / watchboxes | `/api/v1/*` |
| Monitor payload | `/api/v1/monitor` |
| Analyst chat | `/api/ai/ask` |

## Быстрый старт

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
```

Из монорепо (editable):

```bash
cd atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
atlas --reload --host 127.0.0.1 --port 9330
```

## Production

```bash
./scripts/deploy_atlas.sh --remote root@<host>
# Public UI: https://atlas.modelmarket.dev/
```

## Модель нагрузки

| Механизм | Роль |
|-----------|------|
| Cheap fleet poll | Только пины |
| Показания viewport | Датчики **в видимом bbox** |
| Click detail | Карточка + общий TTL-кэш |
| LIVE vs SIM | есть `source` ⇒ LIVE; иначе SIM (правило GAIA) |
| Single-flight | Один вызов GAIA на датчик при concurrency |
| SSE | Fan-out снимка флота |
| Analyst | Снимок сервера + файрвол + ретраи; язык = вопрос ∥ UI locale |

Покупатели **не** могут передать lat/lon в GAIA invoke — якоря задаёт operator env на GAIA.

## Тесты

```bash
pip install -e ".[dev]"
pytest -q
```

Mocked GAIA — сеть не нужна. **101** тест.

## Alien Monitor

Node id `atlas` · env `ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL` · панель: датчики LIVE/SIM + iframe `/embed` + CTA полной карты.

## Лицензия / атрибуция

MIT — см. [LICENSE](../LICENSE).

UI карты + watchboxes над ретрансляторами GAIA. Open-Meteo CC BY 4.0; NWS/USGS/NOAA U.S. public domain; UK Carbon Intensity open data; FIRMS cite NASA; Safecast CC0; CyberNews GNSS CC BY 4.0.
