# ATLAS — 运维与开发指南

**语言：** [EN](../GUIDE.md) · [RU](GUIDE.ru.md) · [ES](GUIDE.es.md) · [FR](GUIDE.fr.md) · [ZH](GUIDE.zh.md)

ATLAS 是生态中的**物理传感器地图**：天气、空气质量、潮汐、英国电网碳强度与地震，数据来自 [GAIA](https://iot.modelmarket.dev) 中继。在 [Alien Monitor](https://magic-ai-factory.com/monitor/) 中为 **ATLAS** 节点（小地图嵌入 + 全图链接），并内置 **ATLAS Analyst**（默认 DeepSeek）。

## 入口

| URL | 作用 |
|-----|------|
| `/` | 完整 MapLibre 地图 + 图层 +「视野内」列表 + AI |
| `/embed` | Monitor iframe 用精简地图 |
| `/health` | 存活检查 |
| `/api/v1/*` | Snapshot、viewport、站点详情、SSE |
| `/api/ai/*` | 模型提供方 + 基于实时数据的对话 |

## 负载模型

- 后台：仅廉价 **fleet**（图钉），不批量拉 reading。
- `POST /api/v1/viewport`：仅刷新**可见 bbox** 内站点，TTL 缓存（约 45 秒），single-flight。
- 点击 → `GET /api/v1/stations/{id}`：可读详情卡（超过约 20 秒则刷新）。
- AI：服务端注入 LIVE SNAPSHOT（客户端无法伪造数值）。

购买方 **不能** 在 GAIA invoke 中传 lat/lon — 锚点由运维在 GAIA 配置。地震事件坐标在 reading 中返回。

## 图层

| 图层 | 典型 device_id |
|------|----------------|
| 天气 | `om-wx-01`、`nws-01` |
| 空气 | `om-aq-01`、`osm-01`、`sta-01` |
| 潮汐 | `noaa-tide-01` |
| 电网 | `uk-grid-01`（区域） |
| 地震 | `usgs-quake-01` |

## API（摘要）

- `GET /api/v1/snapshot` — 图钉 + 缓存
- `POST /api/v1/viewport` — `{west,south,east,north,force?}`
- `GET /api/v1/stations/{id}` — title / summary / metrics
- `POST /api/ai/ask` — 分析与**态势报告**（`report: true`）

生产 LLM：**`DEEPSEEK_API_KEY`**，模型 `deepseek-v4-pro`。

## Alien Monitor

`ALIEN_ATLAS_URL` / `ALIEN_PUBLIC_ATLAS_URL`（默认 `https://atlas.modelmarket.dev`）。面板：传感器 + `/embed` iframe +「Open full map」。

## 部署

```bash
docker compose -f atlas/docker-compose.local.yml up -d --build
export DEEPSEEK_API_KEY=sk-...
docker compose -f atlas/docker-compose.yml up -d --build
```

仅绑定 `127.0.0.1:9330`，TLS 由 nginx 终止。

## 测试

```bash
cd atlas && pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest -q
```

不依赖在线 GAIA（mock）。完整环境变量与 API 见 [英文版](../GUIDE.md)。

## 诚信说明

ATLAS 是 GAIA 中继之上的地图与分析层，并不拥有传感器硬件。Open-Meteo：CC BY 4.0；NWS/USGS/NOAA：美国政府公有领域。
