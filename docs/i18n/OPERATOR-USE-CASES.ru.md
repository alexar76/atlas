# ATLAS — сценарии оператора

**Языки:** [EN](../OPERATOR-USE-CASES.md) · [RU](OPERATOR-USE-CASES.ru.md) · [ES](OPERATOR-USE-CASES.es.md) · [FR](OPERATOR-USE-CASES.fr.md) · [ZH](OPERATOR-USE-CASES.zh.md)

ATLAS — **карта датчиков** оператора плюс **ATLAS Analyst**. GAIA аттестует **показания** LIVE-**ретрансляторов**; Hub продаёт `capability_id`. Эта страница — как оператор (или **агент** с опорой на Analyst) задаёт вопрос о физическом мире, не подменяя **source** моделью.

Термины: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md). Карта/API: [`GUIDE.ru.md`](GUIDE.ru.md). Ретрансляторы и лицензии: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). Добавить **пин**: [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md).

Дата аудита: **2026-08-14**. Статусы:

| Статус | Смысл |
|--------|--------|
| **Live now** | Уже на карте. Спрашивайте Analyst по этим **слоям**. |
| **Proposed — sell** | Лицензия + HTTPS + география закреплены; ещё не в коде. Можно продавать как Hub SKU после Recipe B. |
| **Hold** | Не продавать и не показывать как LIVE, пока не закрыт пробел ниже. |

---

## Как задать вопрос

1. Включите только те **слои**, которые на него отвечают (wildfire — не **тропический циклон**).
2. Сдвиньте **viewport** в лицензированную географию (финский **AIS** — не Северное море).
3. Кликните **пин**. Смотрите `source`, `LIVE`/`SIM` и `captured_at` / время CAP, если есть.
4. Спросите **ATLAS Analyst**, назвав **слой**. Промпт опирается на кэш флота — он должен цитировать пины, а не выдумывать прогноз.
5. Для постоянной проверки — **watchbox** (`atlas.watchbox.subscribe@v1`) на этот слой + bbox.

GAIA **invoke** обычно только `device_id` для устройств с **якорем** оператора. Исключения с lat/lon покупателя на том же SKU: Open-Meteo AQ (`om-aq-*`) и Sensor.Community (`sc-01` / `sc-{slug}`). Event-ленты (FIRMS, землетрясения, CAP) несут координаты в **показании**.

---

## Правила продажи и встраивания

Тот же коммерческий фильтр, что в LIVE-RELAYS. Сценарий, который не проходит строку — **Hold**.

| Гейт | Проход |
|------|--------|
| Лицензия | CC0 / CC BY / OGL / NLOD / PD США / Copernicus CC BY, уже принятые в репозитории. Не NC, не «только ориентир», не ToS через helpdesk. |
| Встраивание | HTTPS-хост в **allowlist** GAIA; без клиентских URL; fail-closed → 503, Hub не дебетует. |
| Смысл | Отвечает на вопрос, которого нет в каталоге, **или** закрывает географию, которой нет у текущего SKU. Не дублирует глобальный USGS под новым именем. |
| Честность | **Продукт предупреждения** ≠ **in-situ** датчик. Публичный **AIS** ≠ свой edge AIS. **VIIRS-точка** ≠ периметр пожара ≠ «бедствие». |

**ATLAS Analyst** может flyTo и открывать карточки. Нельзя: приказывать эвакуацию, называть GDACS классификатором FIRMS, считать пустой tsunami CAP «всё спокойно», выдавать Open-Meteo за in-situ.

---

## Live now — спрашивайте сегодня

| Вопрос оператора / агента | Слои | Что такое LIVE-**показание** | Нельзя утверждать |
|---------------------------|------|------------------------------|-------------------|
| Где сейчас тепловые детекции? | Wildfire `firms-fire-01` | Кластер **VIIRS-точек** NASA FIRMS. Цитировать NASA FIRMS. | Периметр пожара, площадь гари или «это бедствие». |
| Какие пожары Европы в текущем списке EFFIS? | EFFIS `effis-01` | Текущие пожары Copernicus EMS / JRC, **CC BY 4.0**. | Глобальная замена VIIRS; это не FIRMS. |
| Есть ли открытое природное событие NASA (вулкан, шторм, лёд, …)? | Natural events `eonet-01` | Событие каталога EONET. Цитировать NASA EONET. | Трек NHC; не **тропический циклон**-advisory. |
| Есть ли в США CAP паводка / flash-flood? | Flood `nws-flood-01` | **CAP** NWS, **предупреждение о наводнении** (PD США). | Англия / глобальная модель паводка. GloFAS не скрейпим. |
| Каковы уровень/расход на этом речном **якоре**? | Rivers | **In-situ** **показание** USGS / ECCC / SMHI. | **Предупреждение о наводнении**. Gage height — не **качество воды**. |
| Какова непрерывная химия воды в этом bbox США? | Water quality `usgs-wq-01` | Все текущие станции USGS в bbox; pH, температура, растворённый кислород и проводимость; сохраняются provisional/quality metadata. | Уровень реки, лабораторная проба или покрытие вне США. |
| Каков национальный радиационный baseline EPA и где есть отклонение? | EPA RadNet `radnet-*` | Все 140 официальных координат мониторов с утверждёнными почасовыми gamma-показаниями. | Прогноз дозы или объявление ЧС. |
| Какой активный DART-уровнемер ближе к океанскому событию? | DART `noaa-dart-01`, `dart-*` | Все 43 активные станции зафиксированного каталога NDBC в официальных координатах. | Предупреждение о цунами или команда эвакуации. |
| Находится ли **этот североамериканский объект** внутри дымового полигона сейчас? | `atlas.smoke.operations@v1` | Точный point-in-polygon по полной подписанной выгрузке HMS для **Северной Америки** (отверстия и 180-й меридиан учтены) + PM2.5/AQI в той же точке. Отказ при неполной выгрузке или вне географии HMS. | Приказ об эвакуации, медицинское заключение, регуляторный монитор или глобальное покрытие дымом. |
| Есть ли американский **продукт предупреждения** о цунами? | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory. Часто **пусто → offline**. | Мареограф. Пустое — не «на Земле нет цунами». |
| Каков уровень воды на этом приливном **якоре**? | Tide | **In-situ** NOAA CO-OPS / UHSLC. | **Продукт предупреждения** о цунами. |
| Какие суда в **водах Финляндии**? | Public AIS `fintraffic-ais-01` | Снимок Fintraffic Digitraffic, **CC BY 4.0**. | Глобальный AIS, GFW, AISStream или свой `gaia.ais.read@v1`. |
| Какие борта видел **наш** приёмник? | Edge traffic `feeder-adsb-01` | Свой ingest dump1090. Offline до пуша. | ADSBx / OpenSky / публичный агрегатор. |
| Каков crowd PM у этой точки (или любой lat/lon)? | Air `sc-01` / `sc-{slug}` | Sensor.Community area, **ODbL** — цитировать. Покупатель может передать `latitude`/`longitude` на `gaia.air.read@v1`. Mesh — городские якоря. Пусто → offline. | Референсная станция AQ; все SDS011 на Земле; модельный AQ Open-Meteo. |
| Сообщил ли USGS о землетрясении (обычно M≥2.5)? | Earthquakes `usgs-quake-01` | Событие USGS GeoJSON, lat/lon. | Плотность Euro-Med или местный каталог Австралии. |
| Локальные землетрясения Новой Зеландии? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | Глобальный каталог. |
| Каков расход/уровень на Рейне (клик по посту)? | Rivers `pegel-*-01` mesh | WSV **PEGELONLINE** in-situ (DL-DE-Zero). Один кликабельный **пин** на федеральный пост. | **Предупреждение о наводнении**; посты NL/FR. |
| Каков **METAR** в этом аэропорту (клик по аэропорту)? | Aviation `metar-*-01` mesh | AviationWeather.gov METAR (PD США). Один **пин** на ICAO. | Наземный ASOS NWS; прогноз **TAF**. |
| Какова **дорожная погода** на финских трассах (клик по станции)? | Road `fintraffic-road-01` → `road-st-*` | Digitraffic road weather, **CC BY 4.0**. Родитель кластера раскрывает **пины** во viewport. | AIS, EU traffic или NWS. |
| Где сейчас поезда в Финляндии (клик по поезду)? | Rail `fintraffic-rail-01` → `rail-tr-*` | Digitraffic train locations, **CC BY 4.0**. | EU rail или дорожный TMS. |
| Где в США сильнее **засуха** на этой неделе (клик по штату)? | Drought `usdm-01` → `drought-st-*` | **USDM** weekly state stats — attribute NDMC / USDA / NOAA / NASA. | Влажность почвы или CAP NWS. |
| Какие штаты США в засухе на этой неделе? | Drought `usdm-01` | U.S. Drought Monitor — attribute NDMC / USDA / NOAA / NASA. | Пин влажности почвы; flood CAP. |
| Сообщил ли GeoShake community-событие? | Earthquakes `geoshake-01` | Каталог GeoShake **CC BY 4.0** (пусто → offline). | Замена USGS/EMSC. |
| Есть ли канадский публичный CAP-алерт? | Alerts `naad-01` | **NAAD** Atom **CAP-CP** — цитировать issuer (напр. Environment Canada). Пусто ≠ «всё спокойно». | NWS CAP. |
| Каковы солнечный ветер / рентген GOES / DONKI сейчас? | Space weather `swpc-*` / `donki-01` | NOAA **SWPC** PD + NASA **DONKI** open. | Эвакуация; подмена только Kp без указания источника. |
| Каков расход/уровень на **английской** реке (клик по посту)? | Rivers `ea-*-01` mesh | EA Hydrology **in-situ** (OGL v3). Предпочтительны посты с Q и уровнем. | **Предупреждение** EA (`ea-flood-01`); SEPA/NRW; PEGELONLINE. |
| Каков расход/уровень на **NL Рейн/Waal/IJssel** (клик Lobith или Tiel)? | Rivers `rws-*-01` mesh | Rijkswaterstaat WaterWebservices **in-situ** (**CC0**). Lobith/Tiel — Q+уровень; часть постов только уровень. | PEGELONLINE DE; EA England; flood CAP. |
| Каковы уровень и объём этого водохранилища USACE (клик по озеру)? | Reservoir `usace-*-01` mesh | USACE CWMS Elev + Stor (PD США). Два коммерческих поля на пин. | **Продукт предупреждения** о наводнении; один только USGS stage. |
| Какова живая синоптика в **Ирландии** (клик по станции)? | Weather `met-ie-01` → `wx-ie-*` | Наблюдения Met Éireann (**CC BY 4.0** — полная атрибуция). T/RH/ветер/дождь/давление. | Open-Meteo как in-situ; UK/NL посты. |
| Каков расход/уровень на **французской** реке (клик по посту)? | Rivers `hubeau-*-01` mesh | Hub'Eau hydrométrie **in-situ** (**Etalab OL 2.0**). Q + уровень, когда публикуется. | **Vigicrues**; PEGELONLINE DE; eHYD AT. |
| Каков расход/уровень на **австрийской** реке (клик по посту)? | Rivers `ehyd-*-01` mesh | eHYD / BMLUK `pegel_aktuell` **in-situ** (**CC BY 4.0** — «Datenquelle: ehyd.gv.at»). | PEGELONLINE DE; Hub'Eau FR; flood CAP. |
| Какова in-situ погода в **Швеции**? | Weather `smhi-wx-*-01` | SMHI MetObs (**CC BY 4.0**). T/RH/давление/ветер. | `smhi-hydro-01`; Open-Meteo как in-situ. |
| Какова in-situ погода в **Сингапуре**? | Weather `sg-wx-*-01` | Singapore NEA / data.gov.sg (**Open Data Licence**). Ветер (+ T/RH/дождь). | Open-Meteo как in-situ; PSI как станция. |
| Каков региональный **Singapore PSI / PM2.5**? | Air `sg-psi-*-01` | NEA PSI (**Open Data Licence**). Региональный 24h индекс. | Reference-grade монитор; OpenAQ. |
| Какова in-situ погода в **Гонконге**? | Weather `hko-wx-*-01` | HKO `rhrread` (**DATA.GOV.HK**). Температура места (+ RH на Observatory). | Open-Meteo как in-situ. |
| Каков in-situ **Belgium PM2.5**? | Air `be-aq-*-01` | IRCELINE SOS (**CC BY 4.0**). | OpenAQ; Sensor.Community. |
| Какова in-situ погода в **Испании**? | Weather `aemet-wx-*-01` | AEMET OpenData (**Fuente: AEMET**). Нужен `GAIA_AEMET_API_KEY`. | Open-Meteo как in-situ. |
| Какова in-situ погода в **Швейцарии**? | Weather `ch-wx-*-01` | MeteoSwiss OGD (**CC BY 4.0**). | Open-Meteo как in-situ. |
| Каков расход / геодезический уровень на **швейцарской** реке? | Rivers `bafu-*-01` | BAFU/FOEN LINDAS (**OGD-CH Open-Use**). Q + м над ур. моря. | dangerLevel; PEGELONLINE; eHYD; Hub'Eau. |
| Какова in-situ погода на **Тайване**? | Weather `cwa-wx-*-01` | CWA OpenData (**OGDL 1.0**). Нужен `GAIA_CWA_API_KEY`. | Open-Meteo как in-situ. |
| Какова in-situ погода во **Франции** (станция)? | Weather `mf-wx-*-01` | Météo-France DPObs (**Etalab OL 2.0**). Нужен `GAIA_METEOFRANCE_APPLICATION_ID`. | Hub'Eau; Open-Meteo как in-situ. |
| Какова in-situ погода в **Эстонии**? | Weather `ee-wx-*-01` | Estonian Weather Service XML (**CC BY 4.0**). | Open-Meteo как in-situ. |
| Какова in-situ погода в **Исландии**? | Weather `is-wx-*-01` | IMO AWS (**ODC-By**). | Open-Meteo как in-situ. |
| Каков **Hong Kong AQHI** (клик по посту)? | Air `hk-aqhi-*-01` | EPD AQHI (**DATA.GOV.HK**). 1–10 / 10+. | PM2.5; погода HKO; IRCELINE. |

### P12 — новые LIVE-пины и полевые SKU

| Вопрос | Пин / SKU | Источник и граница утверждения |
|---|---|---|
| Какая in-situ погода в **Австрии**? | `at-wx-*-01` | GeoSphere Austria TAWES, **CC BY 4.0**; наблюдения, не платный прогноз. |
| Какая in-situ погода в **Литве**? | `lt-wx-*-01` | LHMT Meteo.lt, **CC BY-SA 4.0**; не используйте `/forecasts`. |
| Каков уровень Немана или Нериса? | `lt-hydro-*-01` | Измеренный LHMT hydro, **CC BY-SA 4.0**; сантиметры приводятся к метрам. |
| Какая in-situ погода в **Латвии**? | `lv-wx-*-01` | LVGMC HVD CSV, **CC0-1.0**; данные старше 6 часов → offline. |
| Каков уровень Даугавы или Лиелупе? | `lv-hydro-*-01` | LVGMC hydro, **CC0-1.0**; это не предупреждение о наводнении. |
| Есть ли предупреждение Vigicrues во французском бассейне? | `vic-*-01` | VIC WARNING, **Etalab OL 2.0**; зелёный/пустой ответ не означает «всё безопасно», не Hub'Eau. |
| Какова национальная производственная углеродная интенсивность Франции? | `rte-grid-01` | RTE éCO2mix, **Etalab OL 2.0**; только производство, без импорта и жизненного цикла. |
| Каков уровень воды у ирландского поста OPW? | `ie-river-*-01` | waterlevel.ie, **CC BY 4.0**; уровни, не flood CAP. |
| Какая in-situ погода в **Японии**? | `jp-wx-*-01` | JMA AMeDAS, Public Data License; цитируйте JMA, это не прогноз. |
| Сообщило ли JMA о землетрясении? | `jma-quake-01` | Официальный JMA `list.json`; не p2pquake и не замена USGS/EMSC. |
| Какой тайфун активен в северо-западной части Тихого океана? | `jma-typhoon-01` | JMA targetTc, Public Data License; пустой сезон → offline, не NHC/JTWC. |
| Какая in-situ погода в **Чехии**? | `cz-wx-*-01` | ČHMÚ climate-now, **CC BY 4.0**; не Open-Meteo как станция. |
| Какая in-situ погода в **Корее**? | `kr-wx-*-01` | KMA ASOS, Public Nuri Type 1; нужен `GAIA_KMA_SERVICE_KEY`, не AirKorea. |
| Есть ли наблюдаемое наводнение Copernicus? | `gfm-flood-01` | Copernicus GFM, **CC BY 4.0**; нужен `GAIA_GFM_TOKEN`, не GloFAS-прогноз. |
| Каков робастный консенсус температур Estonia EWS сейчас? | `atlas.field.consensus@v1`, mesh `ee-wx` | Медиана / biweight LIVE in-situ показаний с квитанцией; не прогноз и не национальная официальная цифра. |
| Где пространственный GP-постериор текущего снимка Estonia EWS? | `atlas.field.posterior@v1`, mesh `ee-wx` | RBF GP интерполирует текущие данные с дисперсией; не прогноз и не national nowcast. |
| Какие рейнские посты опрашивать без cherry-picking? | `atlas.mesh.sample@v1`, mesh `pegel` | Halton-подмножество LIVE PEGELONLINE; воспроизведите с тем же `skip`, это не Sortes ECVRF. |
| Распалась ли бельгийская сеть AQ на кластеры? | `atlas.field.shape@v1`, mesh `be-aq` | H0-компоненты по радиусу для LIVE IRCELINE; не AQI и не петли Betti-1. |

**Стартеры для Analyst (live now)**

- «Выключи все слои кроме Wildfire. Какая ярчайшая **VIIRS-точка** FIRMS в этом **viewport**? Цитируй NASA FIRMS.»
- «`nws-flood-01` online? Если да — процитируй заголовок CAP. Если offline — скажи, что **продукт предупреждения** пуст; не делай вывод о безопасности.»
- «Ближайший LIVE речной **пин** к этому клику — только **показание**, не **предупреждение о наводнении**.»
- «Финский Public AIS: сколько судов в кадре? Кредит Fintraffic. Не называй это глобальным AIS.»

Примеры **watchbox**: слой `fire` + bbox; `flood` + bbox США; `ais` + Балтика.

---

## Proposed — sell

Шесть аудированных SKU (NHC, EMSC, EA flood, PTWC, Kystverket AIS, ADSB.lol) **подключены** — см. **Live now** выше. На карте после редеплоя **GAIA, затем ATLAS**.

---

## Hold — пока не продаём

### 1. «Какой **тропический циклон** активен в Атлантике / восточной Пацифике?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | новый `gaia.cyclone.read@v1` (не навешивать на EONET) |
| **Upstream** | NOAA NHC `CurrentStorms.json` — PD США |
| **География** | Атлантика + восточная Пацифика. Не северо-западная Пацифика (тайфун / 台风). Бассейн NHC: ураган. |
| **Продажа / встраивание** | Да. Пустой сезон → offline / без дебета, как tsunami CAP. |
| **Analyst** | «Перечисли активные шторма NHC с lat/lon и интенсивностью. Это не EONET и не глобальный циклон-фид.» |
| **Нельзя** | Отвечать «тайфун у Японии» из NHC. |

### 2. «Трясёт ли Европу гуще, чем USGS M≥2.5?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | существующий `gaia.quake.read@v1`, новый `device_id` `emsc-01` |
| **Upstream** | EMSC FDSN `seismicportal.eu` — **CC BY 4.0** ([страница сервиса](https://www.seismicportal.eu/fdsn-wsevent.html)) |
| **География** | Плотный Euro-Mediterranean; глобально M≥4.5. Цитировать EMSC. Параметры предварительные. |
| **Продажа / встраивание** | Да. Отдельный **пин** от `usgs-quake-01`. |
| **Analyst** | «Сравни EMSC и USGS в этом **viewport**. Не выбирай победителя; цитируй оба `source`.» |
| **Нельзя** | Подменять USGS глобально. |

### 3. «Есть ли **предупреждение о наводнении** в Англии?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | существующий `gaia.flood.read@v1`, новый `ea-flood-01` (опционально речные **якоря** на `gaia.river.read@v1`) |
| **Upstream** | Environment Agency real-time API — **OGL**, без ключа. Attribution: данные EA о паводке и уровне рек. |
| **География** | **Англия**, не UK (Шотландия SEPA / Уэльс NRW — отдельно). |
| **Продажа / встраивание** | Да. Дополняет NWS CAP только по США. |
| **Analyst** | «**Продукт предупреждения** EA для Англии. Это не **in-situ** уровень Темзы, пока речной **пин** не online.» |
| **Нельзя** | Говорить «паводок UK» или скрейпить GloFAS. |

### 4. «Есть ли тихоокеанский **продукт предупреждения** о цунами?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | существующий `gaia.tsunami.read@v1`, новый `ptwc-01` |
| **Upstream** | PTWC / `tsunami.gov` Atom или CAP — PD США |
| **География** | Тихий океан (бассейны PTWC). Дополняет US-центричный NWS CAP. |
| **Продажа / встраивание** | Да. Пустая лента → offline. **Продукт предупреждения**, не мареограф. |
| **Analyst** | «Цитируй пины PTWC и NWS tsunami раздельно. Пусто ≠ все спокойно.» |
| **Нельзя** | Приказывать эвакуацию; Analyst — не национальный орган предупреждения. |

### 5. «Какие суда у Норвегии?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | существующий `gaia.ais.public.read@v1`, новый `kystverket-ais-01` (или эквивалент) |
| **Upstream** | Kystverket через BarentsWatch — **NLOD**, коммерция с атрибуцией. Бесплатная регистрация OpenID (тот же класс, что `GAIA_KNMI_API_KEY`). |
| **География** | Воды Норвегии, не Финляндия, не глобально. |
| **Продажа / встраивание** | Да, после пина REST-хоста + токена в **allowlist**. |
| **Analyst** | «Норвежский публичный **AIS**. Кредит Kystverket / BarentsWatch. Не Fintraffic и не свой edge AIS.» |
| **Нельзя** | Сливать с `fintraffic-ais-01` в один «европейский AIS». |

### 6. «Какой борт над точкой — без нашего приёмника?»

| | |
|--|--|
| **Статус** | Proposed — sell |
| **SKU** | новый `gaia.adsb.public.read@v1` (параллель публичному AIS; **не** `gaia.adsb.read@v1`) |
| **Upstream** | [ADSB.lol](https://www.adsb.lol/docs/open-data/api/) `api.adsb.lol` — **ODbL 1.0** |
| **География** | Покрытие фида, не национальный мандат. |
| **Продажа / встраивание** | Да, с той же честностью, что Sensor.Community: коммерческое **показание** можно; публичная производная БД — **ODbL share-alike**. Изолировать производную БД ADS-B. Пин только `api.adsb.lol`. |
| **Analyst** | «Публичный ADS-B через ADSB.lol (ODbL). Не наш dump1090. Не OpenSky / ADSBx.» |
| **Нельзя** | Молча перебирать авиаагрегаторы. |

---

## Hold — пока не продавать

### EPA UV как платный «операционный стол»

**Hold для sales-copy юзкейса** (реле может быть LIVE на карте).

- Заголовок пина — один `uv_index` (макс. прогноза по ZIP). Не проходит бар: один скаляр ≠ multi-signal desk.
- Это почасовой **прогноз** EPA, не in-situ пиранометр.
- Разблокировать, когда пин/кластер продаёт ≥2 полезных поля без выдуманных приборов.

**Замена live now:** погода Met Éireann / NWS / Open-Meteo; не продавать UV отдельно как «безопасность площадки».

### GDACS как «бедствие, а не VIIRS-точка»

**Hold.** Вопрос оператора осмысленный, источник по нашим правилам продавать ещё нельзя.

- Официальные [GDACS Terms of use (март 2025)](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) **не** выдают CC BY 4.0. Это модельные оценки воздействия, «as is»; алерты **нельзя** использовать для решений без подтверждения уполномоченных органов.
- GDACS **не** классифицирует **VIIRS-точку** FIRMS. Это многоопасный **продукт предупреждения** / модель UN/EC про международную помощь — другой класс утверждения, чем тепловые детекции и EFFIS.
- Сторонние страницы с «CC BY 4.0» — не пин. Тот же бар, из-за которого EMSC не входил в код, пока страница FDSN не написала CC BY 4.0.

**Замена live now:** FIRMS (детекции) + EFFIS (текущие пожары ЕС) + EONET (события NASA). Analyst держит три `source` раздельно.

### Землетрясения Geoscience Australia как «трясёт ли Австралию?»

**Hold** для живого HTTPS-**ретранслятора**, не для идеи.

- data.gov.au «Recent Earthquakes» — **CC BY 3.0 Australia**, но запись каталога ≠ проверенный allowlist GeoJSON/WFS.
- USGS уже сообщает австралийские события выше своего порога магнитуды. Это честный ответ **Live now**.
- Разблокировать, когда endpoint GA NEAC закреплён так же, как GeoNet (`api.geonet.org.nz`).

### USGS **качество воды** — LIVE-сеть

Подключена текущая OGC-коллекция непрерывных измерений: buyer bbox возвращает все совпавшие станции, каждая становится отдельной координатой показания. Сохраняются время, provisional/approval и qualifier; `gage_height_m` по-прежнему **не** качество воды. География — США.

---

## Что Analyst обязан отказать

| Промпт | Почему |
|--------|--------|
| «Объяви эвакуацию / отбой по этому берегу.» | ATLAS не орган предупреждения. Процитировать **продукт предупреждения** или сказать offline. |
| «Этот пиксель FIRMS — бедствие GDACS?» | Разные классы утверждений; GDACS в **Hold**. |
| «Глобальный AIS / глобальная молния / официальная погода BoM AU.» | Нет лицензии на платный SKU (GFW NC, Blitzortung NC, BoM FTP non-commercial). |
| «Качество воды этой английской реки из USGS.» | Не та география: подключённая непрерывная сеть USGS покрывает США, не Англию. |
| «Тайфун из NHC.» | Не тот бассейн. |

---

## Связанные документы

- Карта оператора: [`GUIDE.ru.md`](GUIDE.ru.md)
- Лицензии ретрансляторов: [`gaia/docs/i18n/LIVE-RELAYS.ru.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.ru.md)
- Глоссарий (**watchbox**, **продукт предупреждения**, **AIS**, **ADS-B**, **тропический циклон**): [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
