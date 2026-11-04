# ATLAS — guía de operador y desarrollador

**Idiomas:** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS es el **mapa de sensores** del ecosistema: clima, aire, mareas, ríos, marino, carbono de la red británica, terremotos, **incendios**, **radiación**, **interferencia GNSS**, AIS público finlandés, alertas tsunami NWS y ADS-B/AIS de borde propio opcional — sobre los relés de [GAIA](https://iot.modelmarket.dev). **Los dispositivos open-data nuevos viven en GAIA; capas del mapa, pines y watchboxes son superficies ATLAS** (no hay UI de producto separada en GAIA). Aparece como nodo **ATLAS** en [Alien Monitor](https://monitor.modelmarket.dev/) e incluye **ATLAS Analyst** (DeepSeek por defecto). Términos: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md).

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

El comprador **por lo general** no pasa lat/lon a GAIA invoke — anclajes del operador. Excepciones en el mismo SKU: `om-aq-*` y `sc-*` (Sensor.Community). Terremotos / fuego / jamming llevan lat/lon en la lectura.

## Capas

GAIA vende **lecturas** (`gaia.*.read@v1`). ATLAS es el **mapa** (capas/pines) y los **watchboxes**.

La lista actual de las **53 capas**, sus colores exactos, significado y ejemplos
de dispositivos está en la [leyenda del mapa ATLAS](LEGEND.es.md). Se genera desde
el mismo catálogo de ejecución que el mapa. El catálogo contiene actualmente
**970 dispositivos configurados**; las fuentes densas y de eventos pueden crear puntos
de lectura adicionales en ejecución.

| Capa | device_id típicos | Notas |
|------|-------------------|-------|
| Clima | `om-wx-01`, `nws-01`, mesh | + sims |
| Aire | `om-aq-01`, `osm-01`, `sta-01`, `sc-01`, `sc-{slug}`, mesh | SC: lat/lon comprador; crowd ≠ estación |
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
| Calidad del agua | `usgs-wq-01` | Observaciones latest-continuous frescas (48 h), paginadas y unidas a USGS monitoring-locations; solo estaciones con parámetros requeridos, una estación = un punto; Approved/Provisional + qualifiers; historial persistente y uptime por sondeos |
| Aguas subterráneas | `usgs-groundwater-01` | Tres pozos piloto del USGS en Maine, Nueva York y Kentucky. Profundidad en metros bajo la superficie local del terreno, con signo positivo hacia abajo. ATLAS muestra la hora de medición y el estado de aprobación del USGS. Las observaciones caducan tras 24 horas. |
| Aguas subterráneas de Hub’Eau | `hubeau-groundwater-01` | Ocho pozos piloto franceses informan de la profundidad desde la referencia de medición y de la cota del agua en NGF. La ficha muestra la hora y la referencia de cada valor. |
| Pronóstico fluvial NOAA NWPS | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` | La ficha muestra el nivel más alto entre los puntos disponibles del pronóstico de las próximas 72 horas, la hora de emisión y la hora del máximo. Las alturas se refieren al datum local de la estación. |
| Mareógrafos de Environment Agency | `ea-tide-e70039`, `ea-tide-e72639`, `ea-tide-e70539`, `ea-tide-e70739`, `ea-tide-e73839` | Las estaciones costeras del Reino Unido miden el nivel medio del mar en metros sobre Ordnance Datum Newlyn (mAOD). |
| Incidencias viales de Fintraffic | `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` | Los avisos y las obras en Finlandia muestran el tramo afectado y el periodo de validez publicado. |
| NOAA G-AIRMET | `awc-gairmet-01` | Los polígonos y líneas de previsión aeronáutica para Estados Unidos muestran el peligro y las horas de emisión y validez. |
| Avisos y cortes de carretera de NDW | `ndw-road-srti-01`, `ndw-road-closures-01` | La capa `road_events` muestra avisos de seguridad vial y cortes temporales en los Países Bajos con la geometría de los tramos afectados. Cada publicación firmada caduca cinco minutos después de su emisión. Cada medida tiene su propio periodo de validez. [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) |
| Boyas de oleaje del FMI en el Báltico | `fmi-marine-103976`, `fmi-marine-108126`, `fmi-marine-108499`, `fmi-marine-134220`, `fmi-marine-134221`, `fmi-marine-134246` | Seis boyas en `marine` informan de la altura significativa de las olas. La ficha incluye el periodo de pico, la dirección de procedencia del oleaje y la temperatura del agua cuando se midieron a la misma hora. La marca de tiempo indica el inicio del muestreo del oleaje. Las observaciones caducan a las dos horas. [FMI · CC BY 4.0](https://en.ilmatieteenlaitos.fi/download-observations-questions) |
| Manto nival de USDA NRCS SNOTEL | `snotel-335`, `snotel-415` | La capa `snow` muestra el espesor de la nieve y su equivalente en agua en centímetros a partir de mediciones horarias en Berthoud Summit y Copper Mountain, Colorado. GAIA empareja las mediciones de la misma hora que han superado el control automático de calidad y tienen como máximo seis horas de antigüedad. [USDA NRCS · dominio público de EE. UU.](https://catalog.data.gov/dataset/snowpack-telemetry-network-snotel) |
| Observaciones marinas de SMHI | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` | `ocean_obs` · Cuatro series a profundidades definidas en tres estaciones suecas. La ficha muestra la salinidad en PSU, el oxígeno disuelto en mL/L o la velocidad y dirección de la corriente, según la estación y la profundidad. Las mediciones corresponden a la misma hora y tienen una antigüedad máxima de tres horas. [SMHI · CC BY 4.0](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) |
| Pronóstico de humo de ECCC | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` | `smoke_forecast` · Tres celdas del modelo cerca de Seattle, Toronto y Calgary. La ficha muestra el pronóstico de PM₂.₅ total cerca de la superficie dentro de la pluma de humo modelada, en µg/m³, para la próxima hora en punto UTC. También indica la hora de ejecución del modelo y la hora de validez del pronóstico. La ejecución puede tener hasta 18 horas de antigüedad. [ECCC · MSC End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) |
| NOAA SWPC D-RAP | `swpc-drap-01` | `hf_absorption` · La cuadrícula global del modelo muestra la frecuencia más alta afectada por una absorción de 1 dB en la región D. La vista global muestra los máximos en MHz en 900 celdas de 6° × 12°. Al acercar el mapa se ven las muestras originales de las 8100 celdas de 2° × 4°. La cuadrícula caduca a los 15 minutos. [NOAA SWPC](https://www.swpc.noaa.gov/products/d-region-absorption-predictions-d-rap) |
| Tasa de dosis gamma ambiental de BfS | `bfs-odl-01` | `radiation` · Las estaciones alemanas muestran tasas horarias validadas de equivalente de dosis gamma ambiental en nSv/h. La ficha indica el final de la hora de observación. Los datos caducan a las dos horas. [BfS · DL-DE-BY 2.0](https://www.imis.bfs.de/geoportal/resources/sitepolicy.html) |
| Altura del agua costera de GeoNet | `geonet-coastal-auct`, `geonet-coastal-wlgt`, `geonet-coastal-taut`, `geonet-coastal-gist`, `geonet-coastal-jbtt` | `tide` · Cinco estaciones de Nueva Zelanda muestran la altura del agua en metros sobre el sensor de presión local. Los datos caducan a los cinco minutos. [GeoNet · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) |
| Observaciones fluviales de ČHMÚ | `chmi-river-042000`, `chmi-river-101800`, `chmi-river-200100` | `river` · Tres estaciones checas muestran mediciones preliminares del nivel y el caudal, además de la temperatura del agua si se midió al mismo tiempo. Los datos caducan a las dos horas. [ČHMÚ · CC BY 4.0](https://www.chmi.cz/-/kde-najdu-otev%C5%99en%C3%A1-data-%C4%8Dhm%C3%BA-) |
| Posiciones de trenes de Entur | `entur-rail-vyg-01` | `rail` · El mapa muestra posiciones observadas recientes de trenes de Vy en Noruega y su línea cuando está disponible. Cada posición caduca al vencer el plazo del proveedor o al cabo de cinco minutos, lo que ocurra primero. [Entur · NLOD](https://developer.entur.no/terms-of-service) |
| Cortes eléctricos de UK Power Networks | `ukpn-live-faults-01` | `power_outages` · Averías activas en la zona del operador. Las fichas muestran el área aproximada afectada, los clientes afectados y la hora estimada de restablecimiento cuando el operador la publica. Los datos caducan a los 30 minutos. [UK Power Networks · CC BY 4.0](https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults) |
| Distancia bajo puentes de NOAA PORTS | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` | `bridge_clearance` · Tres sensores en puentes de Estados Unidos muestran la distancia vertical preliminar entre la superficie del agua y un punto de referencia fijo del puente, en metros. Las fichas incluyen la desviación estándar de la muestra y los indicadores de la fuente. Las observaciones caducan a los 18 minutos. Para decidir un paso, consulte NOAA PORTS y las cartas náuticas oficiales. [NOAA NOS CO-OPS](https://opendap.co-ops.nos.noaa.gov/erddap/info/IOOS_Air_Gap/index.html) |
| Boyas a la deriva de NOAA AOML | `aoml-drifters-01` | `ocean_drifters` · Los informes globales muestran la última posición observada y la temperatura superficial del mar de cada boya, junto con la presión a nivel del mar cuando se comunica. Las observaciones caducan a las seis horas. [NOAA AOML / OSMC · CC0 1.0](https://osmc.noaa.gov/erddap/info/OSMC_flattened/index.json) |
| Bike Share Toronto | `toronto-bikeshare-01` | `bikeshare` · Las fichas muestran bicicletas disponibles, bicicletas eléctricas cuando se informan, anclajes libres y el estado del alquiler y la devolución. Los informes caducan a los cinco minutos. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Restricciones viales de Toronto | `toronto-road-restrictions-01` | `road_events` · Los avisos municipales muestran el punto o tramo de vía durante una restricción activa, incluidas las restricciones periódicas programadas. La instantánea de la fuente caduca a los 15 minutos. Cada aviso tiene su propio intervalo activo. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Observaciones fluviales de ARSO | `arso-river-1060`, `arso-river-3660`, `arso-river-5078`, `arso-river-8080` | `river` · Cuatro estaciones eslovenas informan del nivel preliminar en metros sobre el cero local y del caudal en m³/s. Las fichas incluyen la temperatura del agua cuando se mide al mismo tiempo. Las observaciones caducan a las dos horas. [ARSO](https://kazalci.arso.gov.si/en/content/legal-note) |
| Niveles costeros de Kartverket | `kartverket-tide-bgo`, `kartverket-tide-osl`, `kartverket-tide-svg`, `kartverket-tide-tos`, `kartverket-tide-trd` | `tide` · Cinco mareógrafos noruegos muestran el nivel costero observado en metros con respecto al datum vertical nacional NN2000. Las observaciones caducan a las dos horas. [Kartverket · CC BY 4.0](https://vannstand.kartverket.no/tideapi_en.html) |
| Puntos de posible inundación | `usgs-rtfi-01` | El nivel de una estación del USGS supera el umbral levantado para una carretera, puente, edificio u otro punto. Es un indicio preliminar de posible inundación. Un resultado vacío solo indica que ningún punto cubierto cumple los criterios. |
| DART | `noaa-dart-01`, `dart-*` | Las 43 estaciones activas del directorio oficial NDBC fijado |
| EPA RadNet | `radnet-*` | Las 140 coordenadas oficiales de monitores EPA, no tres ciudades de demostración |
| Estado NEXRAD | `nexrad-status-01` | Cada sitio WSR-88D en su coordenada; estado, no reflectividad |
| Cuadrículas/modelos por coordenada | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | `lat`/`lon` del comprador; ATLAS usa la coordenada de celda fuente/consulta devuelta |

Los datos de restricciones viales y del servicio de bicicletas compartidas de Toronto llevan esta atribución. «Contains information licensed under the Open Government Licence – Toronto.» [Licencia](https://open.toronto.ca/open-data-licence/)

### Recarga, fenómenos peligrosos y observaciones de campo

| Fuente | GAIA | ATLAS | Datos y límites | Fuente y condiciones |
| --- | --- | --- | --- | --- |
| Recarga de NDW DOT-NL | `gaia.ev.charging.read@v1` · `ndw-ev-charging-01` | `ev_charging` | Los puntos de recarga públicos de los Países Bajos indican los conectores disponibles y totales por tipo y potencia. La consulta predeterminada cubre Utrecht. Las consultas regionales abarcan hasta 4 grados cuadrados. Las páginas de Hub contienen hasta 500 puntos y se recorren con el identificador de la instantánea. Cada instantánea caduca a los cuatro minutos. | [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) · [API GeoJSON](https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/) |
| Incendios y perímetros de BC Wildfire | `gaia.fire.perimeters.read@v1` · `bc-wildfire-01` | `wildfire_perimeters` | Los incendios activos de Columbia Británica muestran su estado y el último perímetro publicado cuando está disponible. La actualización del conjunto y la fecha de cada perímetro se muestran por separado. La instantánea caduca al cabo de una hora. | [BC Wildfire Service · OGL–BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) · [Perímetros](https://open.canada.ca/data/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1) |
| Polen medido de MeteoSwiss A7 | `gaia.pollen.read@v1` · `ch-pollen-*` | `pollen` | Quince estaciones automáticas registradas miden concentraciones horarias de siete tipos de polen en granos por metro cúbico. Se conserva el valor cero medido. Las observaciones caducan a las dos horas. | [Source: MeteoSwiss · CC BY 4.0](https://opendatadocs.meteoswiss.ch/general/terms-of-use) · [A7](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations) |
| Red irlandesa de boyas meteorológicas | `gaia.marine.read@v1` · `ie-buoy-m2`, `ie-buoy-m3`, `ie-buoy-m5`, `ie-buoy-m6` | `marine` | Cuatro boyas piloto informan de la altura, el periodo y la dirección de las olas, con temperatura del agua y viento cuando están disponibles. Las observaciones caducan a las dos horas. El código de calidad 0 indica calidad desconocida y el 1 indica buena calidad. | [Marine Institute and Met Éireann · CC BY 4.0](https://erddap.marine.ie/erddap/info/IWBNetwork/index.html) |
| Boyas de oleaje australianas de AODN/IMOS | `gaia.marine.read@v1` · `au-wave-apollo-bay`, `au-wave-wilsons-prom`, `au-wave-wooli` | `marine` | Tres boyas piloto informan de la altura significativa, el periodo de pico y la dirección de procedencia del oleaje cuando están disponibles. GAIA acepta el código de calidad 1 y las observaciones caducan a las dos horas. | [AODN / IMOS · CC BY 4.0](https://registry.opendata.aws/aodn_wave_buoy_realtime_nonqc/) |
| Volcanes y cámaras de GeoNet | `gaia.volcano.read@v1` · `geonet-volcano-01` | `volcano` | Doce volcanes de Nueva Zelanda muestran su nivel de alerta actual y su código de color para aviación. El estado caduca 30 minutos después de la consulta. Las miniaturas disponibles muestran su propia hora de captura y caducan a los 30 minutos. | [GeoNet / Earth Sciences New Zealand and sponsors · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) · [Cámaras](https://doi.org/10.21420/vq6s-w222) |
| Informes locales de tormentas de NOAA SPC | `gaia.storm.reports.read@v1` · `noaa-spc-storm-reports-01` | `storm_reports` | Los informes preliminares de tornados, granizo y vientos fuertes en EE. UU. aparecen en una ventana móvil de 24 horas. Cada punto incluye la hora del fenómeno comunicada por la fuente. | [NOAA/NWS SPC · U.S. public domain](https://www.weather.gov/disclaimer) · [CSV](https://www.spc.noaa.gov/climo/reports/today.csv) |
| Avisos de ceniza volcánica del VAAC de Washington | `gaia.volcanic.ash.read@v1` · `noaa-vaac-ash-01` | `volcanic_ash` | Los polígonos publicados muestran sus límites de altitud, la hora de emisión y la hora de observación o de validez del pronóstico. El aviso caduca a la hora anunciada para el siguiente aviso o siete horas después de su emisión, lo que ocurra primero. | [NOAA Washington VAAC](https://ospo.noaa.gov/products/atmosphere/vaac/messages.html) · [Condiciones de NOAA](https://www.noaa.gov/office-education/outreach-communication/faq) |
| Focos térmicos de Digital Earth Australia | `gaia.fire.hotspots.read@v1` · `dea-hotspots-01` | `fire_hotspots` | Las detecciones térmicas por satélite en Australia, incluidas las de Himawari-9, aparecen en la zona consultada durante las últimas tres horas. El mapa carga hasta 800 detecciones e indica si la cobertura es parcial. | [Geoscience Australia · CC BY 4.0](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/) · [Conjunto DEA Hotspots](https://pid.geoscience.gov.au/dataset/ga/111881) |

Los datos de Columbia Británica llevan la atribución «Contains information licensed under the Open Government Licence – British Columbia.». Los datos de las boyas australianas llevan la atribución «Data was sourced from Australia’s Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)».

En el mapa completo, el control **Imágenes de radar de NOAA** muestra el ráster de reflectividad base NOAA/NWS MRMS para Estados Unidos continental, Alaska, Hawái, el Caribe y Guam. ATLAS presenta una ventana UTC de 10 minutos que termina en la última hora publicada y oculta el mosaico cuando esa hora tiene más de 20 minutos. Los colores siguen la paleta de reflectividad de la fuente. **Estado NEXRAD** es la capa independiente de estado de las estaciones. [Servicio de imágenes NOAA](https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer) · [Política de datos del NWS](https://www.weather.gov/disclaimer)

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
| `atlas.smoke.operations@v1` | `lat`/`lon` del activo → **point-in-polygon** contra la geometría de humo NOAA HMS firmada completa (anillos **y** huecos, seguro en el antimeridiano) + PM2.5/AQI en la misma coordenada; rechaza si el inventario HMS está truncado o falta el aire. Análisis cualitativo, no PM2.5 medido ni orden de evacuación | `POST /api/v1/products/smoke-operations` | same |
| `atlas.nearest.read@v1` | Pin LIVE más cercano a `lat`/`lon` del comprador (capa, `max_km`, recibo) | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | Evalúa watchbox guardado o efímero → matches + recibo | watchbox `…/check` | same |
| `atlas.mesh.sample@v1` | Muestra Halton de pines LIVE de una malla in-situ licenciada (`ee-wx`, `pegel`, …). Sibling `lattice.sequence@v1`. No ECVRF (Sortes es un hop hermano), no Open-Meteo | `POST /api/v1/products/mesh-sample` | same |
| `atlas.field.consensus@v1` | Consenso (equivalente Murmuration) de lecturas LIVE in-situ (mín. 3). No un pronóstico, no Open-Meteo-como-estación | `POST /api/v1/products/field-consensus` | same |
| `atlas.field.posterior@v1` | GP RBF espacial del snapshot LIVE **actual**. Interpola ahora; no es un pronóstico. Sibling `gauss.field@v1` | `POST /api/v1/products/field-posterior` | same |
| `atlas.field.shape@v1` | Persistencia H0 de pines LIVE (componentes vs radio). No Betti-1, no un AQI. Sibling `betti.homology@v1` | `POST /api/v1/products/field-shape` | same |

Fail-closed sin LIVE. FIRMS: citar NASA. **Nearest** usa el índice de mapa ATLAS
(lecturas GAIA siguen con `device_id`). Textos UI Hub:
`aimarket-hub/cap-descriptions-i18n.json` (EN · RU · ES · FR · ZH). Catálogo tras
federation crawl.

## API (breve)

- `GET /api/v1/snapshot` — pins + caché
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics; un pin cuyo feed rotó responde con una ficha «cleared from the live window», no con un 404
- `POST /api/v1/refresh` — solo con token de operador (`X-Atlas-Token`): una llamada relee todo el catálogo
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
