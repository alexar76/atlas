"""Runtime settings for ATLAS."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 9330
    public_url: str = "https://atlas.modelmarket.dev"
    # LLM HTTP retries (transient 429/5xx/timeouts).
    llm_max_retries: int = 3
    llm_retry_base_ms: float = 400.0
    llm_retry_max_ms: float = 4000.0
    cors_origins: str = "*"

    # Upstream GAIA gateway (free demo invokes — no escrow needed on public edge).
    gaia_url: str = "https://iot.modelmarket.dev"
    gaia_product_id: str = "gaia.gateway"
    # FIRMS full-CSV parse regularly exceeds 8s; keep other reads snappy via
    # concurrency, but allow slow live relays (fire/radiation) to finish.
    gaia_timeout_s: float = 180.0
    gaia_concurrency: int = 4

    # Cheap fleet/pin poll — no per-device readings.
    fleet_poll_interval_s: float = 30.0
    stale_after_s: float = 120.0

    # Per-station reading cache (viewport + click share this).
    reading_ttl_s: float = 45.0
    # Click detail may force-refresh if older than this.
    detail_fresh_s: float = 20.0

    # Lazy prefetch: pad viewport (degrees) then warm remaining catalog in background.
    # Fleet is ~52 pins (12 anchors + 20-city Open-Meteo mesh ×2) — an in-process
    # TTL cache is still enough; Redis/PG only if we ever run multiple replicas.
    viewport_pad_deg: float = 25.0
    warm_all_on_fleet: bool = True
    analyst_warm_all: bool = True

    # Stations included in the Alien Monitor payload (ranked: reading → live → online).
    monitor_station_limit: int = 24

    # Soft rate limit for public HTTP (per client IP, sliding window).
    rate_limit_per_min: int = 180
    # Paid/expensive paths get their own much tighter budget:
    #   ai      → every LLM call burns provider tokens
    #   force   → force/fresh/refresh bypass the TTL cache and hit GAIA N times
    rate_limit_ai_per_min: int = 12
    rate_limit_force_per_min: int = 6
    # When set, X-ATLAS-Token holders skip the force budget (operator nudges).
    operator_token: str = ""
    # Reverse-proxy hops in front of ATLAS (nginx = 1). The client IP is taken
    # this many entries from the RIGHT of X-Forwarded-For; the left side is
    # caller-controlled and must never key a budget.
    trusted_proxy_hops: int = 1

    # Local LLM backends (Ollama / LM Studio) are only reachable when someone
    # actually runs them next to ATLAS. Without this opt-in they are listed but
    # reported unavailable, so `any_provider_configured()` stays honest and the
    # offline cache stub can answer instead of failing with a connection error.
    local_llm_enabled: bool = False

    # Quake history kept in the snapshot for map trails.
    quake_history: int = 24

    # AIMarket Hub — live federation catalog for ATLAS Analyst (read-only).
    hub_url: str = "https://modelmarket.dev"
    federation_cache_ttl_s: float = 120.0
    federation_timeout_s: float = 6.0
    federation_capability_limit: int = 80
    # Soft cap for FIRMS/hotspot pins inside the Analyst prompt (map keeps all).
    analyst_fire_pin_limit: int = 24
    # Map Wildfire: max ranked FIRMS hotspots to pull via GAIA packets (factual
    # ceiling for collect). Viewport map densify uses firms_map_pin_limit.
    firms_hotspot_limit: int = 250000
    # Top-N brightest detections densified per camera bbox into the client cache.
    # Map paints every in-view pin (no MapLibre clustering). Sidebar total = hotspot_matched.
    firms_map_pin_limit: int = 2000
    # Identical camera bbox within this window reuses the cached FIRMS cluster
    # instead of forcing another GAIA densify (protects the device lock).
    firms_viewport_ttl_s: float = 20.0
    # Deadline for the targeted densify inside paid product invokes; past it
    # the SKU answers from the store cache instead of hanging the buyer.
    product_densify_timeout_s: float = 10.0

    # Hub federation signing (Ed25519). Prefer ATLAS_SIGNING_SEED_B64 in prod.
    signing_key_path: str = "data/atlas_signing_key"

    # Backward-compatible alias used by older compose files.
    poll_interval_s: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
