"""Runtime settings for ATLAS."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 9330
    public_url: str = "http://127.0.0.1:9330"
    cors_origins: str = "*"

    # Upstream GAIA gateway (free demo invokes — no escrow needed on public edge).
    gaia_url: str = "https://iot.modelmarket.dev"
    gaia_product_id: str = "gaia.gateway"
    gaia_timeout_s: float = 8.0
    gaia_concurrency: int = 4

    # Cheap fleet/pin poll — no per-device readings.
    fleet_poll_interval_s: float = 30.0
    stale_after_s: float = 120.0

    # Per-station reading cache (viewport + click share this).
    reading_ttl_s: float = 45.0
    # Click detail may force-refresh if older than this.
    detail_fresh_s: float = 20.0

    # Soft rate limit for public HTTP (per client IP, sliding window).
    rate_limit_per_min: int = 180

    # Quake history kept in the snapshot for map trails.
    quake_history: int = 24

    # Backward-compatible alias used by older compose files.
    poll_interval_s: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
