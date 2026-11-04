# Leyenda del mapa ATLAS

**Idiomas:** [EN](../LEGEND.md) · [RU](LEGEND.ru.md) · [ES](LEGEND.es.md) · [FR](LEGEND.fr.md) · [ZH](LEGEND.zh.md)

Esta leyenda se genera desde `atlas.stations.LAYER_META` y `STATION_CATALOG`; no se edita a mano. Regenerar con `python3 scripts/atlas_legend.py --write`.

**Contrato de coordenadas:** un punto visible del mapa corresponde a una coordenada de lectura. Una estación fija usa su coordenada oficial; una lectura de cuadrícula bajo demanda usa la celda de origen/consulta devuelta. Las fuentes densas y de eventos se expanden en puntos hijos en la coordenada de la lectura o el centro de celda; el objeto padre no se dibuja como punto duplicado.

El color identifica la capa, no la gravedad ni la salud del sensor. Algunas capas relacionadas comparten color intencionadamente; se distinguen por la clave y el filtro de capa. Los estados LIVE/SIM y la disponibilidad se muestran por separado.

El catálogo define actualmente 66 capas y 1042 dispositivos configurados. Las fuentes densas y de eventos pueden crear puntos de lectura adicionales en ejecución.

El mapa completo también ofrece **Imágenes de radar de NOAA**, un ráster de reflectividad NOAA/NWS MRMS fuera del recuento de capas de datos. La fila `radar` muestra el estado de las estaciones NEXRAD.

En `flood`, `usgs-rtfi-01` identifica puntos evaluados donde se ha superado provisionalmente un umbral. La capa `groundwater` muestra la profundidad bajo el terreno local de tres pozos piloto del USGS. Hub’Eau añade ocho pozos franceses con su referencia de medición y cotas NGF.

| Color | Clave de capa | Qué representa | Ejemplos de device_id |
|---|---|---|---|
| <span style="color:#bef264">●</span> `#bef264` | `ev_charging` | Recarga de vehículos eléctricos | `ndw-ev-charging-01` |
| <span style="color:#f97316">●</span> `#f97316` | `wildfire_perimeters` | Perímetros de incendios | `bc-wildfire-01` |
| <span style="color:#fde047">●</span> `#fde047` | `pollen` | Polen medido | `ch-pollen-pbe`, `ch-pollen-pbs`, `ch-pollen-pbu`, `ch-pollen-pcf` +11 |
| <span style="color:#7dd3fc">●</span> `#7dd3fc` | `storm_reports` | Avisos de tormentas observadas | `noaa-spc-storm-reports-01` |
| <span style="color:#c4b5fd">●</span> `#c4b5fd` | `volcanic_ash` | Ceniza volcánica | `noaa-vaac-ash-01` |
| <span style="color:#fb923c">●</span> `#fb923c` | `fire_hotspots` | Focos térmicos de Australia | `dea-hotspots-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `power_outages` | Cortes eléctricos | `ukpn-live-faults-01` |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `bridge_clearance` | Gálibo de puentes | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `ocean_drifters` | Boyas a la deriva | `aoml-drifters-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `bikeshare` | Bicicletas compartidas | `toronto-bikeshare-01` |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `ocean_obs` | Observaciones oceánicas | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` |
| <span style="color:#c084fc">●</span> `#c084fc` | `smoke_forecast` | Pronóstico de humo | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` |
| <span style="color:#f472b6">●</span> `#f472b6` | `hf_absorption` | Absorción de radio HF | `swpc-drap-01` |
| <span style="color:#3dd6c6">●</span> `#3dd6c6` | `weather` | Clima | `at-wx-wien-01`, `lt-wx-vilnius-01`, `lv-wx-riga-01`, `jp-wx-tokyo-01`, `cz-wx-praha-01`, `kr-wx-seoul-01` +265 |
| <span style="color:#7ec8ff">●</span> `#7ec8ff` | `air` | Aire | `hk-aqhi-centralwestern-01`, `sg-psi-central-01`, `be-aq-brussels-01`, `aurn-01` +122 |
| <span style="color:#4ea8de">●</span> `#4ea8de` | `tide` | Marea | `kartverket-tide-bgo`, `geonet-coastal-auct`, `ea-tide-e70039`, `uhslc-01` +29 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `river` | Ríos | `arso-river-1060`, `chmi-river-042000`, `lt-hydro-kaunas-01`, `lv-hydro-riga-01`, `ie-river-athlone-01` +169 |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `river_forecast` | Previsión del nivel de los ríos | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` |
| <span style="color:#2563eb">●</span> `#2563eb` | `marine` | Marino | `ie-buoy-m2`, `au-wave-apollo-bay`, `fmi-marine-103976`, `cdip-pointreyes-01`, `ndbc-01`, `om-marine-01` +31 |
| <span style="color:#84cc16">●</span> `#84cc16` | `ghg` | GEI | `icos-htm-01`, `icos-zsf-01`, `icos-lin-01` |
| <span style="color:#c4a35a">●</span> `#c4a35a` | `grid` | Red (carbono) | `rte-grid-01`, `uk-grid-01`, `eia-01` |
| <span style="color:#ff6b4a">●</span> `#ff6b4a` | `quake` | Sismos | `jma-quake-01`, `usgs-quake-01`, `emsc-01`, `geonet-01` +2 |
| <span style="color:#e8b86d">●</span> `#e8b86d` | `energy` | Energía | `em-01` |
| <span style="color:#f97316">●</span> `#f97316` | `fire` | Incendios | `firms-fire-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `radiation` | Radiación | `bfs-odl-01`, `safecast-01`, `safecast-tokyo`, `safecast-sf` +11 |
| <span style="color:#e879f9">●</span> `#e879f9` | `jamming` | Interferencia GNSS | `cybernews-jam-01` |
| <span style="color:#34d399">●</span> `#34d399` | `gnss` | Integridad GNSS | `gnss-euref-01`, `gnss-ga-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `traffic` | Tráfico edge | `feeder-adsb-01`, `feeder-ais-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `events` | Eventos naturales | `eonet-01` |
| <span style="color:#818cf8">●</span> `#818cf8` | `spacewx` | Clima espacial | `swpc-01`, `swpc-solarwind-01`, `swpc-xray-01`, `donki-01` |
| <span style="color:#fde047">●</span> `#fde047` | `lightning` | Rayos | `glm-01` |
| <span style="color:#fb7185">●</span> `#fb7185` | `alerts` | Alertas | `nws-alerts-01`, `naad-01` |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `argo` | Flotadores Argo | `argo-01` |
| <span style="color:#c084fc">●</span> `#c084fc` | `geomag` | Geomagnetismo | `usgs-geomag-01`, `usgs-geomag-brw`, `usgs-geomag-bsl`, `usgs-geomag-cmo` +10 |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `iot` | IoT edge | `feeder-iot-01` |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `flood` | Inundación | `vic-meuse-01`, `gfm-flood-01`, `nws-flood-01`, `ea-flood-01` +19 |
| <span style="color:#ea580c">●</span> `#ea580c` | `effis` | Incendios EFFIS | `effis-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `volcano` | Volcanes | `geonet-volcano-01`, `usgs-volcano-01` |
| <span style="color:#0891b2">●</span> `#0891b2` | `ais` | AIS público | `fintraffic-ais-01`, `kystverket-ais-01` |
| <span style="color:#e11d48">●</span> `#e11d48` | `tsunami` | Alertas de tsunami | `nws-tsunami-01`, `ptwc-01` |
| <span style="color:#7c3aed">●</span> `#7c3aed` | `cyclone` | Ciclones tropicales | `jma-typhoon-01`, `nhc-cyclone-01` |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `adsb` | ADS-B público | `adsb-lol-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `smoke` | Humo | `hms-smoke-01` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `water_quality` | Calidad del agua | `usgs-wq-01` |
| <span style="color:#0d9488">●</span> `#0d9488` | `groundwater` | Aguas subterráneas | `usgs-groundwater-01`, `hubeau-groundwater-01` |
| <span style="color:#1d4ed8">●</span> `#1d4ed8` | `dart` | Boyas DART | `dart-21414`, `dart-21415`, `dart-21416`, `dart-21418` +39 |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `precipitation` | Precipitación | `imerg-01` |
| <span style="color:#22c55e">●</span> `#22c55e` | `radar` | Estado NEXRAD | `nexrad-status-01` |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `atmosphere` | Atmósfera | `cams-ottawa`, `cams-berlin`, `cams-delhi`, `cams-tokyo` +2 |
| <span style="color:#84cc16">●</span> `#84cc16` | `radnet` | EPA RadNet | `radnet-ak-anchorage`, `radnet-ak-fairbanks`, `radnet-ak-juneau`, `radnet-birmingham` +136 |
| <span style="color:#a16207">●</span> `#a16207` | `soil` | Humedad del suelo | `soil-ottawa`, `soil-berlin`, `soil-delhi`, `soil-tokyo` +2 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `solar` | Irradiación solar | `solar-ottawa`, `solar-berlin`, `solar-delhi`, `solar-tokyo` +2 |
| <span style="color:#bae6fd">●</span> `#bae6fd` | `snow` | Manto de nieve | `snotel-335`, `snow-rainier`, `snow-tahoe`, `snow-mammoth` +4 |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `sea_ice` | Hielo marino | `nsidc-ice-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `land_temperature` | Temperatura terrestre | `lst-ottawa`, `lst-berlin`, `lst-delhi`, `lst-tokyo` +2 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `aviation` | METAR aviación | `metar-kjfk-01`, `metar-klga-01`, `metar-kbos-01`, `metar-kord-01` +10 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `road` | Clima vial | `fintraffic-road-01` |
| <span style="color:#64748b">●</span> `#64748b` | `rail` | Tráfico ferroviario | `entur-rail-vyg-01`, `fintraffic-rail-01` |
| <span style="color:#d97706">●</span> `#d97706` | `drought` | Sequía | `usdm-01` |
| <span style="color:#0284c7">●</span> `#0284c7` | `reservoir` | Reservoirs | `usace-keys-01`, `usace-pine-01`, `usace-deni-01`, `usace-huds-01` |
| <span style="color:#facc15">●</span> `#facc15` | `uv` | UV forecast | `epa-uv-01` |
| <span style="color:#fb923c">●</span> `#fb923c` | `road_events` | Avisos viales | `toronto-road-restrictions-01`, `ndw-road-srti-01`, `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` +1 |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `aviation_hazards` | Pronósticos de riesgos aéreos | `awc-gairmet-01` |
| <span style="color:#eab308">●</span> `#eab308` | `power_price` | Precio de la electricidad | `smard-price-de-lu`, `smard-price-at`, `smard-price-be`, `smard-price-no2` +11 |
| <span style="color:#10b981">●</span> `#10b981` | `imagery` | Imágenes satelitales | `s2-tempelhof`, `s2-wannsee`, `s2-grandcanyon`, `s2-amazon` +1 |
| <span style="color:#f43f5e">●</span> `#f43f5e` | `actuator` | Actuadores | `plug-sim-01` |
