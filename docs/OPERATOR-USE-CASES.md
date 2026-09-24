# ATLAS — operator use cases

**Languages:** [EN](OPERATOR-USE-CASES.md) · [RU](i18n/OPERATOR-USE-CASES.ru.md) · [ES](i18n/OPERATOR-USE-CASES.es.md) · [FR](i18n/OPERATOR-USE-CASES.fr.md) · [ZH](i18n/OPERATOR-USE-CASES.zh.md)

ATLAS is the operator **sensor map** plus **ATLAS Analyst**. GAIA attests **readings** from LIVE **relays**; the Hub sells `capability_id`s. This page is how an operator (or an **agent** with a grounded Analyst) asks a physical-world question without substituting a model for a **source**.

Terms: [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md) (EN · RU · ES · FR · ZH). Map/API: [`GUIDE.md`](GUIDE.md). Relays and licences: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). Add a **pin**: [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md).

Audit date: **2026-09-07** (P6 critic). Status labels:

| Status | Meaning |
|--------|---------|
| **Live now** | On the map today. Ask Analyst against these layers. |
| **Proposed — sell** | Licence + HTTPS + geography pinned. The 2026-08-14 six are now **Live now** (need GAIA then ATLAS redeploy). |
| **Hold** | Do **not** sell or show as LIVE until the gap below is closed. |

---

## How to run a question

1. Toggle only the **layers** that can answer it (wildfire is not a **tropical cyclone**).
2. Fly the **viewport** to the licensed geography (Finnish **AIS** is not the North Sea).
3. Click a **pin**. Read `source`, `LIVE`/`SIM`, and `captured_at` / CAP time when present.
4. Ask **ATLAS Analyst** a question that names the layer. The prompt is grounded on the cached fleet snapshot — it must cite pins, not invent a forecast.
5. If you need a standing check, set a **watchbox** (`atlas.watchbox.subscribe@v1`) on that layer + bbox.

GAIA **invoke** is usually `device_id`-only for operator-anchored devices. Exceptions that accept buyer `latitude`/`longitude` on the same SKU: Open-Meteo AQ (`om-aq-*`) and Sensor.Community (`sc-01` / `sc-{slug}`). Event feeds (FIRMS, quake, CAP) carry coordinates in the **reading**.

---

## Rules for selling and embedding

These are the same commercial filter as LIVE-RELAYS. A use case that fails one row is **Hold**.

| Gate | Pass |
|------|------|
| Licence | CC0 / CC BY / OGL / NLOD / U.S. PD / Copernicus CC BY already used in-repo. Not NC, not “indicative only”, not a helpdesk-only ToS. |
| Embed | HTTPS host on the GAIA **allowlist**; no client URLs; fail-closed → 503, Hub must not debit. |
| Meaning | Answers a question the existing catalog cannot, **or** a geography the existing SKU does not cover. Does not duplicate USGS-as-global under a new name. |
| Honesty | **Warning product** ≠ **in-situ** gauge. Public **AIS** ≠ own-edge AIS. **VIIRS hotspot** ≠ fire perimeter ≠ “disaster”. |

**ATLAS Analyst** may flyTo and open station panels. It must not: order evacuation, call GDACS a FIRMS classifier, treat an empty tsunami CAP as “all clear”, or present Open-Meteo as in-situ.

---

## Live now — ask these today

| Operator / agent question | Layers | What the LIVE **reading** is | Must not claim |
|---------------------------|--------|------------------------------|----------------|
| Where are thermal detections right now? | Wildfire `firms-fire-01` | NASA FIRMS **VIIRS hotspot** cluster. Cite NASA FIRMS. | Fire perimeter, burned area, or “this is a disaster”. |
| Which European fires are in the EFFIS current list? | EFFIS `effis-01` | Copernicus EMS / JRC current fires, **CC BY 4.0**. | A global VIIRS substitute; not FIRMS. |
| Is there a NASA open natural event (volcano, storm, ice, …)? | Natural events `eonet-01` | EONET catalog event. Cite NASA EONET. | NHC storm track; not a **tropical cyclone** advisory. |
| Is the US in a flood / flash-flood CAP? | Flood `nws-flood-01` | NWS **CAP** **flood warning** (U.S. PD). | England / global flood model. GloFAS is not scraped. |
| What is stage/discharge at this river **anchor**? | Rivers | USGS / ECCC / SMHI **in-situ** **reading**. | A **flood warning**. Gage height is not **water quality**. |
| Is there a US tsunami **warning product**? | Tsunami `nws-tsunami-01` | NWS CAP tsunami warning/watch/advisory. Often **empty → offline**. | A tide gauge. Empty is not “no tsunami on Earth”. |
| Is there a Pacific tsunami **warning product**? | Tsunami `ptwc-01` | PTWC Atom. Information-only quake statements are not sold. Empty → offline. | A tide gauge. Empty ≠ all-clear. Analyst must not order evacuation. |
| What is water level at this tide **anchor**? | Tide | NOAA CO-OPS / UHSLC **in-situ**. | A tsunami **warning product**. |
| What ships are in **Finnish waters**? | Public AIS `fintraffic-ais-01` | Fintraffic Digitraffic snapshot, **CC BY 4.0**. | Global AIS, GFW, AISStream, or own-edge `gaia.ais.read@v1`. |
| What ships are off **Norway**? | Public AIS `kystverket-ais-01` | Kystverket via BarentsWatch, **NLOD 2.0**. Needs operator token. | Finnish AIS, global AIS, or merging with Fintraffic into one Europe blob. |
| What aircraft did **our** receiver see? | Edge traffic `feeder-adsb-01` | Own dump1090 ingest. Offline until push. | ADSBx / OpenSky / a public aggregator. |
| What aircraft are over this **anchor** without our receiver? | Public ADS-B `adsb-lol-01` | ADSB.lol **ODbL 1.0** area query (default LHR). Isolate any derived DB. | Own-edge `gaia.adsb.read@v1`. No OpenSky/ADSBx fallback. |
| What is crowd PM near this map point (or any lat/lon)? | Air `sc-01` / `sc-{slug}` | Sensor.Community area query, **ODbL** — cite. Buyer may pass `latitude`/`longitude` on `gaia.air.read@v1`. Mesh pins are city anchors. Empty area → offline. | A reference AQ station; every SDS011 node on Earth; Open-Meteo model AQ. |
| Did USGS report a quake (typically M≥2.5)? | Earthquakes `usgs-quake-01` | USGS GeoJSON event lat/lon. | Euro-Med density, or a local Australian catalogue. |
| Is Europe denser than USGS M≥2.5? | Earthquakes `emsc-01` | EMSC FDSN, **CC BY 4.0** — cite EMSC. Preliminary. | A USGS replacement. |
| New Zealand local quakes? | Earthquakes `geonet-01` | GeoNet, **CC BY 3.0 NZ**. | A global catalog. |
| Which **tropical cyclone** is active in the Atlantic / East Pacific? | Tropical cyclones `nhc-cyclone-01` | NHC/CPHC CurrentStorms, U.S. PD. Empty season → offline. | JTWC / NW-Pacific typhoon / EONET. |
| Is there a **flood warning** in England? | Flood `ea-flood-01` | EA **OGL** warning product. England only. | “UK flood”, SEPA/NRW, GloFAS, or a Thames **in-situ** stage. |
| What is the latest continuous water chemistry in this U.S. bbox? | Water quality `usgs-wq-01` | Every current USGS continuous site in the bbox; pH, temperature, dissolved oxygen and conductance; provisional/quality metadata retained. | A river stage, discrete lab sample, or coverage outside the U.S. |
| What is the national EPA radiation baseline and where is a station deviating? | EPA RadNet `radnet-*` | All 140 official monitor coordinates with approved hourly gamma readings. | A dose forecast or an emergency declaration. |
| Which active DART gauge is nearest this ocean event? | DART `noaa-dart-01`, `dart-*` | All 43 active stations in the checked-in NDBC directory, each at its official coordinate. | A tsunami warning or evacuation instruction. |
| Where is NOAA HMS smoke over **North America**? | Smoke `hms-smoke-01` | **North America** qualitative polygons (light/medium/heavy); map anchors at the polygon centre; the signed ring travels with the reading. Not global. | PM2.5, an in-situ smoke sensor, or coverage outside North America. |
| Is **this North American site** inside a smoke polygon right now? | `atlas.smoke.operations@v1` | Exact point-in-polygon over the complete signed **North America** HMS inventory (holes and date-line handled) + PM2.5/AQI at the same coordinate. Refuses on a truncated inventory or outside HMS geography. | An evacuation order, a health ruling, a regulatory monitor reading, or global smoke coverage. |
| What is the daily solar resource at this configured cell? | Solar `solar-*` | NASA POWER daily irradiation with its observation date. | An instantaneous pyranometer reading. |
| What are snow depth and SWE at this mountain cell? | Snow `snow-*` | NOHRSC/SNODAS assimilated model cell. | An in-situ snow gauge. |
| What is Arctic ice concentration at this map point? | Sea ice `nsidc-ice-01` | Current Sea Ice Index v4 25-km cell centre. | Navigation advice or discontinued NISE current data. |
| What is land-surface temperature here? | Land temperature `lst-*` | Sentinel-3 SLSTR L2 1-km LST and uncertainty. | Air temperature or a ground thermometer. |
| What is discharge/stage on the Rhine (click a gauge)? | Rivers `pegel-*-01` mesh | WSV PEGELONLINE in-situ (DL-DE-Zero). One clickable ATLAS pin per federal gauge. | A flood warning; NL/FR gauges. |
| What is the METAR at this airport (click the airport)? | Aviation `metar-*-01` mesh | AviationWeather.gov METAR (U.S. PD). One pin per ICAO. | NWS land ASOS pin; TAF forecast. |
| What is road-weather on Finnish highways (click a station)? | Road `fintraffic-road-01` → `road-st-*` | Digitraffic road weather, **CC BY 4.0**. Cluster parent fans viewport pins. | AIS, EU traffic, or NWS. |
| Where are trains in Finland right now (click a train)? | Rail `fintraffic-rail-01` → `rail-tr-*` | Digitraffic train locations, **CC BY 4.0**. | EU rail or road TMS. |
| Where is U.S. drought worst this week (click a state)? | Drought `usdm-01` → `drought-st-*` | USDM weekly state stats — attribute NDMC/USDA/NOAA/NASA. | Soil moisture or NWS alerts. |
| Which U.S. states are in drought this week? | Drought `usdm-01` | U.S. Drought Monitor state stats — attribute NDMC/USDA/NOAA/NASA. | Soil moisture pin; flood CAP. |
| Did GeoShake report a community event? | Earthquakes `geoshake-01` | GeoShake CC BY 4.0 catalog (empty → offline). | USGS/EMSC replacement. |
| Is there a Canadian CAP public alert? | Alerts `naad-01` | NAAD Atom CAP-CP — cite issuer (e.g. Environment Canada). | NWS CAP; empty ≠ all-clear. |
| What is solar-wind / GOES X-ray / DONKI now? | Space weather `swpc-*` / `donki-01` | NOAA SWPC PD + NASA DONKI open. | Evacuation; Kp-only substitute without naming source. |
| What is discharge/stage on this **England** river gauge (click the pin)? | Rivers `ea-*-01` mesh | EA Hydrology API **in-situ** (OGL v3). Prefer pins that carry both Q and stage. | EA **flood warning** (`ea-flood-01`); Scotland SEPA; Wales NRW; PEGELONLINE. |
| What is discharge/stage on this **Scotland** river gauge (click the pin)? | Rivers `sepa-*-01` mesh | SEPA KiWIS **in-situ** (OGL). Stage + flow when published. | EA England; NRW Wales; a flood CAP. |
| What is discharge/stage on this **Wales** river gauge (click the pin)? | Rivers `nrw-*-01` mesh | NRW River Levels API **in-situ** (OGL). Needs host `GAIA_NRW_API_KEY`. | EA England; SEPA; a flood CAP. |
| What is discharge/stage on the **NL Rhine/Waal/IJssel** (click Lobith or Tiel)? | Rivers `rws-*-01` mesh | Rijkswaterstaat WaterWebservices **in-situ** (**CC0**). Lobith/Tiel expose Q+stage; some pins are stage-only. | PEGELONLINE DE; EA England; a flood CAP. |
| What are pool elevation and storage at this USACE reservoir (click the lake)? | Reservoir `usace-*-01` mesh | USACE CWMS Elev + Stor (U.S. PD). Two commercial fields per pin. | A flood **warning product**; USGS river stage alone. |
| What is the live synoptic weather in **Ireland** (click a station)? | Weather `met-ie-01` → `wx-ie-*` | Met Éireann observations (**CC BY 4.0** — full five-line attribution). T/RH/wind/rain/pressure. | Open-Meteo as in-situ; UK/NL land stations. |
| What is in-situ weather in **Norway** (not METAR)? | Weather `frost-*-01` | MET Norway Frost (**CC BY 4.0 + NLOD**). Needs `GAIA_FROST_CLIENT_ID`. | `metno-01` METAR; Open-Meteo locationforecast. |
| What is in-situ weather in **Denmark**? | Weather `dmi-*-01` | DMI metObs (**CC BY 4.0**). No API key. | Open-Meteo as in-situ; Swedish/Norwegian stations. |
| Local **Italy** earthquakes? | Earthquakes `ingv-01` | INGV FDSN (**CC BY 4.0** — cite INGV). | USGS/EMSC replacement. |
| Wave height at this **California** CDIP buoy? | Marine `cdip-*-01` | CDIP ERDDAP in-situ Hs — acknowledge CDIP/Scripps/USACE. | NDBC East Coast; Open-Meteo Marine as in-situ. |
| Atmospheric **CO₂** at this ICOS tower? | GHG `icos-*-01` | ICOS ATC NRT (**CC BY 4.0**). Needs host token. | PM2.5 / OpenAQ; Open-Meteo CO₂. |
| What is discharge/stage on this **France** river gauge (click the pin)? | Rivers `hubeau-*-01` mesh | Hub'Eau hydrométrie **in-situ** (**Etalab OL 2.0**). Q + stage when published. | Vigicrues **warning**; PEGELONLINE DE; eHYD AT. |
| What is discharge/stage on this **Austria** river gauge (click the pin)? | Rivers `ehyd-*-01` mesh | eHYD / BMLUK `pegel_aktuell` **in-situ** (**CC BY 4.0** — «Datenquelle: ehyd.gv.at»). | PEGELONLINE DE; Hub'Eau FR; a flood CAP. |
| What is in-situ weather in **Sweden**? | Weather `smhi-wx-*-01` | SMHI MetObs (**CC BY 4.0**). T/RH/pressure/wind. | `smhi-hydro-01` river; Open-Meteo as in-situ. |
| What is in-situ weather in **Singapore**? | Weather `sg-wx-*-01` | Singapore NEA via data.gov.sg (**Open Data Licence**). Wind (+ T/RH/rain when published). | Open-Meteo as in-situ; regional PSI as station. |
| What is regional **Singapore PSI / PM2.5**? | Air `sg-psi-*-01` | NEA PSI (**Open Data Licence**). 24h regional index. | Reference-grade monitor; OpenAQ elsewhere. |
| What is in-situ weather in **Hong Kong**? | Weather `hko-wx-*-01` | HKO `rhrread` (**DATA.GOV.HK** attribution). Place temperature (+ RH at Observatory). | Open-Meteo as in-situ. |
| What is in-situ **Belgium PM2.5**? | Air `be-aq-*-01` | IRCELINE SOS (**CC BY 4.0**). | OpenAQ; Sensor.Community crowd density. |
| What is in-situ weather in **Spain**? | Weather `aemet-wx-*-01` | AEMET OpenData (**Fuente: AEMET**). Needs `GAIA_AEMET_API_KEY`. | Open-Meteo as in-situ. |
| What is in-situ weather in **Switzerland**? | Weather `ch-wx-*-01` | MeteoSwiss OGD (**CC BY 4.0**). T/RH/QFF/wind. | Open-Meteo as in-situ. |
| What is discharge / geodetic water level on this **Swiss** river gauge? | Rivers `bafu-*-01` | BAFU/FOEN LINDAS (**OGD-CH Open-Use**). Q + m a.s.l. | Flood dangerLevel; PEGELONLINE; eHYD; Hub'Eau. |
| What is in-situ weather in **Taiwan**? | Weather `cwa-wx-*-01` | CWA OpenData (**OGDL 1.0**). Needs `GAIA_CWA_API_KEY`. | Open-Meteo as in-situ. |
| What is in-situ weather in **France** (synoptic station)? | Weather `mf-wx-*-01` | Météo-France DPObs (**Etalab OL 2.0**). Needs `GAIA_METEOFRANCE_APPLICATION_ID`. | Hub'Eau river; Open-Meteo as in-situ. |
| What is in-situ weather in **Estonia**? | Weather `ee-wx-*-01` | Estonian Weather Service XML (**CC BY 4.0**). | Open-Meteo as in-situ. |
| What is in-situ weather in **Iceland**? | Weather `is-wx-*-01` | IMO AWS hourly (**ODC-By**). | Open-Meteo as in-situ. |
| What is the **Hong Kong AQHI** (click the site)? | Air `hk-aqhi-*-01` | EPD AQHI (**DATA.GOV.HK**). 1–10 / 10+. | PM2.5 µg/m³; HKO weather; IRCELINE. |
| What is in-situ weather in **Austria**? | Weather `at-wx-*-01` | GeoSphere TAWES 10-min (**CC BY 4.0**). | Paid GeoSphere forecast; Open-Meteo as in-situ. |
| What is in-situ weather in **Lithuania**? | Weather `lt-wx-*-01` | LHMT Meteo.lt (**CC BY-SA 4.0**). | `/forecasts`; Open-Meteo as in-situ. |
| What is stage on this **Nemunas / Neris** gauge? | Rivers `lt-hydro-*-01` | LHMT hydro measured (**CC BY-SA 4.0**). cm → m. | A flood CAP. |
| What is in-situ weather in **Latvia**? | Weather `lv-wx-*-01` | LVGMC HVD CSV (**CC0-1.0**). Stale >6h → offline. | Open-Meteo as in-situ. |
| What is stage on this **Daugava / Lielupe** gauge? | Rivers `lv-hydro-*-01` | LVGMC hydro CSV (**CC0-1.0**). | A flood warning. |
| Is there a **Vigicrues** flood warning in this French basin? | Flood `vic-*-01` | VIC WARNING (**Etalab OL 2.0**). Green/empty ≠ all-clear. | Hub'Eau in-situ stage. |
| What is **France national** production-only carbon intensity? | Grid `rte-grid-01` | RTE éCO2mix `taux_co2` (**Etalab OL 2.0**). Paris pin. | Imports/lifecycle CO₂; ENTSO-E. |
| What is stage on this **Ireland** OPW gauge? | Rivers `ie-river-*-01` | waterlevel.ie GeoJSON (**CC BY 4.0**). Stations >41000 excluded. | A flood CAP. |
| What is in-situ weather in **Japan**? | Weather `jp-wx-*-01` | JMA AMeDAS (**Public Data License**). Cite JMA. | A JP forecast licence. |
| Did **JMA** report a local quake? | Earthquakes `jma-quake-01` | Official `list.json` (cite JMA). Not p2pquake. | USGS/EMSC replacement. |
| Which **NW-Pacific typhoon** is active? | Tropical cyclones `jma-typhoon-01` | JMA targetTc (cite JMA). Empty season → offline. | NHC / JTWC. |
| ~~INMET Brazil WIS2~~ | — | **Not shipped** — upstream SYNOP stale; offline must not be sold as live. | Revisit when WIS2 observations are current. |
| What is in-situ weather in the **Czech Republic**? | Weather `cz-wx-*-01` | ČHMÚ climate-now (**CC BY 4.0**). | Open-Meteo as in-situ. |
| What is in-situ weather in **Korea**? | Weather `kr-wx-*-01` | KMA ASOS (**Public Nuri Type 1**). Needs `GAIA_KMA_SERVICE_KEY`. | AirKorea (Type 3 ND). |
| Is there an observed Copernicus flood here? | Flood `gfm-flood-01` | Copernicus GFM observed flood (**CC BY 4.0**). Needs `GAIA_GFM_TOKEN`. | GloFAS forecast or a claim that no detection means all-clear. |
| What is the robust consensus of **Estonia EWS** temperatures right now? | `atlas.field.consensus@v1` mesh `ee-wx` | Median / biweight of LIVE `ee-wx-*` in-situ readings + receipt. Cite Estonian Weather Service CC BY 4.0. | Open-Meteo as in-situ; an official national forecast; “all clear” on an empty feed. |
| Where is the spatial GP posterior of the **current** Estonia EWS snapshot? | `atlas.field.posterior@v1` mesh `ee-wx` | Spatial RBF GP of the LIVE `ee-wx` in-situ snapshot + receipt. Interpolates now; sibling `gauss.field@v1`. Cite Estonian Weather Service CC BY 4.0. | A forecast; a national nowcast; Open-Meteo as in-situ. |
| Which Rhine gauges should an agent poll without cherry-picking? | `atlas.mesh.sample@v1` mesh `pegel` | Halton subset of LIVE PEGELONLINE pins. Replay with the same `skip`. | Sortes ECVRF (this SKU is Lattice-equivalent); PEGEL as a flood warning. |
| Has the **Belgian AQ** network split into two clusters? | `atlas.field.shape@v1` mesh `be-aq` | H0 components vs radius of LIVE IRCELINE pins. | An AQI, Betti-1 loops, OpenAQ-as-Belgium. |

**Analyst starters (live now)**

- “Toggle Wildfire off everything else. What is the brightest FIRMS **VIIRS hotspot** in this **viewport**? Cite NASA FIRMS.”
- “Is `nws-flood-01` online? If yes, quote the CAP headline. If offline, say the **warning product** is empty — do not infer safety.”
- “Nearest LIVE river **pin** to this click — **reading** only, not a **flood warning**.”
- “Finnish Public AIS: how many vessels in view? Credit Fintraffic. Do not call it global AIS.”
- “NHC active storms in this **viewport** — intensity and lat/lon. Not EONET, not JTWC.”
- “Compare `emsc-01` vs `usgs-quake-01` here. Cite both `source`s; do not pick a winner.”
- “EA flood **warning product** for England. Not a Thames in-situ stage unless the river **pin** is online.”
- “England river **pin** at Kingston — quote discharge and stage; cite EA Hydrology OGL. Do not call it `ea-flood-01`.”
- “Lobith `rws-lobith-01` — Q and stage, credit Rijkswaterstaat CC0. Not PEGELONLINE.”
- “USACE Keystone — pool elev (m) and storage (m³). Not a flood warning.”
- “Ireland weather cluster: Dublin T/RH/wind; credit Met Éireann CC BY 4.0.”
- “Paris `hubeau-paris-01` — Q/stage; cite Hub'Eau Etalab OL 2.0. Not Vigicrues.”
- “Achleiten `ehyd-achleiten-01` — cite eHYD / ehyd.gv.at. Not PEGELONLINE.”
- “Arlanda `smhi-wx-arlanda-01` — MetObs T/RH; cite SMHI. Not `smhi-hydro-01`.”
- “Singapore `sg-wx-marina-01` — NEA wind; Open Data Licence. Not a forecast.”
- “HK Observatory `hko-wx-observatory-01` — cite HKO / DATA.GOV.HK.”
- “Brussels `be-aq-brussels-01` — IRCELINE PM2.5; cite IRCELINE CC BY 4.0.”
- “Madrid `aemet-wx-madrid-01` — AEMET in-situ; Fuente: AEMET. Not a forecast.”
- “Zürich `ch-wx-zurich-01` — MeteoSwiss 10-min; cite MeteoSwiss CC BY 4.0.”
- “Basel `bafu-basel-01` — BAFU Q and geodetic water level; not a flood warning.”
- “Taipei `cwa-wx-taipei-01` — CWA OGDL; cite CWA.”
- “Paris `mf-wx-paris-01` — DPObs; Etalab OL 2.0. Not `hubeau-paris-01`.”
- “Tallinn `ee-wx-tallinn-01` — Estonian Weather Service CC BY 4.0.”
- “Reykjavík `is-wx-reykjavik-01` — IMO ODC-By.”
- “Central/Western `hk-aqhi-centralwestern-01` — EPD AQHI, not PM2.5.”
- “Wien `at-wx-wien-01` — GeoSphere TAWES; cite GeoSphere Austria CC BY 4.0. Not a forecast.”
- “Vilnius `lt-wx-vilnius-01` — LHMT; not `/forecasts`.”
- “Kaunas `lt-hydro-kaunas-01` — Nemunas stage in metres; cite LHMT.”
- “Rīga `lv-wx-riga-01` — LVGMC CC0; stale DATETIME → offline.”
- “Meuse `vic-meuse-01` — Vigicrues WARNING. Green is not all-clear. Not Hub'Eau.”
- “Paris `rte-grid-01` — production-only gCO₂/kWh. Not imports/lifecycle.”
- “Athlone `ie-river-athlone-01` — OPW stage; cite OPW. Not a flood CAP.”
- “Tokyo `jp-wx-tokyo-01` — JMA AMeDAS; cite JMA. Not a forecast licence.”
- “`jma-quake-01` vs `usgs-quake-01` — cite both; JMA is official host only.”
- “`jma-typhoon-01` — NW Pacific only. Empty season is offline, not all-clear. Not NHC.”
- “Korea `kr-wx-seoul-01` — KMA ASOS; needs `GAIA_KMA_SERVICE_KEY`; Public Nuri Type 1.”
- “Praha `cz-wx-prague-01` — ČHMÚ CC BY 4.0.”

**watchbox** examples: layer `fire` + bbox; layer `flood` + US or England or France-VIC bbox; layer `ais` + Baltic or Norwegian bbox; layer `cyclone` + Atlantic or NW-Pacific bbox; layer `river` + Thames or Lobith or Seine or Rhine-Basel or Nemunas or Shannon bbox; layer `reservoir` + Oklahoma bbox; layer `weather` + Ireland or Sweden or Singapore or Hong Kong or Spain or Switzerland or Taiwan or Estonia or Iceland or Austria or Lithuania or Latvia or Japan or Brazil or Czech bbox; layer `air` + Belgium or Hong Kong AQHI bbox; layer `grid` + France bbox.

---

## Proposed — sell

The six audited SKUs from 2026-08-14 (NHC cyclone, EMSC, EA flood, PTWC, Kystverket AIS, ADSB.lol) are **wired** — see **Live now** above. They appear on the map after **GAIA then ATLAS** redeploy.

---

## Hold — do not sell yet

### EPA UV as a paid “operations desk”

**Hold for use-case sales copy** (the relay may still be LIVE on the map).

- Map pin headline is a single `uv_index` (city ZIP forecast max). That fails the operator bar: one scalar on the pin is not a multi-signal commercial desk.
- Product is an EPA **hourly forecast**, not an in-situ pyranometer — honest, but not a logistics/insurance desk until we expose a multi-city curve or co-located weather without pretending UV is measured irradiance.
- Unlock a use case when the pin/cluster sells ≥2 operator-usable fields (e.g. today’s max + hour-of-max + co-located T) without inventing instruments.

**Live now substitute:** Met Éireann / NWS / Open-Meteo weather for outdoor-ops context; do not sell UV alone as “site safety.”

### GDACS as “disaster, not a VIIRS point”

**Hold.** The operator question is meaningful, the source is not sellable under our rules yet.

- Official [GDACS Terms of use (March 2025)](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) do **not** grant CC BY 4.0. They describe model-based impact estimates, “as is”, and say alerts **must not** be used for decision-making without confirmation from mandated authorities.
- GDACS does **not** classify a FIRMS **VIIRS hotspot**. It is a UN/EC multi-hazard **warning product** / model score for international assistance — a different claim class from thermal detections and from EFFIS.
- Third-party pages that say “CC BY 4.0” are not a pin. Same bar that wired EMSC only after the FDSN page stated CC BY 4.0.

**Live now substitute:** FIRMS (detections) + EFFIS (EU current fires) + EONET (NASA events). Ask Analyst to keep those three `source`s separate.

### Geoscience Australia earthquakes as “is Australia shaking?”

**Hold** for the live HTTPS **relay**, not for the idea.

- data.gov.au “Recent Earthquakes” is **CC BY 3.0 Australia**, but the catalog record is not the same as a pinned, allowlisted GeoJSON/WFS that we have freshness-tested.
- USGS already reports Australian events that meet its magnitude cutoff. That is the honest **Live now** answer.
- Unlock when a GA NEAC machine endpoint is pinned like GeoNet (`api.geonet.org.nz`).

## What Analyst must refuse

| Prompt | Why |
|--------|-----|
| “Is this UV reading a pyranometer?” | EPA UV is a **forecast** product — cite Envirofacts; do not invent an instrument. |
| “Merge EA flood warning with Kingston stage into one ‘flood risk’.” | Warning product ≠ in-situ gauge. Keep `ea-flood-01` and `ea-*-01` separate. |
| “Declare evacuation / all-clear for this coast.” | ATLAS is not a warning authority. Quote the **warning product** or say offline. |
| “Is this FIRMS pixel a GDACS disaster?” | Different claim classes; GDACS is **Hold**. |
| “Global AIS / global lightning / BoM official AU weather.” | Not licensed for a paid SKU (GFW NC, Blitzortung NC, BoM FTP non-commercial). |
| “Water quality of this English river from USGS.” | Wrong geography; the connected USGS continuous network covers the United States, not England. |
| “Typhoon from NHC.” | Wrong basin. |

---

## Related

- Operator map: [`GUIDE.md`](GUIDE.md)
- Relay licences: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md)
- Glossary (including **watchbox**, **warning product**, **AIS**, **ADS-B**, **tropical cyclone**): [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
