# ATLAS 地图图例

**语言:** [EN](../LEGEND.md) · [RU](LEGEND.ru.md) · [ES](LEGEND.es.md) · [FR](LEGEND.fr.md) · [ZH](LEGEND.zh.md)

本图例由 `atlas.stations.LAYER_META` 和 `STATION_CATALOG` 生成；请勿手工编辑。使用 `python3 scripts/atlas_legend.py --write` 重新生成。

**坐标约定：**地图上一个可见点只代表一个读数坐标。固定站点使用其官方坐标；按需网格读数使用数据源返回的源/查询网格单元。密集数据源和事件数据源按读数坐标或网格中心展开为子点；父对象不会再绘制为重复点。

颜色标识图层，不表示严重程度或传感器健康状态。部分相关图层有意共用颜色；请通过图层键和筛选器区分。LIVE/SIM 状态与可用性另行显示。

当前目录定义了 46 个图层和 934 个已配置设备。事件和密集数据源可在运行时创建更多读数点。

| 颜色 | 图层键 | 表示内容 | device_id 示例 |
|---|---|---|---|
| <span style="color:#3dd6c6">●</span> `#3dd6c6` | `weather` | 天气 | `at-wx-wien-01`, `lt-wx-vilnius-01`, `lv-wx-riga-01`, `jp-wx-tokyo-01`, `cz-wx-praha-01`, `kr-wx-seoul-01` +265 |
| <span style="color:#7ec8ff">●</span> `#7ec8ff` | `air` | 空气质量 | `hk-aqhi-centralwestern-01`, `sg-psi-central-01`, `be-aq-brussels-01`, `aurn-01` +122 |
| <span style="color:#4ea8de">●</span> `#4ea8de` | `tide` | 潮汐 | `uhslc-01`, `noaa-tide-01`, `noaa-tide-sf`, `noaa-tide-honolulu` +14 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `river` | 河流 | `lt-hydro-kaunas-01`, `lv-hydro-riga-01`, `ie-river-athlone-01`, `bafu-basel-01` +163 |
| <span style="color:#2563eb">●</span> `#2563eb` | `marine` | 海洋 | `cdip-pointreyes-01`, `ndbc-01`, `om-marine-01`, `cdip-santamonica-01` +20 |
| <span style="color:#84cc16">●</span> `#84cc16` | `ghg` | 温室气体 | `icos-htm-01`, `icos-zsf-01`, `icos-lin-01` |
| <span style="color:#c4a35a">●</span> `#c4a35a` | `grid` | 电网碳强度 | `rte-grid-01`, `uk-grid-01`, `eia-01` |
| <span style="color:#ff6b4a">●</span> `#ff6b4a` | `quake` | 地震 | `jma-quake-01`, `usgs-quake-01`, `emsc-01`, `geonet-01` +2 |
| <span style="color:#e8b86d">●</span> `#e8b86d` | `energy` | 能源 | `em-01` |
| <span style="color:#f97316">●</span> `#f97316` | `fire` | 野火 | `firms-fire-01` |
| <span style="color:#a3e635">●</span> `#a3e635` | `radiation` | 辐射 | `safecast-01`, `safecast-tokyo`, `safecast-sf`, `safecast-denver` +10 |
| <span style="color:#e879f9">●</span> `#e879f9` | `jamming` | GNSS 干扰 | `cybernews-jam-01` |
| <span style="color:#34d399">●</span> `#34d399` | `gnss` | GNSS 完整性 | `gnss-euref-01`, `gnss-ga-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `traffic` | 边缘交通 | `feeder-adsb-01`, `feeder-ais-01` |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `events` | 自然灾害 | `eonet-01` |
| <span style="color:#818cf8">●</span> `#818cf8` | `spacewx` | 空间天气 | `swpc-01`, `swpc-solarwind-01`, `swpc-xray-01`, `donki-01` |
| <span style="color:#fde047">●</span> `#fde047` | `lightning` | 闪电 | `glm-01` |
| <span style="color:#fb7185">●</span> `#fb7185` | `alerts` | 天气预警 | `nws-alerts-01`, `naad-01` |
| <span style="color:#22d3ee">●</span> `#22d3ee` | `argo` | Argo 浮标 | `argo-01` |
| <span style="color:#c084fc">●</span> `#c084fc` | `geomag` | 地磁 | `usgs-geomag-01`, `usgs-geomag-brw`, `usgs-geomag-bsl`, `usgs-geomag-cmo` +10 |
| <span style="color:#2dd4bf">●</span> `#2dd4bf` | `iot` | 边缘物联网 | `feeder-iot-01` |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `flood` | 洪水 | `vic-meuse-01`, `gfm-flood-01`, `nws-flood-01`, `ea-flood-01` +18 |
| <span style="color:#ea580c">●</span> `#ea580c` | `effis` | EFFIS 火情 | `effis-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `volcano` | 火山 | `usgs-volcano-01` |
| <span style="color:#0891b2">●</span> `#0891b2` | `ais` | 公开 AIS | `fintraffic-ais-01`, `kystverket-ais-01` |
| <span style="color:#e11d48">●</span> `#e11d48` | `tsunami` | 海啸预警 | `nws-tsunami-01`, `ptwc-01` |
| <span style="color:#7c3aed">●</span> `#7c3aed` | `cyclone` | 热带气旋 | `jma-typhoon-01`, `nhc-cyclone-01` |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `adsb` | 公开 ADS-B | `adsb-lol-01` |
| <span style="color:#94a3b8">●</span> `#94a3b8` | `smoke` | 烟雾 | `hms-smoke-01` |
| <span style="color:#06b6d4">●</span> `#06b6d4` | `water_quality` | 水质 | `usgs-wq-01` |
| <span style="color:#1d4ed8">●</span> `#1d4ed8` | `dart` | DART 浮标 | `dart-21414`, `dart-21415`, `dart-21416`, `dart-21418` +39 |
| <span style="color:#0ea5e9">●</span> `#0ea5e9` | `precipitation` | 降水 | `imerg-01` |
| <span style="color:#22c55e">●</span> `#22c55e` | `radar` | NEXRAD 状态 | `nexrad-status-01` |
| <span style="color:#a78bfa">●</span> `#a78bfa` | `atmosphere` | 大气 | `cams-ottawa`, `cams-berlin`, `cams-delhi`, `cams-tokyo` +2 |
| <span style="color:#84cc16">●</span> `#84cc16` | `radnet` | EPA RadNet | `radnet-ak-anchorage`, `radnet-ak-fairbanks`, `radnet-ak-juneau`, `radnet-birmingham` +136 |
| <span style="color:#a16207">●</span> `#a16207` | `soil` | 土壤湿度 | `soil-ottawa`, `soil-berlin`, `soil-delhi`, `soil-tokyo` +2 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `solar` | 太阳辐照度 | `solar-ottawa`, `solar-berlin`, `solar-delhi`, `solar-tokyo` +2 |
| <span style="color:#bae6fd">●</span> `#bae6fd` | `snow` | 积雪 | `snow-rainier`, `snow-tahoe`, `snow-mammoth`, `snow-rockies` +2 |
| <span style="color:#67e8f9">●</span> `#67e8f9` | `sea_ice` | 海冰 | `nsidc-ice-01` |
| <span style="color:#ef4444">●</span> `#ef4444` | `land_temperature` | 地表温度 | `lst-ottawa`, `lst-berlin`, `lst-delhi`, `lst-tokyo` +2 |
| <span style="color:#38bdf8">●</span> `#38bdf8` | `aviation` | 航空 METAR | `metar-kjfk-01`, `metar-klga-01`, `metar-kbos-01`, `metar-kord-01` +10 |
| <span style="color:#f59e0b">●</span> `#f59e0b` | `road` | 道路气象 | `fintraffic-road-01` |
| <span style="color:#64748b">●</span> `#64748b` | `rail` | 铁路交通 | `fintraffic-rail-01` |
| <span style="color:#d97706">●</span> `#d97706` | `drought` | 干旱 | `usdm-01` |
| <span style="color:#0284c7">●</span> `#0284c7` | `reservoir` | Reservoirs | `usace-keys-01`, `usace-pine-01`, `usace-deni-01`, `usace-huds-01` |
| <span style="color:#facc15">●</span> `#facc15` | `uv` | UV forecast | `epa-uv-01` |
