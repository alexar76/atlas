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

对带运营方**锚点**的设备，GAIA **invoke** 不接受买方 lat/lon。事件源（FIRMS、地震、CAP）把坐标放在**读数**里。

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
| 是否有美国海啸**警报产品**？ | Tsunami `nws-tsunami-01` | NWS CAP warning/watch/advisory。经常**空 → offline**。 | 验潮仪。空不等于「地球上没有海啸」。 |
| 这个潮汐**锚点**水位是多少？ | Tide | NOAA CO-OPS / UHSLC **in-situ**。 | 海啸**警报产品**。 |
| **芬兰水域**有哪些船？ | Public AIS `fintraffic-ais-01` | Fintraffic Digitraffic 快照，**CC BY 4.0**。 | 全球 AIS、GFW、AISStream 或自有 `gaia.ais.read@v1`。 |
| **我们的**接收机看到哪些飞机？ | Edge traffic `feeder-adsb-01` | 自有 dump1090 ingest。未推送则为 offline。 | ADSBx / OpenSky / 公共聚合器。 |
| USGS 是否报告了地震（通常 M≥2.5）？ | Earthquakes `usgs-quake-01` | USGS GeoJSON 事件 lat/lon。 | 欧地中海密度，或澳大利亚本地目录。 |
| 新西兰本地地震？ | Earthquakes `geonet-01` | GeoNet，**CC BY 3.0 NZ**。 | 全球目录。 |

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

### 把 USGS **水质**当成单独 LIVE SKU

**Hold。** 许可没问题（美国公有领域）。意义和新鲜度不够。

- `gaia.river.read@v1` 上的 `gage_height_m` **不是** **水质**。这条界限保留。
- 审计时 [USGS Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/) 仍标明 **alpha** / 不适合生产。先前试验站点的旧 IV 序列已过期——所以 P2 没有接入 WQ。
- 离散化验样本不是「此刻」**读数**。

仅当有一个运营方**锚点**，其连续参数（如温度、溶解氧）被证明新鲜时才开；过期则 fail-closed。

---

## Analyst 必须拒绝的提问

| 提示 | 原因 |
|------|------|
| 「宣布这条海岸疏散 / 解除警报。」 | ATLAS 不是预警当局。引用**警报产品**或说明 offline。 |
| 「这个 FIRMS 像素是 GDACS 灾害吗？」 | 主张类别不同；GDACS 处于 **Hold**。 |
| 「全球 AIS / 全球闪电 / BoM 官方澳大利亚天气。」 | 没有可售 SKU 的许可（GFW NC、Blitzortung NC、BoM FTP 非商用）。 |
| 「用 USGS 查这条英国河的水质。」 | 地理不对，而且今天没有 WQ SKU。 |
| 「用 NHC 查台风。」 | 盆地不对。 |

---

## 相关

- 运营地图：[`GUIDE.zh.md`](GUIDE.zh.md)
- 中继许可：[`gaia/docs/i18n/LIVE-RELAYS.zh.md`](https://github.com/alexar76/gaia/blob/main/docs/i18n/LIVE-RELAYS.zh.md)
- 术语表（**watchbox**、**警报产品**、**AIS**、**ADS-B**、**热带气旋**）：[`docs/localization-glossary.md`](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)
