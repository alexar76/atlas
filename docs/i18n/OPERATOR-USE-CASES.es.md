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

El **invoke** de GAIA no acepta lat/lon del comprador en dispositivos con **ancla** de operador. Las fuentes de eventos (FIRMS, terremotos, CAP) llevan coordenadas en la **lectura**.

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
| ¿Hay un **producto de aviso** de tsunami de EE. UU.? | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory. A menudo **vacío → offline**. | Un mareógrafo. Vacío no es «no hay tsunami en la Tierra». |
| ¿Cuál es el nivel en este **ancla** de marea? | Tide | **In situ** NOAA CO-OPS / UHSLC. | Un **producto de aviso** de tsunami. |
| ¿Qué buques hay en **aguas finlandesas**? | Public AIS `fintraffic-ais-01` | Instantánea Fintraffic Digitraffic, **CC BY 4.0**. | AIS global, GFW, AISStream o el propio `gaia.ais.read@v1`. |
| ¿Qué aeronaves vio **nuestro** receptor? | Edge traffic `feeder-adsb-01` | Ingest dump1090 propio. Offline hasta el push. | ADSBx / OpenSky / un agregador público. |
| ¿USGS ha publicado un terremoto (típicamente M≥2.5)? | Earthquakes `usgs-quake-01` | Evento GeoJSON USGS, lat/lon. | Densidad euro-mediterránea o un catálogo local australiano. |
| ¿Terremotos locales de Nueva Zelanda? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | Un catálogo global. |

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

### **Calidad del agua** USGS como SKU LIVE aparte

**Hold.** La licencia está bien (PD de EE. UU.). El sentido y la frescura, no.

- `gage_height_m` en `gaia.river.read@v1` **no** es **calidad del agua**. Esa distinción se mantiene.
- La [USGS Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/) moderna constaba como **alpha** / no para producción en la auditoría. Las series IV antiguas en sitios de prueba estaban caducadas — por eso P2 no cableó WQ.
- Las muestras de laboratorio discretas no son una **lectura** de «ahora».

Desbloquear solo con un **ancla** de operador cuyo parámetro continuo (p. ej. temperatura, oxígeno disuelto) esté fresco de forma demostrable; fail-closed si está caduco.

---

## Lo que Analyst debe rechazar

| Prompt | Por qué |
|--------|---------|
| «Declara evacuación / fin de alerta en esta costa.» | ATLAS no es autoridad de avisos. Citar el **producto de aviso** o decir offline. |
| «¿Este píxel FIRMS es un desastre GDACS?» | Clases de afirmación distintas; GDACS está en **Hold**. |
| «AIS global / rayos globales / tiempo oficial BoM AU.» | Sin licencia para un SKU de pago (GFW NC, Blitzortung NC, FTP BoM no comercial). |
| «Calidad del agua de este río inglés desde USGS.» | Geografía incorrecta y, hoy, no hay SKU WQ. |
| «Tifón desde NHC.» | Cuenca incorrecta. |

---

## Relacionado

- Mapa del operador: [`GUIDE.es.md`](GUIDE.es.md)
- Licencias de relés: [`gaia/docs/i18n/LIVE-RELAYS.es.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.es.md)
- Glosario (**watchbox**, **producto de aviso**, **AIS**, **ADS-B**, **ciclón tropical**): [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
