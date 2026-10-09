# ATLAS — casos de uso del operador

**Idiomas:** [EN](../OPERATOR-USE-CASES.md) · [RU](OPERATOR-USE-CASES.ru.md) · [ES](OPERATOR-USE-CASES.es.md) · [FR](OPERATOR-USE-CASES.fr.md) · [ZH](OPERATOR-USE-CASES.zh.md)

ATLAS es el **mapa de sensores** del operador más **ATLAS Analyst**. GAIA atesta **lecturas** de **relés** LIVE; el Hub vende `capability_id`. Esta página explica cómo un operador (o un **agente** anclado en Analyst) formula una pregunta sobre el mundo físico sin sustituir un **source** por un modelo.

Términos: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md). Mapa/API: [`GUIDE.es.md`](GUIDE.es.md). Relés y licencias: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). Añadir un **pin**: [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md).

Fecha de auditoría: **2026-08-14**. Estados:

| Estado | Significado |
|--------|-------------|
| **Live now** | Ya está en el mapa. Pregunte a Analyst sobre estas **capas**. |
| **Proposed — sell** | Licencia + HTTPS + geografía fijadas; aún no hay código. Apto para vender como SKU del Hub tras Recipe B. |
| **Hold** | No vender ni mostrar como LIVE hasta cerrar el hueco siguiente. |

---

## Cómo plantear una pregunta

1. Active solo las **capas** que pueden responderla (wildfire no es un **ciclón tropical**).
2. Lleve el **viewport** a la geografía licenciada (el **AIS** finlandés no es el mar del Norte).
3. Pulse un **pin**. Lea `source`, `LIVE`/`SIM` y `captured_at` / hora CAP si existe.
4. Pregunte a **ATLAS Analyst** nombrando la **capa**. El prompt se ancla en la instantánea de la flota — debe citar pines, no inventar un pronóstico.
5. Para un control permanente, un **watchbox** (`atlas.watchbox.subscribe@v1`) sobre esa capa + bbox.

El **invoke** de GAIA suele ser solo `device_id` en dispositivos con **ancla** de operador. Excepciones con `latitude`/`longitude` del comprador en el mismo SKU: Open-Meteo AQ (`om-aq-*`) y Sensor.Community (`sc-01` / `sc-{slug}`). Las fuentes de eventos (FIRMS, terremotos, CAP) llevan coordenadas en la **lectura**.

---

## Reglas para vender e integrar

El mismo filtro comercial que LIVE-RELAYS. Un caso que falle una fila es **Hold**.

| Puerta | Pasa |
|--------|------|
| Licencia | CC0 / CC BY / OGL / NLOD / PD de EE. UU. / Copernicus CC BY ya usados en el repo. No NC, no «solo indicativo», no ToS solo por helpdesk. |
| Integración | Host HTTPS en el **allowlist** de GAIA; sin URL del cliente; fail-closed → 503, el Hub no debita. |
| Sentido | Responde una pregunta que el catálogo no cubre, **o** una geografía que el SKU actual no cubre. No duplica el USGS global con otro nombre. |
| Honestidad | **Producto de aviso** ≠ sensor **in situ**. **AIS** público ≠ AIS de borde propio. **Hotspot VIIRS** ≠ perímetro de incendio ≠ «desastre». |

**ATLAS Analyst** puede flyTo y abrir fichas. No debe: ordenar evacuación, tratar GDACS como clasificador de FIRMS, interpretar un CAP de tsunami vacío como «todo despejado», ni presentar Open-Meteo como in situ.

---

## Live now — pregunte hoy

| Pregunta del operador / agente | Capas | Qué es la **lectura** LIVE | No afirmar |
|-------------------------------|-------|----------------------------|------------|
| ¿Dónde hay detecciones térmicas ahora? | Wildfire `firms-fire-01` | Clúster de **hotspot VIIRS** NASA FIRMS. Citar NASA FIRMS. | Perímetro, área quemada o «esto es un desastre». |
| ¿Qué incendios europeos están en la lista actual EFFIS? | EFFIS `effis-01` | Incendios actuales Copernicus EMS / JRC, **CC BY 4.0**. | Sustituto global de VIIRS; no es FIRMS. |
| ¿Hay un evento natural abierto de NASA (volcán, tormenta, hielo, …)? | Natural events `eonet-01` | Evento del catálogo EONET. Citar NASA EONET. | Trayectoria NHC; no un aviso de **ciclón tropical**. |
| ¿Hay CAP de inundación / flash-flood en EE. UU.? | Flood `nws-flood-01` | **CAP** NWS, **alerta de inundación** (PD de EE. UU.). | Inglaterra / modelo global de crecida. No se raspa GloFAS. |
| ¿Cuál es el nivel/caudal en este **ancla** de río? | Rivers | **Lectura** **in situ** USGS / ECCC / SMHI. | Una **alerta de inundación**. Gage height no es **calidad del agua**. |
| ¿Cuál es la química continua del agua en este bbox de EE. UU.? | Water quality `usgs-wq-01` | Todos los sitios USGS actuales del bbox; pH, temperatura, oxígeno disuelto y conductividad; se conservan metadatos provisionales/de calidad. | Nivel de río, muestra de laboratorio o cobertura fuera de EE. UU. |
| ¿Cuál es la línea base nacional de radiación EPA y dónde hay desviación? | EPA RadNet `radnet-*` | Las 140 coordenadas oficiales con lecturas gamma horarias aprobadas. | Pronóstico de dosis o declaración de emergencia. |
| ¿Qué medidor DART activo está más cerca del evento oceánico? | DART `noaa-dart-01`, `dart-*` | Las 43 estaciones activas del directorio NDBC fijado, cada una en su coordenada oficial. | Alerta de tsunami u orden de evacuación. |
| ¿**Este activo de Norteamérica** está dentro de un polígono de humo ahora? | `atlas.smoke.operations@v1` | Point-in-polygon exacto sobre el inventario HMS firmado completo de **Norteamérica** (huecos y antimeridiano incluidos) + PM2.5/AQI en la misma coordenada. Rechaza si el inventario está truncado o fuera de la geografía HMS. | Una orden de evacuación, un juicio sanitario, un monitor regulatorio o cobertura global de humo. |
| ¿Hay un **producto de aviso** de tsunami de EE. UU.? | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory. A menudo **vacío → offline**. | Un mareógrafo. Vacío no es «no hay tsunami en la Tierra». |
| ¿Cuál es el nivel en este **ancla** de marea? | Tide | **In situ** NOAA CO-OPS / UHSLC. | Un **producto de aviso** de tsunami. |
| ¿Qué buques hay en **aguas finlandesas**? | Public AIS `fintraffic-ais-01` | Instantánea Fintraffic Digitraffic, **CC BY 4.0**. | AIS global, GFW, AISStream o el propio `gaia.ais.read@v1`. |
| ¿Qué aeronaves vio **nuestro** receptor? | Edge traffic `feeder-adsb-01` | Ingest dump1090 propio. Offline hasta el push. | ADSBx / OpenSky / un agregador público. |
| ¿Cuál es el PM crowd cerca de este punto (o cualquier lat/lon)? | Air `sc-01` / `sc-{slug}` | Consulta de área Sensor.Community, **ODbL** — citar. El comprador puede pasar `latitude`/`longitude` en `gaia.air.read@v1`. Los pines mesh son anclas de ciudad. Área vacía → offline. | Estación AQ de referencia; cada nodo SDS011 en la Tierra; AQ modelo Open-Meteo. |
| ¿USGS ha publicado un terremoto (típicamente M≥2.5)? | Earthquakes `usgs-quake-01` | Evento GeoJSON USGS, lat/lon. | Densidad euro-mediterránea o un catálogo local australiano. |
| ¿Terremotos locales de Nueva Zelanda? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | Un catálogo global. |
| ¿Cuál es el caudal/nivel del Rin (clic en un aforo)? | Rivers `pegel-*-01` mesh | **PEGELONLINE** WSV in situ (DL-DE-Zero). Un **pin** clicable por aforo federal. | Una **alerta de inundación**; aforos NL/FR. |
| ¿Cuál es el **METAR** de este aeropuerto (clic en el aeropuerto)? | Aviation `metar-*-01` mesh | METAR AviationWeather.gov (PD de EE. UU.). Un **pin** por ICAO. | ASOS terrestre NWS; pronóstico **TAF**. |
| ¿Cuál es el **clima vial** en carreteras finlandesas (clic en una estación)? | Road `fintraffic-road-01` → `road-st-*` | Digitraffic road weather, **CC BY 4.0**. El padre de clúster despliega **pines** en el viewport. | AIS, tráfico UE o NWS. |
| ¿Dónde están los trenes en Finlandia ahora (clic en un tren)? | Rail `fintraffic-rail-01` → `rail-tr-*` | Digitraffic train locations, **CC BY 4.0**. | Ferrocarril UE o TMS vial. |
| ¿Dónde es peor la **sequía** en EE. UU. esta semana (clic en un estado)? | Drought `usdm-01` → `drought-st-*` | Estadísticas estatales semanales del **USDM** — atribuir NDMC / USDA / NOAA / NASA. | Humedad del suelo o alertas NWS. |
| ¿Qué estados de EE. UU. están en sequía esta semana? | Drought `usdm-01` | U.S. Drought Monitor — atribuir NDMC / USDA / NOAA / NASA. | Pin de humedad del suelo; CAP de inundación. |
| ¿GeoShake publicó un evento comunitario? | Earthquakes `geoshake-01` | Catálogo GeoShake **CC BY 4.0** (vacío → offline). | Sustituto de USGS/EMSC. |
| ¿Hay una alerta CAP pública canadiense? | Alerts `naad-01` | **NAAD** Atom **CAP-CP** — citar al emisor (p. ej. Environment Canada). Vacío ≠ «todo despejado». | CAP NWS. |
| ¿Cómo están el viento solar / rayos X GOES / DONKI ahora? | Space weather `swpc-*` / `donki-01` | NOAA **SWPC** PD + NASA **DONKI** abierto. | Evacuación; sustituir solo con Kp sin nombrar la fuente. |
| ¿Cuál es el caudal/nivel en este aforo de **Inglaterra** (clic en el pin)? | Rivers `ea-*-01` mesh | EA Hydrology **in situ** (OGL v3). Preferir pines con Q y nivel. | **Aviso** EA (`ea-flood-01`); SEPA/NRW; PEGELONLINE. |
| ¿Cuál es el caudal/nivel en el **Rin/Waal/IJssel NL** (clic Lobith o Tiel)? | Rivers `rws-*-01` mesh | Rijkswaterstaat WaterWebservices **in situ** (**CC0**). Lobith/Tiel dan Q+nivel; algunos pines solo nivel. | PEGELONLINE DE; EA Inglaterra; CAP de inundación. |
| ¿Cuáles son cota y almacenamiento de este embalse USACE (clic en el lago)? | Reservoir `usace-*-01` mesh | USACE CWMS Elev + Stor (PD EE. UU.). Dos campos comerciales por pin. | Un **producto de aviso** de inundación; solo stage USGS. |
| ¿Cuál es el tiempo sinóptico en vivo en **Irlanda** (clic en una estación)? | Weather `met-ie-01` → `wx-ie-*` | Observaciones Met Éireann (**CC BY 4.0** — atribución completa). T/RH/viento/lluvia/presión. | Open-Meteo como in situ; estaciones UK/NL. |
| ¿Cuál es el caudal/nivel en este aforo de **Francia** (clic en el pin)? | Rivers `hubeau-*-01` mesh | Hub'Eau hydrométrie **in situ** (**Etalab OL 2.0**). Q + nivel cuando se publica. | **Vigicrues**; PEGELONLINE DE; eHYD AT. |
| ¿Cuál es el caudal/nivel en este aforo de **Austria** (clic en el pin)? | Rivers `ehyd-*-01` mesh | eHYD / BMLUK `pegel_aktuell` **in situ** (**CC BY 4.0** — «Datenquelle: ehyd.gv.at»). | PEGELONLINE DE; Hub'Eau FR; CAP de inundación. |
| ¿Cuál es el tiempo in situ en **Suecia**? | Weather `smhi-wx-*-01` | SMHI MetObs (**CC BY 4.0**). T/RH/presión/viento. | `smhi-hydro-01`; Open-Meteo como in situ. |
| ¿Cuál es el tiempo in situ en **Singapur**? | Weather `sg-wx-*-01` | Singapore NEA / data.gov.sg (**Open Data Licence**). Viento (+ T/RH/lluvia). | Open-Meteo como in situ; PSI como estación. |
| ¿Cuál es el **PSI / PM2.5** regional de Singapur? | Air `sg-psi-*-01` | NEA PSI (**Open Data Licence**). Índice regional 24h. | Monitor de referencia; OpenAQ. |
| ¿Cuál es el tiempo in situ en **Hong Kong**? | Weather `hko-wx-*-01` | HKO `rhrread` (**DATA.GOV.HK**). Temperatura por lugar (+ RH en Observatory). | Open-Meteo como in situ. |
| ¿Cuál es el **PM2.5** in situ en **Bélgica**? | Air `be-aq-*-01` | IRCELINE SOS (**CC BY 4.0**). | OpenAQ; Sensor.Community. |
| ¿Cuál es el tiempo in situ en **España**? | Weather `aemet-wx-*-01` | AEMET OpenData (**Fuente: AEMET**). Clave `GAIA_AEMET_API_KEY`. | Open-Meteo como in situ. |
| ¿Cuál es el tiempo in situ en **Suiza**? | Weather `ch-wx-*-01` | MeteoSwiss OGD (**CC BY 4.0**). | Open-Meteo como in situ. |
| ¿Cuál es el caudal / nivel geodésico en este aforo **suizo**? | Rivers `bafu-*-01` | BAFU/FOEN LINDAS (**OGD-CH Open-Use**). Q + m s.n.m. | dangerLevel; PEGELONLINE; eHYD; Hub'Eau. |
| ¿Cuál es el tiempo in situ en **Taiwán**? | Weather `cwa-wx-*-01` | CWA OpenData (**OGDL 1.0**). Clave `GAIA_CWA_API_KEY`. | Open-Meteo como in situ. |
| ¿Cuál es el tiempo in situ en **Francia** (estación)? | Weather `mf-wx-*-01` | Météo-France DPObs (**Etalab OL 2.0**). Clave `GAIA_METEOFRANCE_APPLICATION_ID`. | Hub'Eau; Open-Meteo como in situ. |
| ¿Cuál es el tiempo in situ en **Estonia**? | Weather `ee-wx-*-01` | Estonian Weather Service XML (**CC BY 4.0**). | Open-Meteo como in situ. |
| ¿Cuál es el tiempo in situ en **Islandia**? | Weather `is-wx-*-01` | IMO AWS (**ODC-By**). | Open-Meteo como in situ. |
| ¿Cuál es el **AQHI de Hong Kong** (clic en el sitio)? | Air `hk-aqhi-*-01` | EPD AQHI (**DATA.GOV.HK**). 1–10 / 10+. | PM2.5; tiempo HKO; IRCELINE. |

### P12 — nuevos pines LIVE y SKU de campo

| Pregunta | Pin / SKU | Fuente y límite de la afirmación |
|---|---|---|
| ¿Cuál es el tiempo in situ en **Austria**? | `at-wx-*-01` | GeoSphere Austria TAWES, **CC BY 4.0**; observaciones, no un pronóstico de pago. |
| ¿Cuál es el tiempo in situ en **Lituania**? | `lt-wx-*-01` | LHMT Meteo.lt, **CC BY-SA 4.0**; no use `/forecasts`. |
| ¿Cuál es el nivel del Nemunas o Neris? | `lt-hydro-*-01` | Hidrología medida LHMT, **CC BY-SA 4.0**; los centímetros se entregan como metros. |
| ¿Cuál es el tiempo in situ en **Letonia**? | `lv-wx-*-01` | CSV HVD de LVGMC, **CC0-1.0**; más de 6 horas → offline. |
| ¿Cuál es el nivel del Daugava o Lielupe? | `lv-hydro-*-01` | Hidrología LVGMC, **CC0-1.0**; no es un aviso de inundación. |
| ¿Hay un aviso Vigicrues en esta cuenca francesa? | `vic-*-01` | VIC WARNING, **Etalab OL 2.0**; verde/vacío no significa «todo seguro» y no es Hub'Eau. |
| ¿Cuál es la intensidad nacional francesa de carbono de producción? | `rte-grid-01` | RTE éCO2mix, **Etalab OL 2.0**; solo producción, sin importaciones ni ciclo de vida. |
| ¿Cuál es el nivel de este aforo OPW irlandés? | `ie-river-*-01` | waterlevel.ie, **CC BY 4.0**; nivel, no CAP de inundación. |
| ¿Cuál es el tiempo in situ en **Japón**? | `jp-wx-*-01` | JMA AMeDAS, Public Data License; cite JMA, no es una licencia de pronóstico. |
| ¿Informó JMA un terremoto? | `jma-quake-01` | `list.json` oficial de JMA; no p2pquake ni reemplazo de USGS/EMSC. |
| ¿Qué tifón está activo en el Pacífico noroccidental? | `jma-typhoon-01` | JMA targetTc, Public Data License; temporada vacía → offline, no NHC/JTWC. |
| ¿Cuál es el tiempo in situ en la **República Checa**? | `cz-wx-*-01` | ČHMÚ climate-now, **CC BY 4.0**; no Open-Meteo como estación. |
| ¿Cuál es el tiempo in situ en **Corea**? | `kr-wx-*-01` | KMA ASOS, Public Nuri Type 1; requiere `GAIA_KMA_SERVICE_KEY`, no AirKorea. |
| ¿Hay inundación observada por Copernicus? | `gfm-flood-01` | Copernicus GFM, **CC BY 4.0**; requiere `GAIA_GFM_TOKEN`, no es el pronóstico GloFAS. |
| ¿Cuál es el consenso robusto de temperaturas Estonia EWS ahora? | `atlas.field.consensus@v1`, malla `ee-wx` | Mediana / biweight de lecturas LIVE in situ con recibo; no es pronóstico ni cifra nacional oficial. |
| ¿Dónde está el posterior GP espacial de la instantánea Estonia EWS actual? | `atlas.field.posterior@v1`, malla `ee-wx` | El GP RBF interpola datos actuales con varianza; no es pronóstico ni nowcast nacional. |
| ¿Qué aforos del Rin consultar sin elegirlos a conveniencia? | `atlas.mesh.sample@v1`, malla `pegel` | Subconjunto Halton de PEGELONLINE LIVE; repita con el mismo `skip`, no es Sortes ECVRF. |
| ¿Se dividió la red AQ belga en clústeres? | `atlas.field.shape@v1`, malla `be-aq` | Componentes H0 por radio de IRCELINE LIVE; no AQI ni bucles Betti-1. |

**Arranques para Analyst (live now)**

- «Apaga el resto de **capas**. ¿Cuál es el **hotspot VIIRS** FIRMS más brillante en este **viewport**? Cita NASA FIRMS.»
- «¿`nws-flood-01` está online? Si sí, cita el titular CAP. Si offline, di que el **producto de aviso** está vacío — no infieras seguridad.»
- «**Pin** de río LIVE más cercano a este clic — solo la **lectura**, no una **alerta de inundación**.»
- «AIS público finlandés: ¿cuántos buques en vista? Crédito Fintraffic. No lo llames AIS global.»

Ejemplos de **watchbox**: capa `fire` + bbox; `flood` + bbox EE. UU.; `ais` + Báltico.

---

## Proposed — sell (auditoría 2026-08-14)

Los seis SKU auditados (NHC, EMSC, EA flood, PTWC, Kystverket AIS, ADSB.lol) **están cableados** — ver **Live now**. Aparecen en el mapa tras redeploy **GAIA, luego ATLAS**.

### 1. «¿Qué **ciclón tropical** está activo en el Atlántico / Pacífico oriental?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | nuevo `gaia.cyclone.read@v1` (no sobrecargar EONET) |
| **Upstream** | NOAA NHC `CurrentStorms.json` — PD de EE. UU. |
| **Geografía** | Atlántico + Pacífico oriental. No Pacífico noroccidental (tifón / 台风). Cuenca NHC: huracán. |
| **Vender / integrar** | Sí. Temporada vacía → offline / sin débito, como el CAP de tsunami. |
| **Analyst** | «Lista las tormentas activas NHC con lat/lon e intensidad. No es EONET ni un feed global de ciclones.» |
| **No** | Responder «tifón cerca de Japón» desde NHC. |

### 2. «¿Europa tiembla más denso que USGS M≥2.5?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | `gaia.quake.read@v1` existente, nuevo `device_id` `emsc-01` |
| **Upstream** | EMSC FDSN `seismicportal.eu` — **CC BY 4.0** ([página del servicio](https://www.seismicportal.eu/fdsn-wsevent.html)) |
| **Geografía** | Euro-Mediterráneo denso; global M≥4.5. Citar EMSC. Parámetros preliminares. |
| **Vender / integrar** | Sí. **Pin** distinto de `usgs-quake-01`. |
| **Analyst** | «Compara EMSC y USGS en este **viewport**. No elijas ganador; cita ambos `source`.» |
| **No** | Sustituir USGS a escala global. |

### 3. «¿Hay **alerta de inundación** en Inglaterra?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | `gaia.flood.read@v1` existente, nuevo `ea-flood-01` (**anclas** de río opcionales en `gaia.river.read@v1`) |
| **Upstream** | API en tiempo real de Environment Agency — **OGL**, sin clave. Atribución: datos EA de inundación y nivel fluvial. |
| **Geografía** | **Inglaterra**, no el Reino Unido (Escocia SEPA / Gales NRW son aparte). |
| **Vender / integrar** | Sí. Complementa el CAP NWS solo de EE. UU. |
| **Analyst** | «**Producto de aviso** EA para Inglaterra. No es un nivel **in situ** del Támesis salvo que el **pin** de río esté online.» |
| **No** | Decir «inundación UK» ni raspar GloFAS. |

### 4. «¿Hay un **producto de aviso** de tsunami en el Pacífico?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | `gaia.tsunami.read@v1` existente, nuevo `ptwc-01` |
| **Upstream** | PTWC / Atom o CAP de `tsunami.gov` — PD de EE. UU. |
| **Geografía** | Pacífico (cuencas PTWC). Complementa el CAP NWS centrado en EE. UU. |
| **Vender / integrar** | Sí. Feed vacío → offline. **Producto de aviso**, no mareógrafo. |
| **Analyst** | «Cita por separado los pines PTWC y NWS tsunami. Vacío ≠ todo despejado.» |
| **No** | Ordenar evacuación; Analyst no es una autoridad nacional de avisos. |

### 5. «¿Qué buques hay frente a Noruega?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | `gaia.ais.public.read@v1` existente, nuevo `kystverket-ais-01` (o equivalente) |
| **Upstream** | Kystverket vía BarentsWatch — **NLOD**, uso comercial con atribución. Registro OpenID gratuito (misma clase que `GAIA_KNMI_API_KEY`). |
| **Geografía** | Aguas noruegas, no finlandesas, no globales. |
| **Vender / integrar** | Sí, tras fijar el host REST + token en el **allowlist**. |
| **Analyst** | «**AIS** público noruego. Crédito Kystverket / BarentsWatch. No Fintraffic ni AIS de borde propio.» |
| **No** | Fusionar con `fintraffic-ais-01` en un «AIS europeo». |

### 6. «¿Qué aeronave hay sobre este punto — sin nuestro receptor?»

| | |
|--|--|
| **Estado** | Proposed — sell |
| **SKU** | nuevo `gaia.adsb.public.read@v1` (paralelo al AIS público; **no** `gaia.adsb.read@v1`) |
| **Upstream** | [ADSB.lol](https://www.adsb.lol/docs/open-data/api/) `api.adsb.lol` — **ODbL 1.0** |
| **Geografía** | Cobertura del feed, no un mandato nacional. |
| **Vender / integrar** | Sí, con la misma honestidad que Sensor.Community: **lectura** comercial OK; una base derivada pública es **ODbL share-alike**. Aislar la BD derivada ADS-B. Fijar solo `api.adsb.lol`. |
| **Analyst** | «ADS-B público vía ADSB.lol (ODbL). No nuestro dump1090. No OpenSky / ADSBx.» |
| **No** | Encadenar agregadores de aviación en silencio. |

---

## Hold — no vender aún

### EPA UV como «escritorio de operaciones» de pago

**Hold del copy de use-case** (el relé puede seguir LIVE en el mapa).

- El titular del pin es un solo `uv_index` (máx. de pronóstico por ZIP). No pasa el bar: un escalar en el pin no es un escritorio multi-señal.
- Es un **pronóstico** EPA por hora, no un piranómetro in situ.
- Desbloquear cuando el pin/clúster venda ≥2 campos útiles sin inventar instrumentos.

**Sustituto live now:** tiempo Met Éireann / NWS / Open-Meteo; no vender UV solo como «seguridad del sitio».

### GDACS como «desastre, no un punto VIIRS»

**Hold.** La pregunta del operador tiene sentido; la fuente aún no es vendible con nuestras reglas.

- Los [GDACS Terms of use (marzo 2025)](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) oficiales **no** conceden CC BY 4.0. Describen estimaciones de impacto por modelo, «as is», y dicen que las alertas **no** deben usarse para decidir sin confirmación de las autoridades competentes.
- GDACS **no** clasifica un **hotspot VIIRS** de FIRMS. Es un **producto de aviso** multi-peligro / puntuación modelo ONU/CE sobre asistencia internacional — otra clase de afirmación que las detecciones térmicas y EFFIS.
- Páginas de terceros que dicen «CC BY 4.0» no son un pin. El mismo listón que dejó EMSC fuera hasta que la página FDSN declaró CC BY 4.0.

**Sustituto live now:** FIRMS (detecciones) + EFFIS (incendios actuales UE) + EONET (eventos NASA). Analyst mantiene esos tres `source` separados.

### Terremotos de Geoscience Australia como «¿tiembla Australia?»

**Hold** del **relé** HTTPS en vivo, no de la idea.

- «Recent Earthquakes» en data.gov.au es **CC BY 3.0 Australia**, pero el registro del catálogo ≠ un GeoJSON/WFS allowlisted y comprobado en frescura.
- USGS ya informa eventos australianos por encima de su umbral de magnitud. Esa es la respuesta honesta **Live now**.
- Desbloquear cuando un endpoint GA NEAC esté fijado como GeoNet (`api.geonet.org.nz`).

### **Calidad del agua** USGS — red LIVE

Está conectada la colección OGC actual de mediciones continuas: el bbox del comprador devuelve todos los sitios coincidentes y cada uno se convierte en una coordenada de lectura. Se conservan hora, provisional/approval y qualifier; `gage_height_m` sigue sin ser calidad del agua. Geografía: EE. UU.

---

## Lo que Analyst debe rechazar

| Prompt | Por qué |
|--------|---------|
| «Declara evacuación / fin de alerta en esta costa.» | ATLAS no es autoridad de avisos. Citar el **producto de aviso** o decir offline. |
| «¿Este píxel FIRMS es un desastre GDACS?» | Clases de afirmación distintas; GDACS está en **Hold**. |
| «AIS global / rayos globales / tiempo oficial BoM AU.» | Sin licencia para un SKU de pago (GFW NC, Blitzortung NC, FTP BoM no comercial). |
| «Calidad del agua de este río inglés desde USGS.» | Geografía incorrecta: la red continua USGS conectada cubre EE. UU., no Inglaterra. |
| «Tifón desde NHC.» | Cuenca incorrecta. |

---

## Relacionado

- Mapa del operador: [`GUIDE.es.md`](GUIDE.es.md)
- Licencias de relés: [`gaia/docs/i18n/LIVE-RELAYS.es.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.es.md)
- Glosario (**watchbox**, **producto de aviso**, **AIS**, **ADS-B**, **ciclón tropical**): [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
