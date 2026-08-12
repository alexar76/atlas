"""Static AICOM / AIMarket ecosystem brief for ATLAS Analyst.

Sensor numbers always come from the live ATLAS snapshot. This brief answers
architecture / product / URL questions about the broader economy.
"""

from __future__ import annotations

ECOSYSTEM_BRIEF = """
## AICOM / AIMarket ecosystem (authoritative brief)

Mental model: **aicom** (Factory) builds products → listed & invoked via **AIMarket**
(protocol + Hub) → **oracles ×17** sell signed math → **Metis** verifies high-stakes
cognition → **GAIA** sells attested physical-world readings → **ATLAS** (you) maps those
readings → **ARGUS** is the human touchpoint → priced on **ACEX** → visualized in 3D by
**Alien Monitor**. Beyond ARGUS, humans configure infra; machines trade.

### Core rails
- **AI-Factory** (magic-ai-factory.com) — autonomous multi-agent pipeline that designs,
  builds, tests, and publishes products / capabilities into the Hub.
- **AIMarket Protocol v2** (aimarket-protocol) — open standard: discovery, channels,
  invoke, settle, signed manifests (/.well-known/ai-market.json).
- **AIMarket Hub** (modelmarket.dev, :9083) — federated capability catalog, search,
  invoke, payment channels, plugins (safety, TEE escrow, reputation, provenance, …).
- **AI Service Mesh** (:8090, service-mesh.modelmarket.dev) — agent discovery,
  zero-trust verify, escrow, agent-to-agent payments.
- **SDKs / clients** — aimarket-agent (Python), aimarket-sdks (TS/Rust/Dart),
  aimarket-widget (embed), aimarket-desktop (Flutter/Tauri/VS Code SKUs),
  aimarket-bridges (LangGraph / CrewAI / AutoGen adapters with signed receipts).

### Oracle classes (three tiers)
1. **Math oracles ×17** (oracles.modelmarket.dev) — Platon, Chronos (VDF), Lattice,
   Murmuration, Lumen (EigenTrust/PageRank reputation), Colony, Turing, Ablation,
   Percola, Fermat, Gauss, Sortes, Aestus, Betti, Kantor, Fourier, Landauer, …
   Ed25519-signed artifacts; MCP via aimarket-oracle-gateway (~35 tools).
2. **Cognitive — METIS** (metis.modelmarket.dev) — Understanding Council → confidence
   gate → layered MoA → verifier; OpenAI-compatible; factory confidence gate;
   PyPI aimarket-metis. Shared tools via **aimarket-mcp** (web_fetch, web_search,
   metis_verify; SSRF-hardened).
3. **Physical — GAIA** (iot.modelmarket.dev, :9320) — virtual IoT + LIVE public-API
   relays (Open-Meteo, NWS, NOAA tides/NDBC, USGS river/quakes, UK grid carbon, …). Each reading
   Ed25519-attested + statistical plausibility; Pay-on-Verified escrow. Same Hub
   discover → channel → invoke → settle loop.

### ATLAS (this product)
Planetary **MapLibre** sensor map over GAIA relays. Pins are **LIVE** only when GAIA
exposes provenance `source`; otherwise **SIM**. Public: atlas.modelmarket.dev ·
embed: /embed · Alien Monitor node id=`atlas` (stations + mini-map + full-map CTA).
ATLAS Analyst is grounded on the server snapshot for numbers and this brief for
ecosystem Q&A. ATLAS is read-only — it does not sell Hub capabilities or write sensors.

### Human / community / broadcast
- **ARGUS-3** (magic-ai-factory.com/argus/) — sole intended human UI; WARDEN MCP firewall
  (LUMEN); crypto off by default; install: curl …/install | bash.
- **DIOSCURI** — CASTOR (Telegram) + POLLUX (Discord); MNEMOSYNE KB; AEGIS firewall.
- **THEOROS** — Agent Sovereignty Canon; weekly #the-canon via DIOSCURI.
- **HELIOS** — yaml → voiced video → YouTube (@My-AI-Factory), private until approve.

### Capital / observability / learning
- **ACEX** + **Pulse Terminal** (magic-ai-factory.com/pulse/) — CapShares, lending, AMM.
- **Agent Lottery** (lottery.modelmarket.dev) — unbiasable oracle draws · machine UBI.
- **Alien Monitor** (magic-ai-factory.com/monitor/) — live 3D ecosystem graph + AI.
- **SKOPOS** (skopos.modelmarket.dev) — fleet nginx/Apache analytics, Security Center.
- **School / Courses** — edu.modelmarket.dev · aimarket-courses academies.
- **Ecosystem map / docs** — modeldev.modelmarket.dev · docs/ecosystem/knowledge-base.md
  · whitepaper docs/ecosystem/whitepaper/en.md · verify.modelmarket.dev (provenance).

### Trust & settlement (one line)
Byzantine hubs/agents assumed; bonded reputation; non-custodial channels; oracle
outputs verifiable without trusting the operator; Base/EVM USDC escrow + Solana paths.

<!-- BEGIN GENERATED ecosystem-components -->
### Component registry

Generated from scripts/satellite-map.yaml — do not hand-edit. GitHub org: alexar76.
Run: python3 scripts/sync_knowledge_base.py --write (37 components).

- acex: ACEX — Agent Capital Exchange: listings, CapShares, lending, and AMM for AI agents. · https://alexar76.github.io/aicom/
- ai-service-mesh: AI Service Mesh — autonomous agent discovery, verification, escrow, and payments. · https://service-mesh.modelmarket.dev/
- aicom (profile README): AI-Factory — autonomous pipeline that designs, builds, tests, and publishes products. · https://magic-ai-factory.com/
- aicom-landing: AI landing generator — one prompt → self-contained HTML in ~30-60s (MIT, 20 style presets). · https://magic-ai-factory.com/landing-page-generation/
- aicom-wiki (repo aicom.wiki): Documentation wiki for AI-Factory and the AIMarket ecosystem.
- aimarket-agent: Python client for discovering and invoking AIMarket hub capabilities. · https://alexar76.github.io/aicom/
- aimarket-bridges: AIMarket capabilities as native tools for LangChain/LangGraph, CrewAI and AutoGen — signed receipts, per-task budget caps, free trial. The adapter layer for agents built on someone else's framework. · https://modeldev.modelmarket.dev/bridges/
- aimarket-courses: 10 hands-on AIMarket academy courses — orchestration, oracles, MCP security, agent economy (en/ru/es/fr/zh). · https://alexar76.github.io/aimarket-courses/
- aimarket-desktop: 10 desktop & IDE apps for AIMarket — Flutter, Tauri, and VS Code in one Melos monorepo. · https://alexar76.github.io/aicom/
- aimarket-hub: AIMarket Hub — federated capability catalog, channels, invoke API, and plugins. · https://modelmarket.dev/
- aimarket-mcp: Ecosystem MCP gateway — web fetch/search + Metis verify behind one SSRF-hardened MCP endpoint (Streamable-HTTP). Consumed by Metis and ARGUS via the aimarket-web preset. · https://glama.ai/mcp/servers/alexar76/aimarket-mcp
- aimarket-oracle-gateway: MCP server: verifiable oracle services (Platon VRF, Chronos VDF, LUMEN reputation) for AI agents — pay-per-call over the AIMarket protocol, every result independently verifiable. · https://glama.ai/mcp/servers/alexar76/aimarket-oracle-gateway
- aimarket-plugins: 15 AIMarket hub plugins — TEE escrow, channels, reputation, safety, and more. · https://alexar76.github.io/aicom/
- aimarket-protocol: AIMarket Protocol v2 — open specs, JSON schemas, and test vectors. · https://alexar76.github.io/aicom/
- aimarket-school: AIMarket School — 10 free clip lessons (Try-it + Colab) that on-ramp into the academies. Live portal: edu.modelmarket.dev · https://edu.modelmarket.dev/
- aimarket-sdks: Official AIMarket client SDKs — Dart, TypeScript, and Rust. · https://alexar76.github.io/aicom/
- aimarket-widget: Embeddable AIMarket storefront widget — drop-in JS/CSS for any website. · https://modelmarket.dev/widget/demo
- alien-monitor: Alien Monitor — real-time 3D ecosystem pulse visualizer with AI assistant. · https://magic-ai-factory.com/monitor/
- argus: ARGUS-3 — wallet-native, security-hardened personal agent; demand-side reference client (WARDEN MCP firewall scored by LUMEN + native AIMarket consumer/provider). Owner-locked Telegram, multi-provider, autonomous offline. · https://magic-ai-factory.com/argus/
- argus-wiki (repo argus.wiki): Documentation wiki for ARGUS-3 — install, WARDEN, channels, economy, Arena.
- atlas: Planetary sensor map over GAIA's live relays (weather, air, tide, river, marine, grid, quake, energy) with an AI Analyst panel and an Alien Monitor embed. ATLAS maps readings; GAIA attests them. · https://alexar76.github.io/atlas/
- dioscuri: DIOSCURI — one mind, two heavens. Twin community agents: CASTOR rides Telegram, POLLUX holds Discord. Shared GitHub-synced knowledge base (MNEMOSYNE) behind a prompt-injection firewall + moderation shield (AEGIS). · https://alexar76.github.io/dioscuri/
- gaia: Physical oracle: virtual IoT sensors plus LIVE public-API relays, sold as attested readings with a statistical plausibility gate inside a Metis envelope. · https://iot.modelmarket.dev · port 9320
- helios: HELIOS — self-hosted broadcast pipeline for the AIMarket ecosystem. Template in, voiced video out, queued to YouTube — private by default until you approve. · https://alexar76.github.io/helios/
- linkedin-profile-coach (repo linked-in-profile-coach): LinkedIn Profile Coach — Flutter desktop/mobile app for 24 LinkedIn sections, AI draft, scoring, and .docx resume support. · https://alexar76.github.io/linked-in-profile-coach/
- logos: LOGOS — federation analytics engine. Cross-hub query, anomaly detection, NL insights via Metis council. The analytical brain of the AIMarket federation. One node, every insight. · https://alexar76.github.io/logos/
- lottery: AI-Agent Oracle Lottery — an on-chain lottery that is an economic actor of the AI ecosystem: agents buy tickets, an unbiasable Platon+Chronos oracle beacon draws a LUMEN-reputation-weighted winner. · https://lottery.modelmarket.dev/
- metis: Cognitive verification tier: Understanding Council, fail-closed confidence gate, layered MoA, grounded verifier. Also available to MOMUS as an independent external verifier of a finding. · https://metis.modelmarket.dev
- momus: Adversarial-audit red team. Runs safe, read-only conformance probes against the ecosystem's own components and emits Ed25519-signed findings. It FINDS and SIGNS but can never pay itself — a separate Treasury key releases bounties, and only on independent verification. Honest outcomes: FINDING / NO_FINDING / INCONCLUSIVE (an unreachable target is neither a finding nor a pass). · https://momus.modelmarket.dev · port 9410
- oracles: Verifiable AI-economy oracles — Platon, Chronos, Lattice, Murmuration, Lumen, Colony, and Turing on shared oracle-core. · https://oracles.modelmarket.dev/
- platon: Platon UMBRAL — educational cave app for oracle #1: 32D dynamical shadow oracle with live AIMarket backend and holographic cockpit. · https://oracles.modelmarket.dev/platon/umbral/
- profile (repo alexar76) (profile README): GitHub profile README — ecosystem map for alexar76. · https://github.com/alexar76
- pulse-terminal: Pulse Terminal — ACEX capital markets dashboard with live agent pricing. · https://magic-ai-factory.com/pulse/
- signal-hunt: Signal Hunt — federation-native investigation game and educational laboratory over real AIMarket Hub telemetry. Observe measured symptoms, commit a diagnosis, prove it with a reproducible Brier-score verdict. Each round is a live lab on federation literacy. Live data only; no seeded anomalies. · https://alexar76.github.io/signal-hunt/
- skopos: Fleet observability dashboard, and the CONDUCTOR of the remediation loop: it receives MOMUS's signed ticket over A2A, drives the AI-Factory to author a patch, asks MOMUS to re-test as the deploy gate, then signs a DeployOrder and publishes it for the addressed node agent to claim. It orders deploys; it never executes one. · https://skopos.modelmarket.dev
- theoros: THEOROS — Agent Sovereignty Canon. High-tech theorist persona: seven precepts for verified agent economic actors, cosmic landing, weekly column via DIOSCURI #the-canon. · https://alexar76.github.io/theoros/
- treasury: The only key that can pay a red-team bounty. A separate role with its own key: MOMUS finds and signs, the Treasury verifies the signatures, recomputes the dedup identity, and releases the finder/fixer/conductor split (50/35/15). Default settlement is the simulated UNI vault; real on-chain payout needs a second, explicit opt-in beyond enabling crypto. · https://momus.modelmarket.dev/treasury · port 9411
<!-- END GENERATED ecosystem-components -->

When the user asks what a sibling product is, answer from this brief (roles + public
URLs). Never invent live Hub/Factory metrics; for ATLAS readings use the snapshot only.
""".strip()


def ecosystem_brief() -> str:
    return ECOSYSTEM_BRIEF
