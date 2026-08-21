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
    # Ceiling only — GAIA's own edge cuts at 120s, so waiting longer than that
    # could only ever return a 504. Background warms may use the full budget;
    # interactive requests are bounded by viewport_budget_s below.
    gaia_timeout_s: float = 110.0
    # How long a viewport is allowed to wait on cold stations before it answers
    # with what it has. Stragglers keep fetching and land in the cache for the
    # next pan — that is the lazy ring doing its job instead of the user
    # watching a spinner. Measured on prod: one cold Argo directory held an
    # entire viewport for 107s, which is what made detail panels fail.
    viewport_budget_s: float = 6.0
    # FIRMS densify is forced (it is the map's headline layer), so it needs its
    # own budget or it reintroduces the stall on its own: a cold drain took 30s
    # of a 36s response. Warm it runs in ~3s, so this only bites right after a
    # restart — the first pan shows the previous cluster, the next shows fresh.
    fire_budget_s: float = 12.0
    # Once a cluster exists, a pan must not pay for the next drain: the pins
    # already on screen are seconds old and a neighbouring camera shows almost
    # the same fires. Paint them now, swap in the fresh drain when it lands.
    # Only the FIRST paint (no cluster yet) spends the full fire_budget_s —
    # an empty map on arrival is the one thing worse than a short wait.
    fire_budget_pan_s: float = 2.5
    # Ceiling on reads that outlived their caller's budget and keep running.
    # They share GaiaClient's FIFO pacer with interactive requests, so an
    # unbounded backlog just relocates the stall to the next viewport.
    max_detached_reads: int = 8
    # How long a viewport waits for the fleet loop's first snapshot before it
    # answers `warming: true`. Never block a user on the full catalog warm —
    # at 72 requests/min that is minutes, and it is already in flight.
    fleet_wait_s: float = 3.0
    gaia_concurrency: int = 4
    # GAIA's public edge allows 120 invokes/minute per client. ATLAS keeps a
    # deliberate reserve and paces its own background traffic so a larger fleet
    # cannot burst into 429s or starve an interactive map click.
    gaia_requests_per_minute: float = 72.0
    gaia_max_retries: int = 5
    gaia_retry_base_s: float = 3.0
    gaia_retry_max_s: float = 20.0

    # Cheap fleet/pin poll — no per-device readings.
    fleet_poll_interval_s: float = 30.0
    stale_after_s: float = 120.0

    # Per-station reading cache (viewport + click share this).
    # A full physical fleet is larger than one public rate-limit window. Keep
    # background readings for five minutes; station detail can still force a
    # much fresher read through ``detail_fresh_s`` below.
    reading_ttl_s: float = 300.0
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
    # It is also the master key to the watchbox registry: it can read, list and purge
    # every tenant's box, so it is an operator credential, never a buyer's.
    operator_token: str = ""

    # Self-serve watchbox creation. A buyer normally receives a per-watchbox owner token
    # from the operator; with this on, anyone may create a box and is handed the owner
    # token in the create response. OFF by default because an anonymous create is both
    # an unbounded resource (every box costs a check per interval) and an outbound-POST
    # amplifier — the owner-token model makes self-serve *safe to enable*, which is a
    # deployment decision rather than something to inherit by accident.
    watchbox_open_signup: bool = False
    # Ceiling on live self-serve boxes; ignored for operator-created ones.
    watchbox_self_serve_max: int = 200
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
