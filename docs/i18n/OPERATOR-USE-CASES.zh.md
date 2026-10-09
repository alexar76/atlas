# ATLAS — 运营方用例

**语言：** [EN](../OPERATOR-USE-CASES.md) · [RU](OPERATOR-USE-CASES.ru.md) · [ES](OPERATOR-USE-CASES.es.md) · [FR](OPERATOR-USE-CASES.fr.md) · [ZH](OPERATOR-USE-CASES.zh.md)

ATLAS 是运营方的**传感器地图**，并带 **ATLAS Analyst**。GAIA 对 LIVE **中继**的**读数**做证明（attestation）；Hub 出售 `capability_id`。本页说明运营方（或锚定 Analyst 的**智能体**）如何就物理世界提问，而不用模型顶替 **source**。

术语：[`localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)。地图/API：[`GUIDE.zh.md`](GUIDE.zh.md)。中继与许可：[`gaia/docs/LIVE-RELAYS.md`](https://github.com/alexar76/gaia/blob/main/docs/LIVE-RELAYS.md)。添加**针脚**：[`docs/add-gaia-atlas-sensor.md`](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md)。

审计日期：**2026-08-14**。状态：

| 状态 | 含义 |
|------|------|
| **Live now** | 已在地图上。可就这些**图层**询问 Analyst。 |
| **Proposed — sell** | 许可 + HTTPS + 地理范围已钉死；尚未写代码。Recipe B 之后可作为 Hub SKU 出售。 |
| **Hold** | 在下列缺口关闭前，不要出售，也不要显示为 LIVE。 |

---

## 如何提问

1. 只打开能回答该问题的**图层**（野火不是**热带气旋**）。
2. 把 **viewport** 飞到许可覆盖的地理范围（芬兰 **AIS** 不是北海）。
3. 点击**针脚**。查看 `source`、`LIVE`/`SIM`，以及 `captured_at` / CAP 时间（如有）。
4. 向 **ATLAS Analyst** 提问并点名**图层**。提示词锚定在机队快照上——必须引用针脚，不得编造预报。
5. 若需持续检查，对该图层 + bbox 设 **watchbox**（`atlas.watchbox.subscribe@v1`）。

对带运营方**锚点**的设备，GAIA **invoke** 通常只要 `device_id`。同一 SKU 接受买方 `latitude`/`longitude` 的例外：Open-Meteo AQ（`om-aq-*`）与 Sensor.Community（`sc-01` / `sc-{slug}`）。事件源（FIRMS、地震、CAP）把坐标放在**读数**里。

---

## 出售与嵌入规则

与 LIVE-RELAYS 同一套商业过滤器。任一关不过即为 **Hold**。

| 关口 | 通过 |
|------|------|
| 许可 | 仓库已采用的 CC0 / CC BY / OGL / NLOD / 美国公有领域 / Copernicus CC BY。不要 NC、不要「仅供参考」、不要仅 helpdesk 条款。 |
| 嵌入 | HTTPS 主机在 GAIA **allowlist** 上；无客户端 URL；fail-closed → 503，Hub 不得扣款。 |
| 意义 | 回答现有目录没有的问题，**或**补上现有 SKU 没有的地理范围。不要把全球 USGS 换个名字再卖一遍。 |
| 诚实 | **警报产品** ≠ **in-situ** 传感器。公共 **AIS** ≠ 自有边缘 AIS。**VIIRS 热点** ≠ 火场周界 ≠ 「灾害」。 |

**ATLAS Analyst** 可以 flyTo 并打开站点卡片。不得：下令疏散、把 GDACS 当成 FIRMS 分类器、把空的海啸 CAP 当成「安全」、把 Open-Meteo 当成 in-situ。

---

## Live now — 今天就可以问

| 运营方 / 智能体问题 | 图层 | LIVE **读数**是什么 | 不得声称 |
|---------------------|------|---------------------|----------|
| 此刻热探测在哪？ | Wildfire `firms-fire-01` | NASA FIRMS **VIIRS 热点**簇。须注明 NASA FIRMS。 | 火场周界、过火面积或「这是灾害」。 |
| 欧洲哪些火在 EFFIS 当前列表里？ | EFFIS `effis-01` | Copernicus EMS / JRC 当前火情，**CC BY 4.0**。 | 全球 VIIRS 替代品；不是 FIRMS。 |
| 有没有 NASA 开放自然灾害事件（火山、风暴、冰，…）？ | Natural events `eonet-01` | EONET 目录事件。须注明 NASA EONET。 | NHC 路径；不是**热带气旋**公报。 |
| 美国是否有洪水 / 山洪 CAP？ | Flood `nws-flood-01` | NWS **CAP**，**洪水预警**（美国公有领域）。 | 英格兰 / 全球洪水模型。不抓取 GloFAS。 |
| 这条河**锚点**的水位/流量是多少？ | Rivers | USGS / ECCC / SMHI 的 **in-situ** **读数**。 | **洪水预警**。Gage height 不是**水质**。 |
| 这个美国 bbox 内的连续水化学状况如何？ | Water quality `usgs-wq-01` | bbox 内全部当前 USGS 站点；pH、温度、溶解氧和电导率；保留临时/质量元数据。 | 河流水位、离散实验室样本或美国境外覆盖。 |
| EPA 全国辐射基线如何，哪里发生偏离？ | EPA RadNet `radnet-*` | 全部 140 个官方监测坐标及已批准的小时 gamma 读数。 | 剂量预测或紧急状态声明。 |
| 哪个活动 DART 水位计最接近该海洋事件？ | DART `noaa-dart-01`, `dart-*` | 固化 NDBC 目录中的全部 43 个活动站，各自位于官方坐标。 | 海啸警报或疏散命令。 |
| **这个北美场地**现在是否位于烟雾多边形内？ | `atlas.smoke.operations@v1` | 对完整签名的 **北美** HMS 清单做精确点面判断（处理内环与 180° 经线）+ 同坐标 PM2.5/AQI。清单不完整或超出 HMS 地理范围则拒答。 | 疏散命令、健康结论、监管站实测值，或全球烟雾覆盖。 |
| 是否有美国海啸**警报产品**？ | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory。经常**空 → offline**。 | 验潮仪。空不等于「地球上没有海啸」。 |
| 这个潮汐**锚点**水位是多少？ | Tide | NOAA CO-OPS / UHSLC **in-situ**。 | 海啸**警报产品**。 |
| **芬兰水域**有哪些船？ | Public AIS `fintraffic-ais-01` | Fintraffic Digitraffic 快照，**CC BY 4.0**。 | 全球 AIS、GFW、AISStream 或自有 `gaia.ais.read@v1`。 |
| **我们的**接收机看到哪些飞机？ | Edge traffic `feeder-adsb-01` | 自有 dump1090 ingest。未推送则为 offline。 | ADSBx / OpenSky / 公共聚合器。 |
| 该地图点（或任意 lat/lon）附近的众包 PM 是多少？ | Air `sc-01` / `sc-{slug}` | Sensor.Community 区域查询，**ODbL**——须注明。买家可在 `gaia.air.read@v1` 上传 `latitude`/`longitude`。Mesh 钉为城市锚点。空区 → offline。 | 参考空气站；地球上每个 SDS011；Open-Meteo 模式 AQ。 |
| USGS 是否报告了地震（通常 M≥2.5）？ | Earthquakes `usgs-quake-01` | USGS GeoJSON 事件 lat/lon。 | 欧地中海密度，或澳大利亚本地目录。 |
| 新西兰本地地震？ | Earthquakes `geonet-01` | GeoNet，**CC BY 3.0 NZ**。 | 全球目录。 |
| 莱茵河水位/流量如何（点击测站）？ | Rivers `pegel-*-01` mesh | WSV **PEGELONLINE** in-situ（DL-DE-Zero）。每个联邦测站一个可点击**针脚**。 | **洪水预警**；荷兰/法国测站。 |
| 该机场的 **METAR** 是什么（点击机场）？ | Aviation `metar-*-01` mesh | AviationWeather.gov METAR（美国公有领域）。每个 ICAO 一个**针脚**。 | NWS 陆地 ASOS；**TAF** 预报。 |
| 芬兰公路**道路气象**如何（点击站点）？ | Road `fintraffic-road-01` → `road-st-*` | Digitraffic road weather，**CC BY 4.0**。簇父节点在 viewport 展开**针脚**。 | AIS、欧盟交通或 NWS。 |
| 芬兰火车现在在哪（点击列车）？ | Rail `fintraffic-rail-01` → `rail-tr-*` | Digitraffic train locations，**CC BY 4.0**。 | 欧盟铁路或道路 TMS。 |
| 本周美国哪里**干旱**最重（点击州）？ | Drought `usdm-01` → `drought-st-*` | **USDM** 每周州统计 — 注明 NDMC / USDA / NOAA / NASA。 | 土壤湿度或 NWS 警报。 |
| 本周哪些美国州处于干旱？ | Drought `usdm-01` | U.S. Drought Monitor — 注明 NDMC / USDA / NOAA / NASA。 | 土壤湿度针脚；洪水 CAP。 |
| GeoShake 是否报告了社区事件？ | Earthquakes `geoshake-01` | GeoShake 目录 **CC BY 4.0**（空 → offline）。 | 替代 USGS/EMSC。 |
| 是否有加拿大公开 CAP 警报？ | Alerts `naad-01` | **NAAD** Atom **CAP-CP** — 注明签发方（如 Environment Canada）。空 ≠「一切正常」。 | NWS CAP。 |
| 太阳风 / GOES X 射线 / DONKI 现在如何？ | Space weather `swpc-*` / `donki-01` | NOAA **SWPC** 公有领域 + NASA **DONKI** 开放数据。 | 疏散令；仅用 Kp 且不点名来源。 |
| 这条**英格兰**河测站的流量/水位如何（点击针脚）？ | Rivers `ea-*-01` mesh | EA Hydrology **in-situ**（OGL v3）。优先同时有 Q 与水位的针脚。 | EA **洪水预警**（`ea-flood-01`）；SEPA/NRW；PEGELONLINE。 |
| **荷兰莱茵/Waal/IJssel** 的流量/水位如何（点击 Lobith 或 Tiel）？ | Rivers `rws-*-01` mesh | Rijkswaterstaat WaterWebservices **in-situ**（**CC0**）。Lobith/Tiel 有 Q+水位；部分针脚仅水位。 | 德国 PEGELONLINE；英格兰 EA；洪水 CAP。 |
| 这座 USACE 水库的库水位与库容如何（点击湖泊）？ | Reservoir `usace-*-01` mesh | USACE CWMS Elev + Stor（美国公有领域）。每针两个可售字段。 | **洪水预警产品**；仅 USGS 水位。 |
| **爱尔兰**实时天气如何（点击站点）？ | Weather `met-ie-01` → `wx-ie-*` | Met Éireann 观测（**CC BY 4.0** — 完整署名）。气温/湿度/风/雨/气压。 | 把 Open-Meteo 当作 in-situ；英国/荷兰陆地站。 |
| 这条**法国**河测站的流量/水位如何（点击针脚）？ | Rivers `hubeau-*-01` mesh | Hub'Eau hydrométrie **in-situ**（**Etalab OL 2.0**）。有则同时给出 Q 与水位。 | **Vigicrues**；德国 PEGELONLINE；eHYD 奥地利。 |
| 这条**奥地利**河测站的流量/水位如何（点击针脚）？ | Rivers `ehyd-*-01` mesh | eHYD / BMLUK `pegel_aktuell` **in-situ**（**CC BY 4.0** — «Datenquelle: ehyd.gv.at»）。 | 德国 PEGELONLINE；Hub'Eau 法国；洪水 CAP。 |
| **瑞典**现场天气如何？ | Weather `smhi-wx-*-01` | SMHI MetObs（**CC BY 4.0**）。气温/湿度/气压/风。 | `smhi-hydro-01`；把 Open-Meteo 当作 in-situ。 |
| **新加坡**现场天气如何？ | Weather `sg-wx-*-01` | Singapore NEA / data.gov.sg（**Open Data Licence**）。风（+ 温/湿/雨）。 | 把 Open-Meteo 当作 in-situ；把 PSI 当作站点。 |
| 新加坡区域 **PSI / PM2.5** 如何？ | Air `sg-psi-*-01` | NEA PSI（**Open Data Licence**）。区域 24h 指数。 | 参考级监测仪；OpenAQ。 |
| **香港**现场天气如何？ | Weather `hko-wx-*-01` | HKO `rhrread`（**DATA.GOV.HK**）。地点气温（天文台含湿度）。 | 把 Open-Meteo 当作 in-situ。 |
| **比利时**现场 **PM2.5** 如何？ | Air `be-aq-*-01` | IRCELINE SOS（**CC BY 4.0**）。 | OpenAQ；Sensor.Community。 |
| **西班牙**现场天气如何？ | Weather `aemet-wx-*-01` | AEMET OpenData（**Fuente: AEMET**）。需 `GAIA_AEMET_API_KEY`。 | 把 Open-Meteo 当作 in-situ。 |
| **瑞士**现场天气如何？ | Weather `ch-wx-*-01` | MeteoSwiss OGD（**CC BY 4.0**）。 | 把 Open-Meteo 当作 in-situ。 |
| 这条 **瑞士**河流的流量 / 大地水准如何？ | Rivers `bafu-*-01` | BAFU/FOEN LINDAS（**OGD-CH Open-Use**）。Q + 海拔米。 | 洪水 dangerLevel；PEGELONLINE；eHYD；Hub'Eau。 |
| **台湾**现场天气如何？ | Weather `cwa-wx-*-01` | CWA OpenData（**OGDL 1.0**）。需 `GAIA_CWA_API_KEY`。 | 把 Open-Meteo 当作 in-situ。 |
| **法国**现场天气如何（测站）？ | Weather `mf-wx-*-01` | Météo-France DPObs（**Etalab OL 2.0**）。需 `GAIA_METEOFRANCE_APPLICATION_ID`。 | Hub'Eau；把 Open-Meteo 当作 in-situ。 |
| **爱沙尼亚**现场天气如何？ | Weather `ee-wx-*-01` | Estonian Weather Service XML（**CC BY 4.0**）。 | 把 Open-Meteo 当作 in-situ。 |
| **冰岛**现场天气如何？ | Weather `is-wx-*-01` | IMO AWS（**ODC-By**）。 | 把 Open-Meteo 当作 in-situ。 |
| **香港 AQHI** 如何（点击站点）？ | Air `hk-aqhi-*-01` | EPD AQHI（**DATA.GOV.HK**）。1–10 / 10+。 | PM2.5；HKO 天气；IRCELINE。 |

### P12 — 新增 LIVE 针脚与现场 SKU

| 问题 | 针脚 / SKU | 来源与声明边界 |
|---|---|---|
| **奥地利**的现场天气如何？ | `at-wx-*-01` | GeoSphere Austria TAWES，**CC BY 4.0**；仅观测，不是付费预报。 |
| **立陶宛**的现场天气如何？ | `lt-wx-*-01` | LHMT Meteo.lt，**CC BY-SA 4.0**；不用 `/forecasts`。 |
| Nemunas 或 Neris 的水位如何？ | `lt-hydro-*-01` | LHMT 实测水文，**CC BY-SA 4.0**；厘米以米返回。 |
| **拉脱维亚**的现场天气如何？ | `lv-wx-*-01` | LVGMC HVD CSV，**CC0-1.0**；超过 6 小时 → offline。 |
| Daugava 或 Lielupe 的水位如何？ | `lv-hydro-*-01` | LVGMC 水文，**CC0-1.0**；不是洪水预警。 |
| 这个法国流域有 Vigicrues 警报吗？ | `vic-*-01` | VIC WARNING，**Etalab OL 2.0**；绿色/为空不等于「安全」，也不是 Hub'Eau。 |
| 法国全国发电碳强度是多少？ | `rte-grid-01` | RTE éCO2mix，**Etalab OL 2.0**；仅发电，不含进口或全生命周期。 |
| 这个爱尔兰 OPW 测站的水位如何？ | `ie-river-*-01` | waterlevel.ie，**CC BY 4.0**；水位而非洪水 CAP。 |
| **日本**的现场天气如何？ | `jp-wx-*-01` | JMA AMeDAS，Public Data License；须注明 JMA，不是预报许可。 |
| JMA 是否报告了地震？ | `jma-quake-01` | JMA 官方 `list.json`；不是 p2pquake，也不替代 USGS/EMSC。 |
| 西北太平洋当前哪个台风活跃？ | `jma-typhoon-01` | JMA targetTc，Public Data License；空季 → offline，不是 NHC/JTWC。 |
| **捷克**的现场天气如何？ | `cz-wx-*-01` | ČHMÚ climate-now，**CC BY 4.0**；不要把 Open-Meteo 当测站。 |
| **韩国**的现场天气如何？ | `kr-wx-*-01` | KMA ASOS，Public Nuri Type 1；需要 `GAIA_KMA_SERVICE_KEY`，不是 AirKorea。 |
| Copernicus 是否观察到洪水？ | `gfm-flood-01` | Copernicus GFM，**CC BY 4.0**；需要 `GAIA_GFM_TOKEN`，不是 GloFAS 预报。 |
| 当前 Estonia EWS 温度的稳健共识是什么？ | `atlas.field.consensus@v1`，网格 `ee-wx` | 带回执的 LIVE 实地读数中位数 / biweight；不是预报或官方国家数字。 |
| 当前 Estonia EWS 快照的空间 GP 后验在哪里？ | `atlas.field.posterior@v1`，网格 `ee-wx` | RBF GP 对当前数据及方差插值；不是预报或国家 nowcast。 |
| 不挑站时应查询哪些莱茵河测站？ | `atlas.mesh.sample@v1`，网格 `pegel` | LIVE PEGELONLINE 的 Halton 子集；用相同 `skip` 重放，不是 Sortes ECVRF。 |
| 比利时 AQ 网络是否分成两个簇？ | `atlas.field.shape@v1`，网格 `be-aq` | LIVE IRCELINE 的随半径变化 H0 连通分量；不是 AQI 或 Betti-1 环。 |

**Analyst 起始问法（live now）**

- 「关掉其他图层。这个 **viewport** 里最亮的 FIRMS **VIIRS 热点**是哪一个？注明 NASA FIRMS。」
- 「`nws-flood-01` 是否 online？若是，引用 CAP 标题。若 offline，说明**警报产品**为空——不要推断安全。」
- 「距这次点击最近的 LIVE 河流**针脚**——只要**读数**，不要当成**洪水预警**。」
- 「芬兰公共 AIS：视野内多少艘船？注明 Fintraffic。不要叫它全球 AIS。」

**watchbox** 示例：图层 `fire` + bbox；`flood` + 美国 bbox；`ais` + 波罗的海 bbox。

---

## Proposed — sell（2026-08-14 审计）

这六个已审计 SKU（NHC、EMSC、EA flood、PTWC、Kystverket AIS、ADSB.lol）**已接入** — 见 **Live now**。需先部署 **GAIA，再部署 ATLAS** 后才会出现在地图上。

### 1. 「大西洋 / 东太平洋现在有哪个**热带气旋**？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 新 `gaia.cyclone.read@v1`（不要塞进 EONET） |
| **上游** | NOAA NHC `CurrentStorms.json` — 美国公有领域 |
| **地理** | 大西洋 + 东太平洋。不是西北太平洋（台风）。NHC 盆地对应：**飓风**。 |
| **出售 / 嵌入** | 可以。空季 → offline / 不扣款，与海啸 CAP 相同。 |
| **Analyst** | 「列出 NHC 活跃风暴的 lat/lon 与强度。这不是 EONET，也不是全球气旋源。」 |
| **不得** | 用 NHC 回答「日本附近的台风」。 |

### 2. 「欧洲地震是否比 USGS M≥2.5 更密？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 现有 `gaia.quake.read@v1`，新 `device_id` `emsc-01` |
| **上游** | EMSC FDSN `seismicportal.eu` — **CC BY 4.0**（[服务页](https://www.seismicportal.eu/fdsn-wsevent.html)） |
| **地理** | 欧地中海较密；全球 M≥4.5。须注明 EMSC。参数为初步值。 |
| **出售 / 嵌入** | 可以。与 `usgs-quake-01` 分开的**针脚**。 |
| **Analyst** | 「在此 **viewport** 比较 EMSC 与 USGS。不要判胜负；分别引用两个 `source`。」 |
| **不得** | 在全球范围替换 USGS。 |

### 3. 「英格兰有没有**洪水预警**？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 现有 `gaia.flood.read@v1`，新 `ea-flood-01`（可选把河流**锚点**放在 `gaia.river.read@v1`） |
| **上游** | Environment Agency 实时 API — **OGL**，无需密钥。署名：EA 洪水与河道水位数据。 |
| **地理** | **英格兰**，不是整个英国（苏格兰 SEPA / 威尔士 NRW 另算）。 |
| **出售 / 嵌入** | 可以。补上仅覆盖美国的 NWS CAP。 |
| **Analyst** | 「英格兰的 EA **警报产品**。除非河流**针脚** online，否则不是泰晤士河 **in-situ** 水位。」 |
| **不得** | 说成「英国洪水」或抓取 GloFAS。 |

### 4. 「太平洋有没有海啸**警报产品**？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 现有 `gaia.tsunami.read@v1`，新 `ptwc-01` |
| **上游** | PTWC / `tsunami.gov` Atom 或 CAP — 美国公有领域 |
| **地理** | 太平洋（PTWC 盆地）。补上偏美国的 NWS CAP。 |
| **出售 / 嵌入** | 可以。空源 → offline。这是**警报产品**，不是验潮仪。 |
| **Analyst** | 「分别引用 PTWC 与 NWS 海啸针脚。空 ≠ 解除警报。」 |
| **不得** | 下令疏散；Analyst 不是国家预警当局。 |

### 5. 「挪威附近有哪些船？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 现有 `gaia.ais.public.read@v1`，新 `kystverket-ais-01`（或等价 id） |
| **上游** | Kystverket，经 BarentsWatch — **NLOD**，可商用但须署名。免费 OpenID 注册（与 `GAIA_KNMI_API_KEY` 同类）。 |
| **地理** | 挪威水域，不是芬兰，不是全球。 |
| **出售 / 嵌入** | 可以，前提是 REST 主机 + 令牌已钉进 **allowlist**。 |
| **Analyst** | 「挪威公共 **AIS**。注明 Kystverket / BarentsWatch。不是 Fintraffic，也不是自有边缘 AIS。」 |
| **不得** | 与 `fintraffic-ais-01` 合成一个「欧洲 AIS」。 |

### 6. 「这一点上空有哪架飞机——没有我们自己的接收机？」

| | |
|--|--|
| **状态** | Proposed — sell |
| **SKU** | 新 `gaia.adsb.public.read@v1`（与公共 AIS 平行；**不是** `gaia.adsb.read@v1`） |
| **上游** | [ADSB.lol](https://www.adsb.lol/docs/open-data/api/) `api.adsb.lol` — **ODbL 1.0** |
| **地理** | 数据源覆盖范围，不是国家强制。 |
| **出售 / 嵌入** | 可以，诚实口径与 Sensor.Community 相同：商业**读数**可以；公开的派生库须 **ODbL 相同方式共享**。隔离 ADS-B 派生库。只钉 `api.adsb.lol`。 |
| **Analyst** | 「经 ADSB.lol 的公共 ADS-B（ODbL）。不是我们的 dump1090。不是 OpenSky / ADSBx。」 |
| **不得** | 在航空聚合器之间静默回退。 |

---

## Hold — 暂不出售

### EPA UV 作为付费「运营台」

**用例文案 Hold**（中继仍可在地图上 LIVE）。

- 针脚标题只有一个 `uv_index`（按 ZIP 的预报日最大）。不过关：单标量不是多信号商业台。
- 这是 EPA **小时预报**，不是现场日射计。
- 当针脚/簇至少卖 ≥2 个可用字段且不虚构仪器时再解锁用例。

**Live now 替代：** Met Éireann / NWS / Open-Meteo 天气；不要单独把 UV 当「场地安全」卖。

### 把 GDACS 当成「灾害，而不是 VIIRS 点」

**Hold。** 运营问题有意义，但按我们的规则该源还不能卖。

- 官方 [GDACS Terms of use（2025 年 3 月）](https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf) **并未**授予 CC BY 4.0。它描述的是模型冲击估计、「按原样提供」，并写明警报**不得**在未经法定当局确认前用于决策。
- GDACS **不会**给 FIRMS **VIIRS 热点**分类。它是联合国/欧委会多灾种**警报产品** / 国际援助模型分数——与热探测、EFFIS 属于不同主张类别。
- 第三方页面上的「CC BY 4.0」不是钉死。同一道门槛曾让 EMSC 在 FDSN 页面写明 CC BY 4.0 之前不能进代码。

**Live now 替代：** FIRMS（探测）+ EFFIS（欧盟当前火情）+ EONET（NASA 事件）。Analyst 须把这三个 `source` 分开。

### 把 Geoscience Australia 地震当成「澳大利亚在震吗？」

对实时 HTTPS **中继** **Hold**，不是对这个想法 Hold。

- data.gov.au 的 “Recent Earthquakes” 是 **CC BY 3.0 Australia**，但目录记录 ≠ 已 allowlist、已验证新鲜度的 GeoJSON/WFS。
- USGS 已经报告超过其震级阈值的澳大利亚事件。这才是诚实的 **Live now** 答案。
- 等到 GA NEAC 机器端点像 GeoNet（`api.geonet.org.nz`）那样钉死再开。

### USGS **水质** — LIVE 网络

当前连续测量 OGC 集合已经接入：买方 bbox 返回全部匹配站点，每个站点各自成为一个读数坐标。保留时间、provisional/approval 和 qualifier；`gage_height_m` 仍然不是水质。覆盖范围：美国。

---

## Analyst 必须拒绝的提问

| 提示 | 原因 |
|------|------|
| 「宣布这条海岸疏散 / 解除警报。」 | ATLAS 不是预警当局。引用**警报产品**或说明 offline。 |
| 「这个 FIRMS 像素是 GDACS 灾害吗？」 | 主张类别不同；GDACS 处于 **Hold**。 |
| 「全球 AIS / 全球闪电 / BoM 官方澳大利亚天气。」 | 没有可售 SKU 的许可（GFW NC、Blitzortung NC、BoM FTP 非商用）。 |
| 「用 USGS 查这条英国河的水质。」 | 地理不对：已接入的 USGS 连续网络覆盖美国，不覆盖英格兰。 |
| 「用 NHC 查台风。」 | 盆地不对。 |

---

## 相关

- 运营地图：[`GUIDE.zh.md`](GUIDE.zh.md)
- 中继许可：[`gaia/docs/i18n/LIVE-RELAYS.zh.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.zh.md)
- 术语表（**watchbox**、**警报产品**、**AIS**、**ADS-B**、**热带气旋**）：[`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
