# Leyenda del mapa ATLAS

**Idiomas:** [EN](../LEGEND.md) · [RU](LEGEND.ru.md) · [ES](LEGEND.es.md) · [FR](LEGEND.fr.md) · [ZH](LEGEND.zh.md)

Esta leyenda se genera desde `atlas.stations.LAYER_META` y `STATION_CATALOG`; no se edita a mano. Regenerar con `python3 scripts/atlas_legend.py --write`.

**Contrato de coordenadas:** un punto visible del mapa corresponde a una coordenada de lectura. Una estación fija usa su coordenada oficial; una lectura de cuadrícula bajo demanda usa la celda de origen/consulta devuelta. Las fuentes densas y de eventos se expanden en puntos hijos en la coordenada de la lectura o el centro de celda; el objeto padre no se dibuja como punto duplicado.

El color identifica la capa, no la gravedad ni la salud del sensor. Algunas capas relacionadas comparten color intencionadamente; se distinguen por la clave y el filtro de capa. Los estados LIVE/SIM y la disponibilidad se muestran por separado.

El catálogo define actualmente 46 capas y 934 dispositivos configurados. Las fuentes densas y de eventos pueden crear puntos de lectura adicionales en ejecución.

| Color | Clave de capa | Qué representa | Ejemplos de device_id |
|---|---|---|---|
| <span style="color:#3dd6c6">●</span> `#3dd6c6` | `weather` | Clima | `at-wx-wien-01`, `lt-wx-vilnius-01`, `lv-wx-riga-01`, `jp-wx-tokyo-01`, `cz-wx-praha-01`, `kr-wx-seoul-01` +265 |
| <span style="color:#7ec8ff">●</span> `#7ec8ff` | `air` | Aire | `hk-aqhi-centralwestern-01`, `sg-psi-central-01`, `be-aq-brussels-01`, `aurn-01` +122 |
| <span style="color:#4ea8de">●</span> `#4ea8de` | `tide` | Marea | `uhslc-01`, `noaa-tide-01`, `noaa-tide-sf`, `noaa-tide-honolulu` +14 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `river` | Ríos | `lt-hydro-kaunas-01`, `lv-hydro-riga-01`, `ie-river-athlone-01`, `bafu-basel-01` +163 |
| <span style="color:#2563eb">●</span> `#2563eb` | `marine` | Marino | `cdip-pointreyes-01`, `ndbc-01`, `om-marine-01`, `cdip-santamonica-01` +20 |
| <span style="color:#84cc16">●</span> `#84cc16` | `ghg` | GEI | `icos-htm-01`, `icos-zsf-01`, `icos-lin-01` |
| <span style="color:#c4a35a">●</span> `#c4a35a` | `grid` | Red (carbono) | `rte-grid-01`, `uk-grid-01`, `eia-01` |
| <span style="color:#ff6b4a">●</span> `#ff6b4a` | `quake` | Sismos | `jma-quake-01`, `usgs-quake-01`, `emsc-01`, `geonet-01` +2 |
| <span style="color:#e8b86d">●</span> `#e8b86d` | `energy` | Energía | `em-01` |
| <span style="color:#f97316">●</span> `#f97316` | `fire` | Incendios | `firms-fire-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `radiation` | Radiación | `safecast-01`, `safecast-tokyo`, `safecast-sf`, `safecast-denver` +10 |
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
| <span style="color:#38bdf8">●</span> `#38bdf8` | `flood` | Inundación | `vic-meuse-01`, `gfm-flood-01`, `nws-flood-01`, `ea-flood-01` +18 |
| <span style="color:#ea580c">●</span> `#ea580c` | `effis` | Incendios EFFIS | `effis-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `volcano` | Volcanes | `usgs-volcano-01` |
| <span style="color:#0891b2">●</span> `#0891b2` | `ais` | AIS público | `fintraffic-ais-01`, `kystverket-ais-01` |
| <span style="color:#e11d48">●</span> `#e11d48` | `tsunami` | Alertas de tsunami | `nws-tsunami-01`, `ptwc-01` |
| <span style="color:#7c3aed">●</span> `#7c3aed` | `cyclone` | Ciclones tropicales | `jma-typhoon-01`, `nhc-cyclone-01` |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `adsb` | ADS-B público | `adsb-lol-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `smoke` | Humo | `hms-smoke-01` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `water_quality` | Calidad del agua | `usgs-wq-01` |
| <span style="color:#1d4ed8">●</span> `#1d4ed8` | `dart` | Boyas DART | `dart-21414`, `dart-21415`, `dart-21416`, `dart-21418` +39 |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `precipitation` | Precipitación | `imerg-01` |
| <span style="color:#22c55e">●</span> `#22c55e` | `radar` | Estado NEXRAD | `nexrad-status-01` |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `atmosphere` | Atmósfera | `cams-ottawa`, `cams-berlin`, `cams-delhi`, `cams-tokyo` +2 |
| <span style="color:#84cc16">●</span> `#84cc16` | `radnet` | EPA RadNet | `radnet-ak-anchorage`, `radnet-ak-fairbanks`, `radnet-ak-juneau`, `radnet-birmingham` +136 |
| <span style="color:#a16207">●</span> `#a16207` | `soil` | Humedad del suelo | `soil-ottawa`, `soil-berlin`, `soil-delhi`, `soil-tokyo` +2 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `solar` | Irradiación solar | `solar-ottawa`, `solar-berlin`, `solar-delhi`, `solar-tokyo` +2 |
| <span style="color:#bae6fd">●</span> `#bae6fd` | `snow` | Manto de nieve | `snow-rainier`, `snow-tahoe`, `snow-mammoth`, `snow-rockies` +2 |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `sea_ice` | Hielo marino | `nsidc-ice-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `land_temperature` | Temperatura terrestre | `lst-ottawa`, `lst-berlin`, `lst-delhi`, `lst-tokyo` +2 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `aviation` | METAR aviación | `metar-kjfk-01`, `metar-klga-01`, `metar-kbos-01`, `metar-kord-01` +10 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `road` | Clima vial | `fintraffic-road-01` |
| <span style="color:#64748b">●</span> `#64748b` | `rail` | Tráfico ferroviario | `fintraffic-rail-01` |
| <span style="color:#d97706">●</span> `#d97706` | `drought` | Sequía | `usdm-01` |
| <span style="color:#0284c7">●</span> `#0284c7` | `reservoir` | Reservoirs | `usace-keys-01`, `usace-pine-01`, `usace-deni-01`, `usace-huds-01` |
| <span style="color:#facc15">●</span> `#facc15` | `uv` | UV forecast | `epa-uv-01` |
