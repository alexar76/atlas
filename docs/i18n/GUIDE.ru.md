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

Актуальный список всех **53 слоёв**, точные цвета, значения и примеры устройств:
[легенда карты ATLAS](LEGEND.ru.md). Она генерируется из того же runtime-каталога,
что и карта. В каталоге сейчас **970 настроенных устройств**; плотные и событийные
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
| Грунтовые воды | `usgs-groundwater-01` | Три пилотные скважины USGS в штатах Мэн, Нью-Йорк и Кентукки. Глубина от местной поверхности земли в метрах, положительное направление вниз. ATLAS показывает время замера и статус проверки USGS. Замеры старше 24 часов скрываются. |
| Грунтовые воды Hub’Eau | `hubeau-groundwater-01` | Восемь французских пилотных скважин передают глубину до воды от измерительной отметки и высоту уровня в системе NGF. В карточке видны время замера и система отсчёта каждого значения. |
| Речной прогноз NOAA NWPS | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` | Карточка показывает наивысший уровень среди доступных точек прогноза на ближайшие 72 часа, время выпуска и время пика. Высота указана относительно местного нуля поста. |
| Мареографы Environment Agency | `ea-tide-e70039`, `ea-tide-e72639`, `ea-tide-e70539`, `ea-tide-e70739`, `ea-tide-e73839` | Прибрежные станции Великобритании измеряют средний уровень моря в метрах относительно нуля Ordnance Datum Newlyn (mAOD). |
| Дорожные события Fintraffic | `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` | Дорожные сообщения и работы в Финляндии показываются на затронутых участках с указанием срока действия. |
| NOAA G-AIRMET | `awc-gairmet-01` | На карте видны полигоны и линии авиационного прогноза для США, тип опасности, время выпуска и время действия. |
| Дорожные сообщения и перекрытия NDW | `ndw-road-srti-01`, `ndw-road-closures-01` | Слой `road_events` показывает предупреждения о дорожной безопасности и временные перекрытия в Нидерландах с геометрией затронутых участков. Данные в подписанной сводке действительны пять минут с момента публикации. У каждой меры есть собственный период действия. [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) |
| Балтийские волновые буи FMI | `fmi-marine-103976`, `fmi-marine-108126`, `fmi-marine-108499`, `fmi-marine-134220`, `fmi-marine-134221`, `fmi-marine-134246` | Шесть буёв в слое `marine` передают значительную высоту волн. В карточке также видны пиковый период, направление, откуда приходят волны, и температура воды, если они измерены в то же время. Метка времени указывает начало замера волн. Данные устаревают через два часа. [FMI · CC BY 4.0](https://en.ilmatieteenlaitos.fi/download-observations-questions) |
| Снежный покров USDA NRCS SNOTEL | `snotel-335`, `snotel-415` | Слой `snow` показывает почасовую высоту снежного покрова и его водный эквивалент в сантиметрах на станциях Berthoud Summit и Copper Mountain в Колорадо. GAIA объединяет замеры за один час, если они прошли автоматический контроль качества и получены не более шести часов назад. [USDA NRCS · общественное достояние США](https://catalog.data.gov/dataset/snowpack-telemetry-network-snotel) |
| Морские наблюдения SMHI | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` | `ocean_obs` · Четыре ряда измерений на заданных глубинах на трёх шведских станциях. В зависимости от станции и глубины карточка показывает солёность в PSU, растворённый кислород в мл/л или скорость и направление течения. Измерения в карточке сделаны в одно время и доступны до трёх часов. [SMHI · CC BY 4.0](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) |
| Прогноз дыма ECCC | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` | `smoke_forecast` · Три ячейки модели рядом с Сиэтлом, Торонто и Калгари. Карточки показывают прогноз суммарной приземной концентрации PM₂.₅ внутри смоделированного шлейфа дыма в мкг/м³ на ближайший полный час UTC, время запуска модели и время прогноза. Запуск модели должен быть не старше 18 часов. [ECCC · MSC End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) |
| NOAA SWPC D-RAP | `swpc-drap-01` | `hf_absorption` · Глобальная модель показывает верхнюю частоту, затронутую поглощением радиоволн на 1 дБ в области D ионосферы. На общем плане 900 ячеек размером 6° × 12° показывают максимальные значения в МГц. При увеличении доступны исходные значения всех 8 100 ячеек размером 2° × 4°. Данные действуют 15 минут. [NOAA SWPC](https://www.swpc.noaa.gov/products/d-region-absorption-predictions-d-rap) |
| Мощность дозы гамма-излучения BfS | `bfs-odl-01` | `radiation` · Немецкие станции показывают проверенные почасовые значения мощности амбиентного эквивалента дозы гамма-излучения в нЗв/ч. В карточке указано время окончания часа наблюдения. Измерения доступны до двух часов. [BfS · DL-DE-BY 2.0](https://www.imis.bfs.de/geoportal/resources/sitepolicy.html) |
| Уровень прибрежных вод GeoNet | `geonet-coastal-auct`, `geonet-coastal-wlgt`, `geonet-coastal-taut`, `geonet-coastal-gist`, `geonet-coastal-jbtt` | `tide` · Пять станций в Новой Зеландии показывают высоту воды в метрах над местным датчиком давления. Измерения доступны до пяти минут. [GeoNet · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) |
| Речные наблюдения ČHMÚ | `chmi-river-042000`, `chmi-river-101800`, `chmi-river-200100` | `river` · Три чешских гидропоста показывают предварительные замеры уровня и расхода воды, а также температуру, если её измерили в то же время. Измерения доступны до двух часов. [ČHMÚ · CC BY 4.0](https://www.chmi.cz/-/kde-najdu-otev%C5%99en%C3%A1-data-%C4%8Dhm%C3%BA-) |
| Местоположение поездов Entur | `entur-rail-vyg-01` | `rail` · Карта показывает последние наблюдаемые координаты поездов Vy в Норвегии и их линию, если она известна. Точка исчезает по истечении срока источника или через пять минут, в зависимости от того, что наступит раньше. [Entur · NLOD](https://developer.entur.no/terms-of-service) |
| Перебои электроснабжения UK Power Networks | `ukpn-live-faults-01` | `power_outages` · Текущие аварии в зоне обслуживания оператора. В карточке видны примерный район отключения, число затронутых абонентов и ожидаемое время восстановления, если оператор его сообщил. Снимок устаревает через 30 минут. [UK Power Networks · CC BY 4.0](https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults) |
| Просвет под мостами NOAA PORTS | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` | `bridge_clearance` · Датчики на трёх мостах США передают предварительные замеры вертикального расстояния от поверхности воды до фиксированной точки на мосту в метрах. В карточке видны стандартное отклонение выборки и флаги источника. Замеры устаревают через 18 минут. Для решения о проходе используйте официальные данные NOAA PORTS и навигационные карты. [NOAA NOS CO-OPS](https://opendap.co-ops.nos.noaa.gov/erddap/info/IOOS_Air_Gap/index.html) |
| Дрейфующие буи NOAA AOML | `aoml-drifters-01` | `ocean_drifters` · Глобальная сеть передаёт последние наблюдаемые координаты и температуру поверхности моря для каждого буя. Давление на уровне моря отображается, если его сообщил буй. Замеры устаревают через шесть часов. [NOAA AOML / OSMC · CC0 1.0](https://osmc.noaa.gov/erddap/info/OSMC_flattened/index.json) |
| Велопрокат Bike Share Toronto | `toronto-bikeshare-01` | `bikeshare` · Карточки станций показывают доступные велосипеды, электровелосипеды при наличии данных, свободные доки и доступность выдачи и возврата. Отчёты устаревают через пять минут. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Дорожные ограничения Торонто | `toronto-road-restrictions-01` | `road_events` · Городские сообщения показывают точку или участок дороги на время действия ограничения, включая повторяющиеся по расписанию. Снимок источника устаревает через 15 минут. У каждого сообщения есть свой интервал действия. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Речные наблюдения ARSO | `arso-river-1060`, `arso-river-3660`, `arso-river-5078`, `arso-river-8080` | `river` · Четыре словенских гидропоста передают предварительные замеры уровня в метрах над местным нулём поста и расхода в м³/с. В карточке также видна температура воды, если её измерили в то же время. Замеры устаревают через два часа. [ARSO](https://kazalci.arso.gov.si/en/content/legal-note) |
| Уровень прибрежных вод Kartverket | `kartverket-tide-bgo`, `kartverket-tide-osl`, `kartverket-tide-svg`, `kartverket-tide-tos`, `kartverket-tide-trd` | `tide` · Пять норвежских станций показывают наблюдаемый уровень моря в метрах относительно национальной системы высот NN2000. Замеры устаревают через два часа. [Kartverket · CC BY 4.0](https://vannstand.kartverket.no/tideapi_en.html) |
| Точки возможного подтопления | `usgs-rtfi-01` | Уровень ближайшего гидропоста USGS превысил обследованный порог для дороги, моста, здания или другой точки. Это предварительный сигнал возможного подтопления. Пустая выдача означает отсутствие подходящих срабатываний в охваченных точках. |
| DART | `noaa-dart-01`, `dart-*` | Все 43 активные станции из зафиксированного официального каталога NDBC |
| EPA RadNet | `radnet-*` | Все 140 официальных координат мониторов EPA, а не три демо-города |
| Статус NEXRAD | `nexrad-status-01` | Каждая станция WSR-88D в собственной координате; статус, не отражаемость |
| Координатные сетки/модели | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | `lat`/`lon` покупателя; ATLAS использует возвращённую координату исходной/расчётной ячейки |

Для данных о дорожных ограничениях и велопрокате Торонто используется формулировка лицензии. «Contains information licensed under the Open Government Licence – Toronto.» [Лицензия](https://open.toronto.ca/open-data-licence/)

### Зарядки, опасные явления и полевые наблюдения

| Источник | GAIA | ATLAS | Данные и ограничения | Источник и условия |
| --- | --- | --- | --- | --- |
| Зарядки NDW DOT-NL | `gaia.ev.charging.read@v1` · `ndw-ev-charging-01` | `ev_charging` | Публичные зарядные станции Нидерландов сообщают число свободных и всех разъёмов по типам и мощность. Запрос по умолчанию охватывает Утрехт. Региональный запрос ограничен 4 квадратными градусами. Страница Hub содержит до 500 станций, для продолжения нужен идентификатор снимка. Снимок действителен четыре минуты. | [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) · [API GeoJSON](https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/) |
| Пожары и периметры BC Wildfire | `gaia.fire.perimeters.read@v1` · `bc-wildfire-01` | `wildfire_perimeters` | Для активных пожаров в Британской Колумбии показаны статус и последний опубликованный периметр, если он есть. Время обновления набора и дата каждого периметра указаны отдельно. Снимок набора действителен один час. | [BC Wildfire Service · OGL–BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) · [Периметры](https://open.canada.ca/data/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1) |
| Измерения пыльцы MeteoSwiss A7 | `gaia.pollen.read@v1` · `ch-pollen-*` | `pollen` | Пятнадцать зарегистрированных автоматических станций сообщают почасовую концентрацию семи типов пыльцы в зёрнах на кубический метр. Измеренный ноль сохраняется. Наблюдения действительны два часа. | [Source: MeteoSwiss · CC BY 4.0](https://opendatadocs.meteoswiss.ch/general/terms-of-use) · [A7](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations) |
| Морские буи Ирландии | `gaia.marine.read@v1` · `ie-buoy-m2`, `ie-buoy-m3`, `ie-buoy-m5`, `ie-buoy-m6` | `marine` | Четыре пилотных буя сообщают высоту, период и направление волн, температуру воды и ветер при наличии данных. Наблюдения действительны два часа. Код качества 0 означает неизвестное качество, код 1 означает хорошее качество. | [Marine Institute and Met Éireann · CC BY 4.0](https://erddap.marine.ie/erddap/info/IWBNetwork/index.html) |
| Волномерные буи AODN/IMOS | `gaia.marine.read@v1` · `au-wave-apollo-bay`, `au-wave-wilsons-prom`, `au-wave-wooli` | `marine` | Три пилотных буя сообщают значительную высоту волн, пиковый период и направление, откуда приходят волны, при наличии данных. GAIA принимает код качества 1. Наблюдения действительны два часа. | [AODN / IMOS · CC BY 4.0](https://registry.opendata.aws/aodn_wave_buoy_realtime_nonqc/) |
| Вулканы и камеры GeoNet | `gaia.volcano.read@v1` · `geonet-volcano-01` | `volcano` | Для двенадцати вулканов Новой Зеландии показаны текущий уровень тревоги и авиационный цветовой код. Статус действителен 30 минут после получения. У доступных кадров есть собственное время съёмки, срок показа составляет 30 минут. | [GeoNet / Earth Sciences New Zealand and sponsors · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) · [Камеры](https://doi.org/10.21420/vq6s-w222) |
| Сообщения о сильных грозах NOAA SPC | `gaia.storm.reports.read@v1` · `noaa-spc-storm-reports-01` | `storm_reports` | Предварительные сообщения о торнадо, граде и сильном ветре в США отображаются за последние 24 часа. У каждой точки указано время события по сообщению источника. | [NOAA/NWS SPC · U.S. public domain](https://www.weather.gov/disclaimer) · [CSV](https://www.spc.noaa.gov/climo/reports/today.csv) |
| Бюллетени о вулканическом пепле Washington VAAC | `gaia.volcanic.ash.read@v1` · `noaa-vaac-ash-01` | `volcanic_ash` | У опубликованных контуров пепла указаны высоты, время выпуска и время наблюдения или действия прогноза. Бюллетень действует до времени следующего выпуска или до истечения семи часов после выпуска, в зависимости от того, что наступит раньше. | [NOAA Washington VAAC](https://ospo.noaa.gov/products/atmosphere/vaac/messages.html) · [Условия NOAA](https://www.noaa.gov/office-education/outreach-communication/faq) |
| Тепловые аномалии Digital Earth Australia | `gaia.fire.hotspots.read@v1` · `dea-hotspots-01` | `fire_hotspots` | Спутниковые тепловые аномалии в Австралии, включая данные Himawari-9, отображаются за последние три часа в запрошенной области. Карта загружает до 800 точек и отмечает неполный охват. | [Geoscience Australia · CC BY 4.0](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/) · [Набор DEA Hotspots](https://pid.geoscience.gov.au/dataset/ga/111881) |

Данные Британской Колумбии сопровождаются атрибуцией «Contains information licensed under the Open Government Licence – British Columbia.» Для данных австралийских буёв используется атрибуция «Data was sourced from Australia’s Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)».

Переключатель **«Радар NOAA»** на полной карте включает растр базовой отражаемости NOAA/NWS MRMS для континентальной части США, Аляски, Гавайев, Карибского региона и Гуама. ATLAS показывает 10-минутное окно UTC до последней метки времени источника и скрывает мозаику, если эта метка старше 20 минут. Цвета соответствуют шкале отражаемости источника. Состояние станций показано в отдельном слое **«Статус NEXRAD»**. [Сервис изображений NOAA](https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer) · [Условия NWS](https://www.weather.gov/disclaimer)

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
