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

全部 **39 个图层**的当前列表、精确颜色、含义和设备示例见
[ATLAS 地图图例](LEGEND.zh.md)。该图例与地图使用同一运行时目录生成。
目录当前包含 **369 个已配置设备**；事件和密集数据源可在运行时创建更多读数点。

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
| DART | `noaa-dart-01`, `dart-*` | 固化官方 NDBC 目录中的全部 43 个活动站 |
| EPA RadNet | `radnet-*` | 全部 140 个 EPA 官方监测点坐标，不是三个演示城市 |
| NEXRAD 状态 | `nexrad-status-01` | 每个 WSR-88D 站点位于自身坐标；是状态，不是反射率 |
| 坐标网格/模型 | `imerg-01`, `cams-*`, `soil-*`, `solar-*`, `snow-*`, `nsidc-ice-01`, `lst-*` | 买方 `lat`/`lon`；ATLAS 使用返回的源/查询网格坐标 |

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
