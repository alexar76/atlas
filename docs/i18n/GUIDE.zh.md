# ATLAS — 运维与开发指南

**语言：** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS 是生态中的**传感器地图**：天气、空气质量、潮汐、河流、海洋、英国电网碳强度、地震、**野火**、**辐射**、**GNSS 干扰**、芬兰公共 AIS、NWS 海啸警报，以及可选的自有边缘 ADS-B/AIS——数据来自 [GAIA](https://iot.modelmarket.dev) 中继。**新的开放数据设备在 GAIA 上；地图图层、针脚与 watchbox 是 ATLAS 表面**（GAIA 侧无单独产品 UI）。在 [Alien Monitor](https://monitor.modelmarket.dev/) 中为 **ATLAS** 节点，并内置 **ATLAS Analyst**（默认 DeepSeek）。术语见 [`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)。

**Add sensor:** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md) (EN · RU · ES · FR · ZH)。GAIA 设备目录：[LIVE-RELAYS](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md)。**运营方用例**（地图 + ATLAS Analyst）：[`OPERATOR-USE-CASES.zh.md`](OPERATOR-USE-CASES.zh.md)。

## 表面

| URL | 作用 |
|-----|------|
| `/` | 完整 MapLibre 地图 + 图层 + 视野内列表 + AI |
| `/embed` | Monitor iframe 用紧凑地图 |
| `/health` | 存活检查 |
| `/api/v1/*` | Snapshot、viewport、站点详情、SSE、**watchboxes** |
| `/api/ai/*` | 提供方 + 基于 live 数据的对话 |

## 负载模型

- 后台：仅廉价 **fleet**（针脚）。
- `POST /api/v1/viewport`：先刷新**可见 bbox**；邻居与其余目录后台写入 TTL 缓存（约 45 秒），single-flight。
- 点击 → `GET /api/v1/stations/{id}` — 可读详情。
- **ATLAS Analyst：** 注入**整支**已缓存机队的 LIVE SNAPSHOT + 生态简报。
- **LIVE** / **SIM** 徽章不翻译。

**Analyst 自动学习：** ATLAS SURFACES 与 `snapshot.capabilities` 由 `STATION_CATALOG` / `LAYER_META` / watchboxes 生成——目录中新增设备即进入提示词，无需手改角色文案。

买家**通常**不能向 GAIA invoke 传入经纬度；例外是同一 SKU 上的 `om-aq-*` 与 `sc-*`（Sensor.Community）。地震 / 火灾 / 干扰事件的坐标来自读数。

## 图层

GAIA 出售**读数**（`gaia.*.read@v1`）。ATLAS 是**地图**（图层/针脚）与 **watchboxes**。

全部 **53 个图层**的当前列表、精确颜色、含义和设备示例见
[ATLAS 地图图例](LEGEND.zh.md)。该图例与地图使用同一运行时目录生成。
目录当前包含 **970 个已配置设备**；事件和密集数据源可在运行时创建更多读数点。

| 图层 | 典型 device_id | 说明 |
|------|----------------|------|
| 天气 | `om-wx-01`, `nws-01`, mesh | + 模拟 |
| 空气 | `om-aq-01`, `osm-01`, `sta-01`, `sc-01`, `sc-{slug}`, mesh | SC：买家 lat/lon；众包 ≠ 参考站 |
| 潮汐 | `noaa-tide-01` | |
| 河流 | `usgs-river-01`, `eccc-hydro-01`, `smhi-hydro-01` | USGS / ECCC / SMHI |
| 海洋 | `ndbc-01`, `om-marine-01` | |
| 电网 | `uk-grid-01` | 区域 |
| 地震 | `usgs-quake-01` | event lat/lon |
| 能源 | `em-01` | 模拟器 |
| 野火 | `firms-fire-01` | NASA FIRMS — 须注明 NASA |
| 辐射 | `safecast-01` + 锚点 | Safecast **CC0** · Hub 为 30 天；Melbourne/Adelaide 为档案（2014 澳网格，`captured_at`） |
| 干扰 | `cybernews-jam-01` | CyberNews GNSS **CC BY 4.0** |
| 交通 | `feeder-adsb-01`, `feeder-ais-01` | 自有边缘（`GAIA_FEEDER_*`） |
| 公共 AIS | `fintraffic-ais-01`, `kystverket-ais-01` | Fintraffic CC BY 4.0（芬兰）· Kystverket NLOD（挪威）— 不是「欧洲 AIS」一团 |
| 公开 ADS-B | `adsb-lol-01` | ADSB.lol ODbL 1.0 — 不是自有边缘，不是 OpenSky/ADSBx |
| 海啸 | `nws-tsunami-01`, `ptwc-01` | NWS CAP + PTWC Atom（不是验潮仪；空 ≠ 全部安全） |
| 热带气旋 | `nhc-cyclone-01` | NHC/CPHC AL+EP+CP — 不是 JTWC |
| 水质 | `usgs-wq-01` | 新鲜（48 小时）分页 latest-continuous 观测联接 USGS monitoring-locations；仅保留所需参数站点，一站一点；逐参数 Approved/Provisional + qualifiers；持久历史及按轮询计算的 uptime |
| 地下水 | `usgs-groundwater-01` | 覆盖缅因州、纽约州和肯塔基州的三个 USGS 试点井。深度以当地地表为基准，单位为米，向下为正。ATLAS 显示测量时间和 USGS 审核状态。超过 24 小时的观测会被隐藏。 |
| Hub’Eau 地下水 | `hubeau-groundwater-01` | 法国八口试点井提供从测量基准点到水面的深度和以 NGF 表示的水面高程。卡片会显示观测时间和每项数值的基准。 |
| NOAA NWPS 河流水位预报 | `nwps-pttp1`, `nwps-rmdv2`, `nwps-vckm6`, `nwps-dlrt2` | 卡片显示未来 72 小时内可用预报点的最高水位、发布时间和峰值时间。水位以该水文站的本地基准为准。 |
| 英国环境署验潮站 | `ea-tide-e70039`, `ea-tide-e72639`, `ea-tide-e70539`, `ea-tide-e70739`, `ea-tide-e73839` | 英国沿海站点以米为单位提供相对于 Ordnance Datum Newlyn 基准的平均海平面高度（mAOD）。 |
| Fintraffic 道路事件 | `fintraffic-road-announcements-01`, `fintraffic-roadworks-01` | 芬兰道路通告和施工记录显示受影响路段及源数据中的有效时段。 |
| NOAA G-AIRMET | `awc-gairmet-01` | 美国航空预报的多边形和线条标注危险类型、发布时间和有效时间。 |
| NDW 道路通告和临时封闭 | `ndw-road-srti-01`, `ndw-road-closures-01` | `road_events` 图层显示荷兰道路安全通告、临时封闭及受影响路段的几何形状。签名快照在发布五分钟后过期。每项交通措施另有自己的有效时段。 [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) |
| FMI 波罗的海测波浮标 | `fmi-marine-103976`, `fmi-marine-108126`, `fmi-marine-108499`, `fmi-marine-134220`, `fmi-marine-134221`, `fmi-marine-134246` | `marine` 图层中的六个浮标提供有效波高。卡片也会显示同一时刻测得的谱峰周期、来波方向和水温。时间戳表示波浪采样的开始时间。观测数据两小时后过期。 [FMI · CC BY 4.0](https://en.ilmatieteenlaitos.fi/download-observations-questions) |
| USDA NRCS SNOTEL 积雪观测 | `snotel-335`, `snotel-415` | `snow` 图层显示科罗拉多州 Berthoud Summit 和 Copper Mountain 两站的每小时积雪深度及雪水当量，单位为厘米。GAIA 只配对同一小时内通过自动质量检查且距今不超过六小时的测量值。 [USDA NRCS · 美国公有领域](https://catalog.data.gov/dataset/snowpack-telemetry-network-snotel) |
| SMHI 海洋观测 | `smhi-ocean-flinten16-8m`, `smhi-ocean-flinten16-2m`, `smhi-ocean-flinten7-8m`, `smhi-ocean-kalmar2-0m` | `ocean_obs` · 瑞典三个站点提供四组指定深度的观测序列。卡片按站点和深度显示盐度（PSU）、溶解氧（mL/L）或流速和流向。同一卡片中的测量值取自同一观测时刻，最长保留三小时。 [SMHI · CC BY 4.0](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) |
| ECCC 野火烟雾预报 | `eccc-smoke-seattle`, `eccc-smoke-toronto`, `eccc-smoke-calgary` | `smoke_forecast` · 覆盖西雅图、多伦多和卡尔加里附近的三个模型网格。卡片显示下一 UTC 整点模拟烟羽内的近地面总 PM₂.₅ 浓度（µg/m³）、模型起报时间及预报有效时间。模型起报时间距今最长 18 小时。 [ECCC · MSC End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) |
| NOAA SWPC D-RAP | `swpc-drap-01` | `hf_absorption` · 全球模型网格显示受电离层 D 区 1 dB 吸收影响的最高频率。全球概览显示 900 个 6° × 12° 网格内的最大值，单位为 MHz。放大后可以查看全部 8,100 个 2° × 4° 原始网格的采样值。网格数据在 15 分钟后失效。 [NOAA SWPC](https://www.swpc.noaa.gov/products/d-region-absorption-predictions-d-rap) |
| BfS 环境伽马剂量率 | `bfs-odl-01` | `radiation` · 德国监测站显示经过验证的每小时环境伽马剂量当量率（nSv/h）。卡片注明观测小时的结束时间。数据在两小时后失效。 [BfS · DL-DE-BY 2.0](https://www.imis.bfs.de/geoportal/resources/sitepolicy.html) |
| GeoNet 沿岸水位 | `geonet-coastal-auct`, `geonet-coastal-wlgt`, `geonet-coastal-taut`, `geonet-coastal-gist`, `geonet-coastal-jbtt` | `tide` · 新西兰五个站点显示以当地压力传感器为基准的水柱高度，单位为米。数据在五分钟后失效。 [GeoNet · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) |
| ČHMÚ 河流观测 | `chmi-river-042000`, `chmi-river-101800`, `chmi-river-200100` | `river` · 捷克三个水文站显示初步观测水位和流量。如果同一时刻测量了水温，卡片也会显示水温。数据在两小时后失效。 [ČHMÚ · CC BY 4.0](https://www.chmi.cz/-/kde-najdu-otev%C5%99en%C3%A1-data-%C4%8Dhm%C3%BA-) |
| Entur 列车位置 | `entur-rail-vyg-01` | `rail` · 地图显示挪威 Vy 列车近期观测位置，并在有数据时显示线路。位置在供应方设定的有效期结束时失效，最长保留五分钟。 [Entur · NLOD](https://developer.entur.no/terms-of-service) |
| UK Power Networks 实时停电 | `ukpn-live-faults-01` | `power_outages` · 显示运营商服务区内的当前故障。卡片显示大致受影响范围、受影响客户数以及运营商发布的预计恢复时间。快照在 30 分钟后失效。 [UK Power Networks · CC BY 4.0](https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults) |
| NOAA PORTS 桥下净空 | `noaa-airgap-8726371`, `noaa-airgap-8545556`, `noaa-airgap-8575432` | `bridge_clearance` · 美国三座桥梁的传感器提供水面到桥梁固定参考点的初步垂直距离，单位为米。卡片显示样本标准差和来源标志。观测在 18 分钟后失效。通航决策请查阅 NOAA PORTS 和官方航海图。 [NOAA NOS CO-OPS](https://opendap.co-ops.nos.noaa.gov/erddap/info/IOOS_Air_Gap/index.html) |
| NOAA AOML 海洋漂流浮标 | `aoml-drifters-01` | `ocean_drifters` · 全球数据展示各浮标最近观测位置和海表温度。浮标报告海平面气压时也会显示。观测在六小时后失效。 [NOAA AOML / OSMC · CC0 1.0](https://osmc.noaa.gov/erddap/info/OSMC_flattened/index.json) |
| Bike Share Toronto 共享单车 | `toronto-bikeshare-01` | `bikeshare` · 站点卡片显示可用单车数量、已报告的电动单车数量、空桩数量及租借和归还状态。报告在五分钟后失效。 [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| 多伦多道路限制 | `toronto-road-restrictions-01` | `road_events` · 市政公告在限制有效期间显示受影响的点位或路段，包含按计划重复实施的限制。来源快照在 15 分钟后失效。每条公告都有自己的生效时段。 [City of Toronto · OGL](https://open.toronto.ca/open-data-licence/) |
| ARSO 河流观测 | `arso-river-1060`, `arso-river-3660`, `arso-river-5078`, `arso-river-8080` | `river` · 斯洛文尼亚四个水文站报告初步水位和流量。水位以测站当地零点为基准，单位为米，流量单位为 m³/s。卡片也会显示同一时刻测得的水温。观测在两小时后失效。 [ARSO](https://kazalci.arso.gov.si/en/content/legal-note) |
| Kartverket 沿岸水位 | `kartverket-tide-bgo`, `kartverket-tide-osl`, `kartverket-tide-svg`, `kartverket-tide-tos`, `kartverket-tide-trd` | `tide` · 挪威五个验潮站显示相对于国家高程基准 NN2000 的沿岸观测水位，单位为米。观测在两小时后失效。 [Kartverket · CC BY 4.0](https://vannstand.kartverket.no/tideapi_en.html) |
| 可能受淹点位 | `usgs-rtfi-01` | 附近 USGS 水文站的水位超过道路、桥梁、建筑物或其他地点的实测阈值，提示该地点可能受淹。结果为初步判断。空结果仅表示覆盖范围内没有满足条件的点位。 |
| DART | `noaa-dart-01`, `dart-*` | 固化官方 NDBC 目录中的全部 43 个活动站 |
| EPA RadNet | `radnet-*` | 全部 140 个 EPA 官方监测点坐标，不是三个演示城市 |
| NEXRAD 状态 | `nexrad-status-01` | 每个 WSR-88D 站点位于自身坐标；是状态，不是反射率 |
| 坐标网格/模型 | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | 买方 `lat`/`lon`；ATLAS 使用返回的源/查询网格坐标 |

多伦多道路限制与共享单车数据使用以下署名。“Contains information licensed under the Open Government Licence – Toronto.” [许可证](https://open.toronto.ca/open-data-licence/)

### 充电站、灾害与现场观测

| 来源 | GAIA | ATLAS | 数据与限制 | 来源与条款 |
| --- | --- | --- | --- | --- |
| NDW DOT-NL 公共充电站 | `gaia.ev.charging.read@v1` · `ndw-ev-charging-01` | `ev_charging` | 荷兰公共充电站按接口类型显示空闲数量、总数量和功率。默认查询乌得勒支。区域查询最多覆盖 4 平方度。Hub 每页最多返回 500 个站点，续页须使用快照标识。快照在四分钟后失效。 | [NDW · CC0 1.0](https://docs.ndw.nu/algemeen/data-gebruiksvoorwaarden/) · [GeoJSON API](https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/) |
| BC Wildfire 火灾位置和边界 | `gaia.fire.perimeters.read@v1` · `bc-wildfire-01` | `wildfire_perimeters` | 不列颠哥伦比亚省的活动火灾显示当前状态，并在有数据时显示最新发布的边界。数据集更新时间和各边界的日期分别显示。快照在一小时后失效。 | [BC Wildfire Service · OGL–BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) · [火灾边界](https://open.canada.ca/data/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1) |
| MeteoSwiss A7 花粉实测 | `gaia.pollen.read@v1` · `ch-pollen-*` | `pollen` | 15 个已登记的自动站按小时报告七类花粉的浓度，单位为粒每立方米。实测零值会保留。观测在两小时后失效。 | [Source: MeteoSwiss · CC BY 4.0](https://opendatadocs.meteoswiss.ch/general/terms-of-use) · [A7](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations) |
| 爱尔兰气象浮标网 | `gaia.marine.read@v1` · `ie-buoy-m2`, `ie-buoy-m3`, `ie-buoy-m5`, `ie-buoy-m6` | `marine` | 四个试点浮标报告波高、周期和方向，并在有数据时显示海水温度和风况。观测在两小时后失效。质量标志 0 表示质量未知，1 表示质量良好。 | [Marine Institute and Met Éireann · CC BY 4.0](https://erddap.marine.ie/erddap/info/IWBNetwork/index.html) |
| 澳大利亚 AODN/IMOS 测波浮标 | `gaia.marine.read@v1` · `au-wave-apollo-bay`, `au-wave-wilsons-prom`, `au-wave-wooli` | `marine` | 三个试点浮标在有数据时报告有效波高、峰值周期和来波方向。GAIA 采用来源质量标志 1 的数据。观测在两小时后失效。 | [AODN / IMOS · CC BY 4.0](https://registry.opendata.aws/aodn_wave_buoy_realtime_nonqc/) |
| GeoNet 新西兰火山和相机 | `gaia.volcano.read@v1` · `geonet-volcano-01` | `volcano` | 12 座监测火山显示当前警戒级别和航空颜色代码。状态在取得后 30 分钟失效。可用的相机缩略图显示各自的拍摄时间，并在 30 分钟后失效。 | [GeoNet / Earth Sciences New Zealand and sponsors · CC BY 3.0 NZ](https://www.geonet.org.nz/policy) · [相机](https://doi.org/10.21420/vq6s-w222) |
| NOAA SPC 当地强风暴报告 | `gaia.storm.reports.read@v1` · `noaa-spc-storm-reports-01` | `storm_reports` | 地图显示过去 24 小时内美国龙卷风、冰雹和强风的初步报告。每个点标注来源报告的事件时间。 | [NOAA/NWS SPC · U.S. public domain](https://www.weather.gov/disclaimer) · [CSV](https://www.spc.noaa.gov/climo/reports/today.csv) |
| 华盛顿 VAAC 火山灰通告 | `gaia.volcanic.ash.read@v1` · `noaa-vaac-ash-01` | `volcanic_ash` | 已发布的火山灰多边形显示高度范围、签发时间以及观测时间或预报有效时间。通告在下一次预定签发时间或签发七小时后失效，以较早者为准。 | [NOAA Washington VAAC](https://ospo.noaa.gov/products/atmosphere/vaac/messages.html) · [NOAA 使用条款](https://www.noaa.gov/office-education/outreach-communication/faq) |
| Digital Earth Australia 热点 | `gaia.fire.hotspots.read@v1` · `dea-hotspots-01` | `fire_hotspots` | 在查询范围内显示最近三小时的澳大利亚卫星热异常，包括 Himawari-9 的探测结果。地图最多加载 800 个探测点，并标明覆盖是否完整。 | [Geoscience Australia · CC BY 4.0](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/) · [DEA Hotspots 数据集](https://pid.geoscience.gov.au/dataset/ga/111881) |

不列颠哥伦比亚省数据附有署名“Contains information licensed under the Open Government Licence – British Columbia.”。澳大利亚浮标数据附有署名“Data was sourced from Australia’s Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)”。

完整地图的 **NOAA 雷达影像** 开关显示 NOAA/NWS MRMS 基础反射率栅格，覆盖美国大陆、阿拉斯加、夏威夷、加勒比地区和关岛。ATLAS 显示截至数据源最新发布时间的 10 分钟 UTC 窗口。若该时间已过去超过 20 分钟，地图会隐藏拼图。栅格沿用数据源的反射率配色。站点运行状态见独立的 **NEXRAD 状态** 图层。 [NOAA 影像服务](https://mapservices.weather.noaa.gov/eventdriven/rest/services/radar/radar_base_reflectivity_time/ImageServer) · [NWS 数据政策](https://www.weather.gov/disclaimer)

## Watchboxes (`atlas.watchbox.subscribe@v1` + `atlas.watchbox.check@v1`)

**Watchbox** 是已保存的「监视框」：bbox（west/south/east/north）+ 地图图层过滤。
含义：「当这些图层在这个矩形内出现 LIVE 时告诉我」——不是 GAIA 设备读数。

- **Subscribe**（REST / `atlas.watchbox.subscribe@v1`）— 创建/列出/删除框
  （plumbing；不是 Hub 计费 SKU）。
- **Check**（`atlas.watchbox.check@v1`）— 用当前机队快照评估框：匹配项 + content
  receipt。这是 Hub 计费产品（也可用临时 bbox + 图层，无需已保存 id）。

仅可自由商用图层（`ALLOWED_WATCHBOX_LAYERS`）。Peer：`/.well-known/ai-market.json`。

- `GET`/`POST /api/v1/watchboxes`
- `GET`/`DELETE /api/v1/watchboxes/{id}`
- `POST /api/v1/watchboxes/{id}/check`

curl 示例见 [EN](../GUIDE.md#watchboxes-atlaswatchboxsubscribev1--atlaswatchboxcheckv1)。

## 组合产品（ATLAS > 部件）

| SKU | 作用 | Convenience | Hub invoke |
|-----|------|-------------|------------|
| `atlas.situation.brief@v1` | bbox 跨层打分简报——默认含地图图层（flood、EFFIS、lightning、volcano、公共 AIS、海啸…）；空则拒绝 | `POST /api/v1/products/situation-brief` | `POST /ai-market/v2/invoke` |
| `atlas.fire.weather@v1` | bbox 内 FIRMS **和/或** Copernicus EFFIS + 最近 LIVE 天气（两个列表；非预报） | `POST /api/v1/products/fire-weather` | same |
| `atlas.smoke.operations@v1` | 场地 `lat`/`lon` → 对完整签名的 NOAA HMS 烟雾几何做**点面判断**（含外环**与**内环，跨 180° 经线安全）+ 同坐标 PM2.5/AQI；HMS 清单不完整或缺少空气数据时拒答。定性分析，不是实测 PM2.5，也不是疏散命令 | `POST /api/v1/products/smoke-operations` | same |
| `atlas.nearest.read@v1` | 距买家 `lat`/`lon` 最近的 LIVE 针脚（图层、`max_km`、回执） | `POST /api/v1/products/nearest` | same |
| `atlas.watchbox.check@v1` | 评估已保存或临时 watchbox → 匹配 + 回执 | watchbox `…/check` | same |
| `atlas.mesh.sample@v1` | 对已许可的实地网格（`ee-wx`、`pegel`…）做 Halton LIVE 针脚抽样。Sibling `lattice.sequence@v1`。不是 ECVRF（Sortes 是兄弟 hop），不是 Open-Meteo | `POST /api/v1/products/mesh-sample` | same |
| `atlas.field.consensus@v1` | LIVE 实地读数的 Murmuration 等价共识（至少 3 站）。不是预报，不是把 Open-Meteo 当测站 | `POST /api/v1/products/field-consensus` | same |
| `atlas.field.posterior@v1` | 对**当前** LIVE 快照的空间 RBF GP。只插值此刻，不是预报。Sibling `gauss.field@v1` | `POST /api/v1/products/field-posterior` | same |
| `atlas.field.shape@v1` | LIVE 针脚的 H0 持续性（连通分量 vs 半径）。不是 Betti-1，不是 AQI。Sibling `betti.homology@v1` | `POST /api/v1/products/field-shape` | same |

无 LIVE 则失败关闭。FIRMS 须注明 NASA。**Nearest** 用 ATLAS 地图索引（GAIA 读数仍用
`device_id`）。Hub UI 文案：`aimarket-hub/cap-descriptions-i18n.json`
（EN · RU · ES · FR · ZH）。联邦 crawl 后出现在目录。

## API（简）

- `GET /api/v1/snapshot` — 针脚 + 缓存
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics；数据源已滚动的图钉返回「cleared from the live window」卡片，而不是 404
- `POST /api/v1/refresh` — 需要运维令牌（`X-Atlas-Token`）：一次调用会重读整个目录
- `POST /api/ai/ask` — 分析与**态势报告**（`report: true`）

生产 LLM： **`DEEPSEEK_API_KEY`**，模型 `deepseek-v4-pro`。

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL`（默认 `https://atlas.modelmarket.dev`）。面板：传感器 + `/embed` iframe +「Open full map」。

## 部署

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

仅 loopback `127.0.0.1:9330` — TLS 经 nginx。

## 测试

```bash
cd atlas && pip install -e ".[dev]"
pytest -q
```

无需在线 GAIA（mock）。完整 env/API：[EN](../GUIDE.md)。

## 诚实性

ATLAS 是 GAIA 中继之上的地图、**ATLAS Analyst** 与 watchboxes。Open-Meteo：CC BY 4.0；NWS/USGS/NOAA：美国公有领域；FIRMS：注明 NASA；Safecast：CC0；CyberNews：CC BY 4.0。
