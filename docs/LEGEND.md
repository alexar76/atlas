# ATLAS map legend

**Languages:** [EN](LEGEND.md) · [RU](i18n/LEGEND.ru.md) · [ES](i18n/LEGEND.es.md) · [FR](i18n/LEGEND.fr.md) · [ZH](i18n/LEGEND.zh.md)

This legend is generated from `atlas.stations.LAYER_META` and `STATION_CATALOG`; do not edit it by hand. Regenerate it with `python3 scripts/atlas_legend.py --write`.

**Coordinate contract:** one visible map point is one reading coordinate. A fixed station uses its official anchor; an on-demand grid read uses the returned source/query cell. Dense and event feeds are expanded into child points at the reading coordinate or cell centre; their parent object is not plotted as a duplicate point.

Colour identifies the layer, not severity or sensor health. Some related layers intentionally share a colour; use the layer key and filter to distinguish them. LIVE/SIM state and availability are shown separately.

The catalog currently defines 46 layers and 934 configured devices. Event and dense feeds may create additional reading points at runtime.

| Colour | Layer key | Meaning | Example device IDs |
|---|---|---|---|
| <span style="color:#3dd6c6">●</span> `#3dd6c6` | `weather` | Weather | `at-wx-wien-01`, `lt-wx-vilnius-01`, `lv-wx-riga-01`, `jp-wx-tokyo-01`, `cz-wx-praha-01`, `kr-wx-seoul-01` +265 |
| <span style="color:#7ec8ff">●</span> `#7ec8ff` | `air` | Air quality | `hk-aqhi-centralwestern-01`, `sg-psi-central-01`, `be-aq-brussels-01`, `aurn-01` +122 |
| <span style="color:#4ea8de">●</span> `#4ea8de` | `tide` | Tide | `uhslc-01`, `noaa-tide-01`, `noaa-tide-sf`, `noaa-tide-honolulu` +14 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `river` | Rivers | `lt-hydro-kaunas-01`, `lv-hydro-riga-01`, `ie-river-athlone-01`, `bafu-basel-01` +163 |
| <span style="color:#2563eb">●</span> `#2563eb` | `marine` | Marine | `cdip-pointreyes-01`, `ndbc-01`, `om-marine-01`, `cdip-santamonica-01` +20 |
| <span style="color:#84cc16">●</span> `#84cc16` | `ghg` | Greenhouse gas | `icos-htm-01`, `icos-zsf-01`, `icos-lin-01` |
| <span style="color:#c4a35a">●</span> `#c4a35a` | `grid` | Grid carbon | `rte-grid-01`, `uk-grid-01`, `eia-01` |
| <span style="color:#ff6b4a">●</span> `#ff6b4a` | `quake` | Earthquakes | `jma-quake-01`, `usgs-quake-01`, `emsc-01`, `geonet-01` +2 |
| <span style="color:#e8b86d">●</span> `#e8b86d` | `energy` | Energy | `em-01` |
| <span style="color:#f97316">●</span> `#f97316` | `fire` | Wildfire | `firms-fire-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `radiation` | Radiation | `safecast-01`, `safecast-tokyo`, `safecast-sf`, `safecast-denver` +10 |
| <span style="color:#e879f9">●</span> `#e879f9` | `jamming` | GNSS jamming | `cybernews-jam-01` |
| <span style="color:#34d399">●</span> `#34d399` | `gnss` | GNSS integrity | `gnss-euref-01`, `gnss-ga-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `traffic` | Edge traffic | `feeder-adsb-01`, `feeder-ais-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `events` | Natural events | `eonet-01` |
| <span style="color:#818cf8">●</span> `#818cf8` | `spacewx` | Space weather | `swpc-01`, `swpc-solarwind-01`, `swpc-xray-01`, `donki-01` |
| <span style="color:#fde047">●</span> `#fde047` | `lightning` | Lightning | `glm-01` |
| <span style="color:#fb7185">●</span> `#fb7185` | `alerts` | Weather alerts | `nws-alerts-01`, `naad-01` |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `argo` | Argo floats | `argo-01` |
| <span style="color:#c084fc">●</span> `#c084fc` | `geomag` | Geomagnetism | `usgs-geomag-01`, `usgs-geomag-brw`, `usgs-geomag-bsl`, `usgs-geomag-cmo` +10 |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `iot` | Edge IoT | `feeder-iot-01` |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `flood` | Flood | `vic-meuse-01`, `gfm-flood-01`, `nws-flood-01`, `ea-flood-01` +18 |
| <span style="color:#ea580c">●</span> `#ea580c` | `effis` | EFFIS fires | `effis-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `volcano` | Volcanoes | `usgs-volcano-01` |
| <span style="color:#0891b2">●</span> `#0891b2` | `ais` | Public AIS | `fintraffic-ais-01`, `kystverket-ais-01` |
| <span style="color:#e11d48">●</span> `#e11d48` | `tsunami` | Tsunami alerts | `nws-tsunami-01`, `ptwc-01` |
| <span style="color:#7c3aed">●</span> `#7c3aed` | `cyclone` | Tropical cyclones | `jma-typhoon-01`, `nhc-cyclone-01` |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `adsb` | Public ADS-B | `adsb-lol-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `smoke` | Smoke | `hms-smoke-01` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `water_quality` | Water quality | `usgs-wq-01` |
| <span style="color:#1d4ed8">●</span> `#1d4ed8` | `dart` | DART gauges | `dart-21414`, `dart-21415`, `dart-21416`, `dart-21418` +39 |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `precipitation` | Precipitation | `imerg-01` |
| <span style="color:#22c55e">●</span> `#22c55e` | `radar` | NEXRAD status | `nexrad-status-01` |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `atmosphere` | Atmosphere | `cams-ottawa`, `cams-berlin`, `cams-delhi`, `cams-tokyo` +2 |
| <span style="color:#84cc16">●</span> `#84cc16` | `radnet` | EPA RadNet | `radnet-ak-anchorage`, `radnet-ak-fairbanks`, `radnet-ak-juneau`, `radnet-birmingham` +136 |
| <span style="color:#a16207">●</span> `#a16207` | `soil` | Soil moisture | `soil-ottawa`, `soil-berlin`, `soil-delhi`, `soil-tokyo` +2 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `solar` | Solar irradiation | `solar-ottawa`, `solar-berlin`, `solar-delhi`, `solar-tokyo` +2 |
| <span style="color:#bae6fd">●</span> `#bae6fd` | `snow` | Snowpack | `snow-rainier`, `snow-tahoe`, `snow-mammoth`, `snow-rockies` +2 |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `sea_ice` | Sea ice | `nsidc-ice-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `land_temperature` | Land temperature | `lst-ottawa`, `lst-berlin`, `lst-delhi`, `lst-tokyo` +2 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `aviation` | Aviation METAR | `metar-kjfk-01`, `metar-klga-01`, `metar-kbos-01`, `metar-kord-01` +10 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `road` | Road weather | `fintraffic-road-01` |
| <span style="color:#64748b">●</span> `#64748b` | `rail` | Rail traffic | `fintraffic-rail-01` |
| <span style="color:#d97706">●</span> `#d97706` | `drought` | Drought | `usdm-01` |
| <span style="color:#0284c7">●</span> `#0284c7` | `reservoir` | Reservoirs | `usace-keys-01`, `usace-pine-01`, `usace-deni-01`, `usace-huds-01` |
| <span style="color:#facc15">●</span> `#facc15` | `uv` | UV forecast | `epa-uv-01` |
