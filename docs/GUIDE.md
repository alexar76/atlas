# ATLAS — operator & developer guide

**Languages:** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)

ATLAS is the ecosystem **physical sensor map**: live weather, air quality, tides, rivers, marine, UK grid carbon, earthquakes, wildfire, radiation, GNSS jamming, NASA EONET events, NOAA space weather, GOES lightning, NWS alerts, Argo floats, USGS geomag, floods, Copernicus EFFIS, volcanoes, public AIS (Finland / Norway), NWS/PTWC tsunami CAP, NHC tropical cyclones, public ADS-B, and optional own-edge ADS-B/AIS/IoT traffic — all plotted from [GAIA](https://iot.modelmarket.dev) relays. **New open-data devices live on GAIA; their map layers, pins, and watchboxes are ATLAS surfaces** (not a separate GAIA product UI). It appears as the **ATLAS** node on [Alien Monitor](https://monitor.modelmarket.dev/) (mini-map embed + full-map link) and ships with **ATLAS Analyst** (DeepSeek by default) — grounded on the live fleet snapshot, auto-discovered ATLAS SURFACES, a **live Hub federation** capability slice, and an embedded **AICOM / AIMarket ecosystem brief**, with mandatory **cross-layer** reasoning when evidence spans layers. Terminology: [`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md) (EN · RU · ES · FR · ZH).

**Add a sensor / pin:** [`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH) — Open-Meteo **mesh** city YAML + new LIVE **relay** checklist. GAIA device catalog / licenses: [`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md). **Operator use cases** (map + ATLAS Analyst, live vs proposed vs hold): [`OPERATOR-USE-CASES.md`](OPERATOR-USE-CASES.md) (EN · RU · ES · FR · ZH).

## Surfaces

| URL | Role |
|-----|------|
| `/` | Full MapLibre map + layers + in-view list + AI |
| `/embed` | Compact map for Alien Monitor iframe |
| `/health` | Liveness JSON |
| `/api/v1/*` | Snapshot, viewport, station detail, SSE, **watchboxes** |
| `/api/ai/*` | Providers + grounded analyst chat |

## Architecture (load model)

```
Browser ──► ATLAS (single uvicorn worker)
              │
              ├─ fleet poll (cheap) ──► GAIA gaia.fleet.status@v1
              ├─ viewport / click ────► GAIA device reads (TTL cache + single-flight)
              └─ AI ask ──────────────► DeepSeek (+ LIVE snapshot in system prompt)
```

| Mechanism | Behaviour |
|-----------|-----------|
| Fleet poll | Pins only — no stampede of per-device invokes |
| `POST /api/v1/viewport` | Refresh readings for sensors **inside the visible bbox** |
| `GET /api/v1/stations/{id}` | Human-readable card; refresh if older than detail TTL |
| Reading TTL | Default **45s** shared cache |
| Prefetch | Viewport loads **visible** first; padded neighbors + rest of catalog warm in background |
| Analyst context | Full cached fleet (not only visible bbox) + ecosystem brief only |
| Map actions | Analyst can **flyTo** places and **open** station panels (`actions[]` on `/api/ai/ask`) |
| Detail freshness | Click refreshes if older than **20s** |
| Single-flight | Concurrent clients for the same `device_id` share one GAIA call |
| SSE | Fleet snapshot fan-out to browsers (poll only as fallback) |
| Rate limit | In-app soft IP limit + nginx edge |
| Cache bypass | `force` / `fresh` have their own tight per-IP budget (429 when spent) — they multiply into GAIA invokes |
| Full refresh | `POST /api/v1/refresh` re-reads the whole catalog through GAIA's pacer, so it needs the operator token (`X-Atlas-Token`); fails closed with no `ATLAS_OPERATOR_TOKEN` set (401) |
| Detail budget | A pin click answers within `detail_budget_s` (8s) and says *refreshing*; the live read finishes into the cache. Only operator `?fresh=1` waits |
| Dropped pins | An event pin whose feed rolled still answers: the live detection within 0.05° (*matched by position*), else a card at the pin's own coordinate marked *cleared from the live window*. Only non-pin ids 404 |
| AI budget | `POST /api/ai/*` has a separate per-IP budget (LLM calls cost money) |
| Viewport contract | bbox must be lat ±90 / lon ±180; the map client wraps MapLibre bounds before sending (world spans collapse to −180/180) |

Station networks use official registry coordinates. Coordinate/grid capabilities accept buyer `lat`/`lon` and return the actual source/query cell; USGS water quality accepts a buyer bbox and expands every returned station into its own point. Event feeds carry their own reading coordinates.

## Layers & stations

The canonical, current list of all **53 data layers**, their exact colours, localized
meaning, and example device anchors is the [ATLAS map legend](LEGEND.md). It is
generated from the same runtime catalog as the map. The catalog currently has
**970 configured devices**; dense/event feeds can expand into additional reading
points at runtime.

GAIA sells the **readings** (`gaia.*.read@v1`). ATLAS is where those devices
appear as **map layers / pins** and where **watchboxes** run.

| Layer | Devices | Notes |
|-------|---------|-------|
| Weather | `om-wx-01`, `nws-01`, `om-wx-{slug}` ×50, `ws-01`, `ws-02` | Berlin Open-Meteo · NYC NWS · city mesh · 2 sims |
| Air | `om-aq-01`, `osm-01`, `sta-01`, `sc-01`, `sc-{slug}`, `om-aq-{slug}` ×50, `aq-01` | PM / CO₂ / senseBox · SC crowd (buyer lat/lon OK) · city meshes · 1 sim |
| Tide | `noaa-tide-01` | Battery, NYC gauge |
| River | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS NWIS Potomac · ECCC Humber (End-use Licence) · SMHI Abisko (CC BY 4.0) |
| Marine | `ndbc-01`, `om-marine-01` | NDBC NY Bight buoy · Open-Meteo NYC Harbor |
| Grid | `uk-grid-01` | UK carbon intensity (region) |
| Quake | `usgs-quake-01`, `geonet-01`, `emsc-01` | USGS · GeoNet NZ · EMSC FDSN (CC BY 4.0 — cite EMSC; not a USGS replacement) |
| Energy | `em-01` | Household meter simulator (no public API) |
| Fire | `firms-fire-01` | NASA FIRMS VIIRS — cite NASA FIRMS · map expands `hotspots[]` into many Wildfire pins (`firms-hs-*`); toggle other layers off to focus |
| Radiation | `safecast-01` + city anchors | Safecast **CC0** · Hub SKU = 30-day CPM; Melbourne/Adelaide archive so 2014 AU drive-grids stay on the map (`captured_at`) |
| Jamming | `cybernews-jam-01` | CyberNews GNSS — **CC BY 4.0** · event lat/lon |
| Traffic | `feeder-adsb-01`, `feeder-ais-01` | Own-edge ingest on GAIA (`GAIA_FEEDER_*`); offline until push |
| Public AIS | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic (CC BY 4.0, Finnish waters) · Kystverket/BarentsWatch (NLOD, Norwegian waters, token). **Not** one Europe blob; **not** own-edge `gaia.ais.read@v1` |
| Public ADS-B | `adsb-lol-01` | ADSB.lol ODbL 1.0 area query (default LHR). **Not** own-edge `gaia.adsb.read@v1`, not OpenSky/ADSBx |
| Natural events | `eonet-01` | NASA EONET — cite NASA EONET · map expands hotspots |
| Space weather | `swpc-01` | NOAA SWPC Kp (Boulder) + OVATION aurora cells |
| Lightning | `glm-01` | GOES-19/18 GLM via NOAA NODD (not Blitzortung) |
| Weather alerts | `nws-alerts-01` | NWS CAP centroids |
| Argo | `argo-01` → `argo-wmo-{WMO}` | Official GDAC active-float network (30-day rule); click a WMO for its latest QC-gated profile — cite DOI 10.17882/42182 |
| Geomag | `usgs-geomag-01`, `usgs-geomag-*` | All 14 official USGS observatories as separate LIVE pins; total field F (nT), source coordinates, observation age — not INTERMAGNET |
| Edge IoT | `feeder-iot-01` | Own Tasmota/TTN/SenML ingest |
| Flood | `nws-flood-01`, `ea-flood-01` | NWS CAP US · EA OGL England only (not SEPA/NRW; GloFAS WMS not scraped) |
| EFFIS | `effis-01` | Copernicus EFFIS current fires — CC BY 4.0 |
| Volcanoes | `usgs-volcano-01` | USGS elevated volcanoes |
| Tsunami alerts | `nws-tsunami-01`, `ptwc-01` | NWS CAP US · PTWC Atom Pacific — often empty; not a tide gauge; empty ≠ all-clear |
| Tropical cyclones | `nhc-cyclone-01` | NHC/CPHC CurrentStorms (U.S. PD) — Atlantic + EPac + CPac; not JTWC; empty season → offline |
| Water quality | `usgs-wq-01` | Fresh (48h default) paginated latest-continuous observations joined to USGS monitoring-locations; only parameter-qualified stations, one station = one point; per-parameter Approved/Provisional + qualifiers; bounded durable history and poll-based uptime |
| Groundwater | `usgs-groundwater-01` | Three USGS pilot wells in Maine, New York, and Kentucky. Depth in metres below local land surface, positive downward. ATLAS shows the observation time and the USGS approval status. Observations expire after 24 hours. |
| Hub’Eau groundwater | `hubeau-groundwater-01` | Eight French pilot wells report depth below the measuring reference and water elevation in NGF. The card shows the observation time and the reference for each value. |
| NOAA NWPS river forecast | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` | The card shows the highest level among the available forecast points in the next 72 hours, the issue time and the time of the peak. Heights use the local gauge datum. |
| Environment Agency tide gauges | `ea-tide-e70039`, `ea-tide-e72639`, `ea-tide-e70539`, `ea-tide-e70739`, `ea-tide-e73839` | UK coastal stations report mean sea level in metres above Ordnance Datum Newlyn (mAOD). |
| Fintraffic road events | `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` | Finnish road notices and works display the affected road geometry and the source validity period. |
| NOAA G-AIRMET | `awc-gairmet-01` | U.S. aviation forecast polygons and lines carry their hazard, issue time and valid time. |
| NDW road notices and closures | `ndw-road-srti-01`, `ndw-road-closures-01` | The `road_events` layer shows Dutch road safety notices and temporary closures with their affected geometry. Each signed snapshot expires five minutes after publication. Each action also has its own validity window. [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) |
| FMI Baltic wave buoys | `fmi-marine-103976`, `fmi-marine-108126`, `fmi-marine-108499`, `fmi-marine-134220`, `fmi-marine-134221`, `fmi-marine-134246` | Six buoys in `marine` report significant wave height. The card adds peak period, the direction waves come from and water temperature when measured at the same time. The timestamp marks the start of wave sampling. Readings expire after two hours. [FMI · CC BY 4.0](https://en.ilmatieteenlaitos.fi/download-observations-questions) |
| USDA NRCS SNOTEL snowpack | `snotel-335`, `snotel-415` | The `snow` layer shows hourly snow depth and snow water equivalent in centimetres at Berthoud Summit and Copper Mountain, Colorado. GAIA pairs measurements from the same hour that pass automated quality checks and are up to six hours old. [USDA NRCS · U.S. public domain](https://catalog.data.gov/dataset/snowpack-telemetry-network-snotel) |
| SMHI ocean observations | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` | `ocean_obs` · Four depth-specific series at three Swedish stations. Cards show salinity in PSU, dissolved oxygen in mL/L or current speed and direction, according to the station and depth. Measurements share an observation time and are at most three hours old. [SMHI · CC BY 4.0](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) |
| ECCC wildfire smoke forecast | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` | `smoke_forecast` · Three model cells near Seattle, Toronto and Calgary. Cards show the next full UTC hour’s forecast of total near-surface PM₂.₅ within the modelled smoke plume in µg/m³, along with the model run time and forecast valid time. The model run can be at most 18 hours old. [ECCC · MSC End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) |
| NOAA SWPC D-RAP | `swpc-drap-01` | `hf_absorption` · A global model grid shows the highest frequency affected by 1 dB of D-region radio absorption. The global overview shows maxima in MHz for 900 cells of 6° × 12°. Zoom in to see the original samples from all 8,100 native cells of 2° × 4°. Grids expire after 15 minutes. [NOAA SWPC](https://www.swpc.noaa.gov/products/d-region-absorption-predictions-d-rap) |
| BfS ambient gamma dose rate | `bfs-odl-01` | `radiation` · German monitoring stations show validated hourly ambient gamma dose equivalent rates in nSv/h. Cards show the end of the observation hour. Observations expire after two hours. [BfS · DL-DE-BY 2.0](https://www.imis.bfs.de/geoportal/resources/sitepolicy.html) |
| GeoNet coastal water height | `geonet-coastal-auct`, `geonet-coastal-wlgt`, `geonet-coastal-taut`, `geonet-coastal-gist`, `geonet-coastal-jbtt` | `tide` · Five New Zealand stations show water height in metres above each local pressure sensor. Observations expire after five minutes. [GeoNet · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) |
| ČHMÚ river observations | `chmi-river-042000`, `chmi-river-101800`, `chmi-river-200100` | `river` · Three Czech gauges show preliminary observed stage and discharge, with water temperature when recorded at the same time. Observations expire after two hours. [ČHMÚ · CC BY 4.0](https://www.chmi.cz/-/kde-najdu-otev%C5%99en%C3%A1-data-%C4%8Dhm%C3%BA-) |
| Entur train positions | `entur-rail-vyg-01` | `rail` · The map shows recent observed positions of Vy trains in Norway and their line when available. Positions expire at the provider’s validity limit or after five minutes, whichever comes first. [Entur · NLOD](https://developer.entur.no/terms-of-service) |
| UK Power Networks live outages | `ukpn-live-faults-01` | `power_outages` · Current faults in the operator’s service area. Cards show the approximate affected area, customers affected and the provider’s estimated restoration time when available. The snapshot expires after 30 minutes. [UK Power Networks · CC BY 4.0](https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults) |
| NOAA PORTS bridge air gap | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` | `bridge_clearance` · Three US bridge sensors show the preliminary vertical distance from the water surface to a fixed reference on the bridge, in metres. Cards include the sample standard deviation and source flags. Observations expire after 18 minutes. Use official NOAA PORTS and navigation charts for passage decisions. [NOAA NOS CO-OPS](https://opendap.co-ops.nos.noaa.gov/erddap/info/IOOS_Air_Gap/index.html) |
| NOAA AOML ocean drifters | `aoml-drifters-01` | `ocean_drifters` · Global reports show each drifting buoy’s last observed position and sea-surface temperature, with sea-level pressure when reported. Observations expire after six hours. [NOAA AOML / OSMC · CC0 1.0](https://osmc.noaa.gov/erddap/info/OSMC_flattened/index.json) |
| Bike Share Toronto | `toronto-bikeshare-01` | `bikeshare` · Station cards show available bikes, e-bikes where reported, open docks and rental and return status. Reports expire after five minutes. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| Toronto road restrictions | `toronto-road-restrictions-01` | `road_events` · City notices show the affected point or stretch of road during an active restriction, including scheduled recurring restrictions. The source snapshot expires after 15 minutes. Each notice has its own active interval. [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| ARSO river observations | `arso-river-1060`, `arso-river-3660`, `arso-river-5078`, `arso-river-8080` | `river` · Four Slovenian gauges report preliminary stage in metres above the local gauge zero and discharge in m³/s. Cards include water temperature when measured at the same time. Observations expire after two hours. [ARSO](https://kazalci.arso.gov.si/en/content/legal-note) |
| Kartverket coastal water levels | `kartverket-tide-bgo`, `kartverket-tide-osl`, `kartverket-tide-svg`, `kartverket-tide-tos`, `kartverket-tide-trd` | `tide` · Five Norwegian gauges show observed coastal water level in metres relative to the national NN2000 vertical datum. Observations expire after two hours. [Kartverket · CC BY 4.0](https://vannstand.kartverket.no/tideapi_en.html) |
| Flood impact locations | `usgs-rtfi-01` | A nearby USGS gauge exceeded the surveyed threshold for a road, bridge, building, or other site. Preliminary indication of possible inundation. An empty feed only means no qualifying points in the covered sites. |
| DART | `noaa-dart-01`, `dart-*` | All 43 active stations from the checked-in official NDBC directory |
| EPA RadNet | `radnet-*` | All 140 official EPA monitor coordinates, not three demo cities |
| NEXRAD status | `nexrad-status-01` | Every returned WSR-88D site at its own coordinate; status, not reflectivity |
| Coordinate grids/models | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | Buyer `lat`/`lon`; ATLAS uses the returned source/query-cell coordinate |

The City of Toronto’s road restrictions and bike share data carry this attribution. “Contains information licensed under the Open Government Licence – Toronto.” [Licence](https://open.toronto.ca/open-data-licence/)

### Charging, hazards and field observations

| Source | GAIA | ATLAS | Data and limits | Source and terms |
| --- | --- | --- | --- | --- |
| NDW DOT-NL charging | `gaia.ev.charging.read@v1` · `ndw-ev-charging-01` | `ev_charging` | Public Dutch charging sites report available and total connectors by type and power. The default query covers Utrecht. Regional requests cover up to 4 square degrees. Hub pages contain up to 500 sites and use the snapshot token to continue. Snapshots expire after four minutes. | [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) · [GeoJSON API](https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/) |
| BC wildfire locations and perimeters | `gaia.fire.perimeters.read@v1` · `bc-wildfire-01` | `wildfire_perimeters` | Current fires in British Columbia carry their status and the latest reported perimeter where available. The map distinguishes the feed update time from the date of each perimeter. The feed snapshot expires after one hour. | [BC Wildfire Service · OGL–BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) · [Perimeters](https://open.canada.ca/data/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1) |
| MeteoSwiss A7 pollen | `gaia.pollen.read@v1` · `ch-pollen-*` | `pollen` | Fifteen registered automatic stations report hourly concentrations for seven pollen types in grains per cubic metre. The map preserves a measured zero and expires observations after two hours. | [Source: MeteoSwiss · CC BY 4.0](https://opendatadocs.meteoswiss.ch/general/terms-of-use) · [A7](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations) |
| Irish Weather Buoy Network | `gaia.marine.read@v1` · `ie-buoy-m2`, `ie-buoy-m3`, `ie-buoy-m5`, `ie-buoy-m6` | `marine` | Four pilot buoys report wave height, period and direction, with sea temperature and wind when available. Readings expire after two hours. Source quality code 0 means unknown quality and code 1 means good. | [Marine Institute and Met Éireann · CC BY 4.0](https://erddap.marine.ie/erddap/info/IWBNetwork/index.html) |
| Australian AODN/IMOS wave buoys | `gaia.marine.read@v1` · `au-wave-apollo-bay`, `au-wave-wilsons-prom`, `au-wave-wooli` | `marine` | Three pilot buoys report significant wave height, peak period and the direction the waves come from when available. GAIA accepts source quality code 1 and expires observations after two hours. | [AODN / IMOS · CC BY 4.0](https://registry.opendata.aws/aodn_wave_buoy_realtime_nonqc/) |
| GeoNet New Zealand volcanoes and cameras | `gaia.volcano.read@v1` · `geonet-volcano-01` | `volcano` | Twelve monitored volcanoes carry their current alert level and aviation colour code. Status expires 30 minutes after retrieval. Available camera thumbnails show their own capture time and expire after 30 minutes. | [GeoNet / Earth Sciences New Zealand and sponsors · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) · [Cameras](https://doi.org/10.21420/vq6s-w222) |
| NOAA SPC Local Storm Reports | `gaia.storm.reports.read@v1` · `noaa-spc-storm-reports-01` | `storm_reports` | Preliminary U.S. tornado, hail and wind reports appear within a rolling 24-hour window. Each point carries the reported event time. | [NOAA/NWS SPC · U.S. public domain](https://www.weather.gov/disclaimer) · [CSV](https://www.spc.noaa.gov/climo/reports/today.csv) |
| NOAA Washington VAAC ash advisories | `gaia.volcanic.ash.read@v1` · `noaa-vaac-ash-01` | `volcanic_ash` | Published ash polygons carry their altitude bounds, issue time and observation or forecast valid time. An advisory expires at the earlier of the next-advisory time and seven hours after issuance. | [NOAA Washington VAAC](https://ospo.noaa.gov/products/atmosphere/vaac/messages.html) · [NOAA reuse policy](https://www.noaa.gov/office-education/outreach-communication/faq) |
| Digital Earth Australia hotspots | `gaia.fire.hotspots.read@v1` · `dea-hotspots-01` | `fire_hotspots` | Australian satellite thermal detections, including Himawari-9, appear within the queried area and a rolling three-hour window. The map loads up to 800 detections and identifies incomplete coverage. | [Geoscience Australia · CC BY 4.0](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/) · [DEA Hotspots dataset](https://pid.geoscience.gov.au/dataset/ga/111881) |

British Columbia data carry the credit “Contains information licensed under the Open Government Licence – British Columbia.” Australian buoy data carry the credit “Data was sourced from Australia’s Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)”.

On the full map, **NOAA radar imagery** shows the NOAA/NWS MRMS base-reflectivity raster for the continental United States, Alaska, Hawaii, the Caribbean, and Guam. ATLAS displays a 10-minute UTC window ending at the latest published source time and hides the mosaic once that time is more than 20 minutes old. The raster uses the source reflectivity palette. **NEXRAD status** is a separate layer for station health. [NOAA image service](https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer) · [NWS data policy](https://www.weather.gov/disclaimer)

Mesh cities: Ottawa · New Delhi · Tokyo · Sydney · São Paulo · Lagos · Cairo ·
Cape Town · Singapore · Dubai · Los Angeles · Mexico City · Moscow · Paris ·
Reykjavík · Anchorage · Buenos Aires · Jakarta · Nairobi · Vancouver.

## HTTP API

### `GET /api/v1/snapshot`

Pins + any cached headlines / values.

### `POST /api/v1/viewport`

```json
{ "west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7, "force": false }
```

Returns `requested`, `cache_hits`, `stations`, and a full `snapshot`.

### `GET /api/v1/stations/{device_id}?fresh=0`

Human-readable detail: `title`, `summary`, `metrics[]` (`label` / `value` / `hint`), `status_line`.

### `GET /api/v1/stream`

SSE `event: snapshot` fan-out.

### Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

A **watchbox** is a saved geographic “watch frame”: a bbox (west/south/east/north)
plus a filter of map layers. Think “alert me when something LIVE appears in this
rectangle on these layers” — not a GAIA device read.

- **Subscribe** (`atlas.watchbox.subscribe@v1` / REST) — create/list/unsubscribe the
  saved frame. Free plumbing; not the billable Hub SKU.
- **Check** (`atlas.watchbox.check@v1`) — evaluate the frame against the current
  fleet snapshot; returns matches + a content receipt. This is the Hub-billable
  product (also callable with an ephemeral bbox + layers, no saved id).

Only **free-to-commercialize** catalog layers (`ALLOWED_WATCHBOX_LAYERS`). NC feeds
are not on ATLAS at all.

**Ownership.** The registry is not public. Every watchbox gets an **owner token**,
returned exactly once in the create response (like `webhook_secret`) and stored only as
a SHA-256 digest — list/get never echo it and it cannot be recovered later. Send it as
`X-Atlas-Watchbox-Token: <token>` (or `Authorization: Bearer <token>`); the operator
token `X-Atlas-Token` works everywhere the owner token does. Anonymous callers get
`401`; a wrong token gets the same `404` as an id that never existed, so the registry
cannot be enumerated.

Creation is operator-only unless `ATLAS_WATCHBOX_OPEN_SIGNUP=1` enables self-serve
(bounded by `ATLAS_WATCHBOX_SELF_SERVE_MAX`, default 200 live boxes).

| Method | Path | Who |
|--------|------|-----|
| `GET` | `/api/v1/watchboxes` | owner (own boxes only) or operator (all) |
| `POST` | `/api/v1/watchboxes` | operator, or anyone when self-serve is on |
| `GET` / `DELETE` | `/api/v1/watchboxes/{id}` | owner or operator |
| `GET` | `/api/v1/watchboxes/{id}/log` | owner or operator |
| `POST` | `/api/v1/watchboxes/{id}/check` | owner or operator |

**`DELETE` is an unsubscribe, not a purge.** Monitoring stops; the registry row and the
signed monitor log stay readable with the owner token. Dropping the row would orphan the
log — the checks would still be in SQLite but `…/log` resolves the registry first, so
the evidence would be unreachable while the delete reported success. `?purge=true`
destroys the row and is operator-only.

```bash
# create — save the owner_token from this response, it is shown once
curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes \
  -H 'Content-Type: application/json' -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" \
  -d '{"west":-10,"south":35,"east":40,"north":60,"layers":["fire","jamming"],"label":"EU hazards"}'

curl -s -X POST https://atlas.modelmarket.dev/api/v1/watchboxes/<id>/check \
  -H "X-Atlas-Watchbox-Token: $OWNER_TOKEN"

# the monitoring evidence — still readable after unsubscribing
curl -s https://atlas.modelmarket.dev/api/v1/watchboxes/<id>/log \
  -H "X-Atlas-Watchbox-Token: $OWNER_TOKEN"
```

Through the Hub the token travels in the invoke body, since the hub forwards the input
rather than our headers — `{"capability_id":"atlas.watchbox.check@v1","input":
{"watchbox_id":"<id>","owner_token":"<token>"}}`. Ephemeral bbox+layers checks need no
token.

### Composite products (ATLAS &gt; parts)

| SKU | What it does | Convenience | Hub invoke |
|-----|--------------|-------------|------------|
| `atlas.situation.brief@v1` | Cross-layer scored brief for a bbox — defaults include flood, EFFIS, lightning, volcano, alerts, events, public AIS, tsunami (not spacewx/geomag/argo); refuse if empty | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | FIRMS **and/or** Copernicus EFFIS in bbox + nearest LIVE weather (two lists, dual attribution; not a forecast) | `POST /api/v1/products/fire-weather` | same |
| `atlas.smoke.operations@v1` | Asset `lat`/`lon` → **point-in-polygon** against the complete signed NOAA HMS smoke geometry (rings **and** holes, date-line safe) fused with PM2.5/AQI at the same coordinate; refuses on a truncated inventory or missing air data. Qualitative analysis, not measured PM2.5, not an evacuation order | `POST /api/v1/products/smoke-operations` | same |
| `atlas.nearest.read@v1` | Nearest LIVE pin to buyer `lat`/`lon` (layer filter, `max_km`, receipt) | `POST /api/v1/products/nearest` | same |
| `atlas.point.read@v1` | Exact clickable `point_id` → values, provenance, parent GAIA rail, signed ATLAS receipt | `POST /api/v1/products/point` | same |
| `atlas.watchbox.check@v1` | Evaluate saved or ephemeral watchbox → matches + receipt | watchbox `…/check` | same |
| `atlas.mesh.sample@v1` | Halton (Lattice-equivalent) sample of a **named licensed in-situ mesh** so an agent cannot cherry-pick stations. Not ECVRF (Sortes is a sibling hop), not Open-Meteo | `POST /api/v1/products/mesh-sample` | same |
| `atlas.field.consensus@v1` | Robust consensus (median / trimmed mean / Tukey biweight / DeGroot) of LIVE in-situ readings on that mesh. One broken station cannot move the number. Not a forecast, not Open-Meteo-as-station | `POST /api/v1/products/field-consensus` | same |
| `atlas.field.posterior@v1` | Spatial RBF GP posterior of the **current snapshot** + highest-variance next pin. Interpolates now; not a forecast | `POST /api/v1/products/field-posterior` | same |
| `atlas.field.shape@v1` | H0 persistence of LIVE pins (connected components vs radius). Not Betti-1 loops, not an AQI | `POST /api/v1/products/field-shape` | same |

Licensed meshes (Estonia EWS `ee-wx`, PEGEL, Hub'Eau, …): `GET /api/v1/field-meshes`. Open-Meteo is refused.

Hub UI blurbs (EN · RU · ES · FR · ZH): `aimarket-hub/cap-descriptions-i18n.json`.

```bash
curl -s https://atlas.modelmarket.dev/.well-known/ai-market.json
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/fire-weather \
  -H 'Content-Type: application/json' \
  -d '{"west":-125,"south":32,"east":-114,"north":42,"limit":24}'
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/smoke-operations \
  -H 'Content-Type: application/json' \
  -d '{"lat":37.7749,"lon":-122.4194,"asset_id":"yard-7"}'
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/nearest \
  -H 'Content-Type: application/json' \
  -d '{"lat":52.52,"lon":13.41,"layer":"weather"}'
curl -s -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.point.read@v1","input":{"point_id":"argo-wmo-1901760","fresh":true}}'
curl -s https://atlas.modelmarket.dev/api/v1/field-meshes
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/mesh-sample \
  -H 'Content-Type: application/json' \
  -d '{"mesh_id":"ee-wx","count":8}'
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/field-consensus \
  -H 'Content-Type: application/json' \
  -d '{"mesh_id":"ee-wx","quantity":"temperature_c"}'
curl -s -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.field.posterior@v1","input":{"mesh_id":"ee-wx","lat":58.6,"lon":25.0}}'
curl -s -X POST https://atlas.modelmarket.dev/api/v1/products/field-shape \
  -H 'Content-Type: application/json' \
  -d '{"mesh_id":"pegel"}'
```

Fail-closed when the bbox has no LIVE readings — never pad with SIM. Fire product
requires NASA FIRMS attribution. **Nearest** takes buyer `lat`/`lon` (ATLAS map
index); GAIA device reads stay `device_id`-anchored.
Every interactive sensor/event/observation exposes the same exact `point_id` to
the UI and agents. Catalog sensors and Argo WMO platforms refresh directly;
dense event pixels are selected from the latest parent snapshot and state that
evidence boundary in the response rather than pretending the upstream accepts
an individual-pixel query.

### `GET /api/ai/providers`

Default: `deepseek_api` / `deepseek-v4-pro`.

### `POST /api/ai/ask`

```json
{
  "question": "Write a situation report for sensors in view",
  "locale": "en",
  "report": true,
  "bbox": { "west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7 }
}
```

Server injects the LIVE ATLAS snapshot into the system prompt (clients cannot forge numbers). Optional `station_ids`, `provider`, `model_role` (`heavy`|`light`).

With **no** provider configured (no cloud key and `ATLAS_LOCAL_LLM_ENABLED` off) an offline stub answers from the reading cache instead of failing. Local backends (Ollama / LM Studio) only count as available behind that opt-in — otherwise a keyless server would "have" a provider it cannot reach.

**Auto-learning:** ATLAS Analyst builds `ATLAS SURFACES` + `snapshot.capabilities` from `STATION_CATALOG` / `LAYER_META` / watchboxes (`atlas/atlas/capability_awareness.py`). Adding a mirrored GAIA device to the catalog is enough — no hard-coded prompt edit per SKU. Topic-scope markers are derived the same way.

## Alien Monitor

Hardwired node `atlas` (`group: physical`):

- Poll: `ALIEN_ATLAS_URL` → `/health` + `/api/v1/monitor`
- Panel: stations + iframe `/embed` + **Open full map**
- Env: `ALIEN_PUBLIC_ATLAS_URL` (default `https://atlas.modelmarket.dev`)

## Deploy

```bash
# PyPI package (map UI bundled in the wheel)
pip install aimarket-atlas
export ATLAS_GAIA_URL=https://iot.modelmarket.dev
atlas --host 127.0.0.1 --port 9330

# local Docker
docker compose -f atlas/docker-compose.local.yml up -d --build
# → http://127.0.0.1:9330/

# production (ecosystem network + nginx)
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
# nginx: deploy/nginx/atlas.modelmarket.dev.conf
# or: sudo ./scripts/deploy_atlas.sh
```

Loopback bind `127.0.0.1:9330` — TLS only via nginx.

## Environment (`ATLAS_` prefix + LLM)

All ATLAS settings carry the `ATLAS_` prefix (`ATLAS_PUBLIC_URL`, …); provider
API keys use their vendor names (`DEEPSEEK_API_KEY`, …).

| Variable | Default | Purpose |
|----------|---------|---------|
| `ATLAS_PUBLIC_URL` | `https://atlas.modelmarket.dev` | Links in monitor payload |
| `ATLAS_GAIA_URL` | `https://iot.modelmarket.dev` | Upstream gateway |
| `ATLAS_HUB_URL` | `https://modelmarket.dev` | Live federation catalog for Analyst |
| `ATLAS_FEDERATION_CACHE_TTL_S` | `120` | Hub manifest/peers cache |
| `ATLAS_ANALYST_FIRE_PIN_LIMIT` | `24` | Max FIRMS hotspots in Analyst prompt (map keeps all) |
| `ATLAS_FLEET_POLL_INTERVAL_S` | `30` | Pin/fleet cadence |
| `ATLAS_READING_TTL_S` | `45` | Reading cache TTL |
| `ATLAS_VIEWPORT_PAD_DEG` | `25` | Lazy neighbor prefetch pad (degrees) |
| `ATLAS_WARM_ALL_ON_FLEET` | `true` | Background-warm full catalog after fleet poll |
| `ATLAS_ANALYST_WARM_ALL` | `true` | Analyst gets full cached fleet, not only bbox |
| `ATLAS_DETAIL_FRESH_S` | `20` | Click refresh threshold |
| `ATLAS_RATE_LIMIT_PER_MIN` | `180` | Soft per-IP limit (all `/api/*`) |
| `ATLAS_RATE_LIMIT_AI_PER_MIN` | `12` | Per-IP budget for `POST /api/ai/*` |
| `ATLAS_RATE_LIMIT_FORCE_PER_MIN` | `6` | Per-IP budget for `force` / `fresh` / `/refresh` |
| `ATLAS_OPERATOR_TOKEN` | — | When set, `X-ATLAS-Token` holders skip the cache-bypass budget |
| `ATLAS_TRUSTED_PROXY_HOPS` | `1` | Proxies in front of ATLAS. The budget key comes from `X-Real-IP` (nginx overwrites it), else this far from the **right** of `X-Forwarded-For`; `0` ignores both headers (no proxy) |
| `ATLAS_TRUSTED_PROXIES` | loopback | Peers whose proxy headers count at all: addresses, CIDRs, host names, `gateway` (the container's default route: the host's nginx for a published port). Any other peer is keyed on itself (since 0.3.3) |
| `ATLAS_MONITOR_STATION_LIMIT` | `24` | Stations in the Alien Monitor payload (ranked) |
| `ATLAS_GAIA_CONCURRENCY` | `4` | Parallel GAIA invokes |
| `ATLAS_LOCAL_LLM_ENABLED` | `false` | Count Ollama / LM Studio as available providers |
| `ATLAS_LLM_MAX_RETRIES` | `3` | LLM retries on 429/5xx/timeout |
| `DEEPSEEK_API_KEY` | — | **Production LLM key** |
| `ATLAS_LLM_PROVIDER` | `deepseek_api` | Default provider |
| `ATLAS_LLM_MODEL` | `deepseek-v4-pro` | Heavy model |
| `ATLAS_LLM_MODEL_LIGHT` | `deepseek-v4-flash` | Light model |
| `ATLAS_LLM_CONFIG` | `/app/config/model_providers.yaml` | Optional YAML |

## Tests

```bash
cd atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

**101 tests.** Coverage areas: formatters, catalog/bbox + viewport normalization,
aggregator cache & single-flight, HTTP API + edge guards (cache-bypass / AI
budgets, operator token), map actions & place aliases, prompt firewall, AI
grounding / DeepSeek defaults / offline stub. **No live GAIA** required —
invokes are mocked.

## Honesty & attribution

- ATLAS is a **map + analyst + watchboxes** over GAIA relays; it does not own sensors.
- Open-Meteo: CC BY 4.0 · NWS / USGS / NOAA: U.S. Government public domain · UK Carbon Intensity: National Grid ESO open data · FIRMS: cite NASA · Safecast: CC0 · CyberNews GNSS: CC BY 4.0.
- Live keys on GAIA prove **relay custody**, not hardware ownership.
- Edge traffic pins stay offline until **your** feeder pushes — never third-party NC aggregators.
