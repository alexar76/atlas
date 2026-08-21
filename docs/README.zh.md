# ATLAS

> 🌐 [English](../README.md) · [Русский](README.ru.md) · [Español](README.es.md) · [Français](README.fr.md) · **中文** · [术语表](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


<p align="center">
  <strong>ATLAS</strong> — 覆盖 <a href="https://iot.modelmarket.dev/">GAIA</a> 中继的行星级<strong>传感器地图</strong><br/>
  诚实的 <strong>LIVE</strong> vs <strong>SIM</strong> 标记 · 可选<strong>三维地球</strong> · 属于 <a href="https://github.com/alexar76">alexar76</a> AI 智能体经济
</p>

<p align="center">
  <strong><a href="https://atlas.modelmarket.dev/">在线地图</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/atlas/">落地页</a></strong>
  ·
  <strong><a href="https://iot.modelmarket.dev/">GAIA</a></strong>
  ·
  <strong><a href="https://magic-ai-factory.com/monitor/">Alien Monitor</a></strong>
</p>

**文档：** [EN](GUIDE.md) · [RU](i18n/GUIDE.ru.md) · [ES](i18n/GUIDE.es.md) · [FR](i18n/GUIDE.fr.md) · [ZH](i18n/GUIDE.zh.md)  
**添加传感器：** [add-gaia-atlas-sensor](https://github.com/alexar76/aicom/blob/main/docs/add-gaia-atlas-sensor.md)

ATLAS 是生态的**物理传感器地图**：天气、空气质量、潮汐、河流、海洋、英国电网碳强度、地震、**野火**、**辐射**、**GNSS 完好性**站、独立来源的 **GNSS 干扰**报告、**芬兰公共 AIS**、**NWS 海啸 CAP**、可选边缘 **ADS-B/AIS** 与能源 — 均来自 [GAIA](https://iot.modelmarket.dev/) 中继。每个 GNSS 站有稳定可点的 `point_id`；智能体可通过 `atlas.point.read@v1` 查询，或经 `atlas.gnss.degradation.read@v1` 请求签名的 point/bbox/route 场。**新的开放数据设备在 GAIA 注册；地图图层、标记与 watchboxes 属于 ATLAS**。仅当 GAIA 暴露上游 provenance `source` URL 时标记为 **LIVE**；仿真器为 **SIM**。附带 **ATLAS Analyst**（默认 DeepSeek `deepseek-v4-pro`）、防 prompt-injection 防火墙，以及完整的 AICOM / AIMarket **生态简报**。

## 图库

<p align="center"><img src="../docs/screenshots/readme/map.png" alt="ATLAS" width="820"></p>

## 表面

| 表面 | URL / path |
|---------|------------|
| **公开地图** | https://atlas.modelmarket.dev/ |
| 落地页 | https://alexar76.github.io/atlas/ |
| Alien Monitor 嵌入 | `/embed` |
| Health | `/health` |
| Snapshot / viewport / station / watchboxes | `/api/v1/*` |
| Analyst 聊天 | `/api/ai/ask` |

## 快速开始

```bash
pip install aimarket-atlas
export ATLAS_GAIA_URL=https://iot.modelmarket.dev
atlas --host 127.0.0.1 --port 9330
```

## 生产

```bash
./scripts/deploy_atlas.sh --remote root@<host>
```

## 负载模型

| 机制 | 角色 |
|-----------|------|
| Cheap fleet poll | 仅标记 |
| 视口读数 | **可见 bbox** 内的传感器 |
| LIVE vs SIM | 有 `source` ⇒ LIVE；否则 SIM |
| Analyst | 快照 + 防火墙 + 重试；语言 = 问题 ∥ UI 区域设置 |

买方**不能**把 lat/lon 传入 GAIA invoke。

## 测试

```bash
pip install -e ".[dev]" && pytest -q
```

**101** 项测试。

## 许可

MIT — [LICENSE](../LICENSE)。
