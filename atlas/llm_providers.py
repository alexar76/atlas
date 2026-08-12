"""LLM provider registry — factory-compatible (OpenAI / Anthropic / Ollama / LM Studio)."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import httpx
import yaml

from .config import get_settings

DEFAULT_PROVIDER = "deepseek_api"
DEFAULT_MODEL_HEAVY = "deepseek-v4-pro"
DEFAULT_MODEL_LIGHT = "deepseek-v4-flash"

_HERE = Path(__file__).resolve().parent
# Docker: /app/atlas → parent=/app ; monorepo: atlas/atlas → parent=atlas/
# Installed wheel: atlas/_static + atlas/config live beside this file.
_ATLAS_ROOTS = [_HERE, _HERE.parent]
_AICOM_ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent

_config_cache: dict[str, Any] | None = None
log = logging.getLogger("atlas.llm")
T = TypeVar("T")


def _retry_settings() -> tuple[int, float, float]:
    """Env wins (tests / ad-hoc tuning), else the ATLAS_* settings object.

    Reading the settings too keeps ``ATLAS_LLM_*`` values that arrive via
    ``.env`` (parsed by pydantic-settings, never exported to os.environ) from
    being silently ignored.
    """
    s = get_settings()
    max_retries = max(0, int(os.getenv("ATLAS_LLM_MAX_RETRIES", str(s.llm_max_retries))))
    base_ms = float(os.getenv("ATLAS_LLM_RETRY_BASE_MS", str(s.llm_retry_base_ms)))
    max_ms = float(os.getenv("ATLAS_LLM_RETRY_MAX_MS", str(s.llm_retry_max_ms)))
    return max_retries, base_ms, max_ms


def _is_retryable_http(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


async def with_llm_retry(fn: Callable[[], Awaitable[T]], *, label: str = "llm") -> T:
    """Exponential backoff + jitter on transient LLM HTTP failures."""
    max_retries, base_ms, max_ms = _retry_settings()
    last: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last = exc
            if attempt >= max_retries or not _is_retryable_http(exc):
                raise
            delay = min(base_ms * (2**attempt), max_ms) / 1000.0
            delay += random.uniform(0, delay * 0.25)
            log.warning(
                "llm retry attempt=%s label=%s err=%s delay=%.2fs",
                attempt + 1,
                label,
                type(exc).__name__,
                delay,
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last


def reset_config_cache() -> None:
    global _config_cache
    _config_cache = None


def _config_paths() -> list[Path]:
    custom = (
        os.getenv("ATLAS_LLM_CONFIG", "").strip()
        or os.getenv("ALIEN_LLM_CONFIG", "").strip()
    )
    paths: list[Path] = []
    if custom:
        paths.append(Path(custom))
    # Packaged example (wheel → atlas/_config/)
    paths.append(_HERE / "_config" / "model_providers.yaml")
    paths.append(_HERE / "_config" / "model_providers.example.yaml")
    paths.append(_AICOM_ROOT / "data" / "config" / "model_providers.yaml")
    paths.append(_AICOM_ROOT / "data" / "config" / "model_providers.example.yaml")
    for root in _ATLAS_ROOTS:
        paths.append(root / "config" / "model_providers.yaml")
        paths.append(root / "config" / "model_providers.example.yaml")
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            key = p.resolve()
        except Exception:
            key = p
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def builtin_config() -> dict[str, Any]:
    """Same provider ids as AI-Factory / Alien Monitor."""
    return {
        "default_provider": DEFAULT_PROVIDER,
        "providers": {
            "deepseek_api": {
                "api_key_env": "DEEPSEEK_API_KEY",
                "base_url": os.getenv("ATLAS_LLM_BASE_URL", "https://api.deepseek.com/v1"),
                "enabled": True,
                "models": {
                    "heavy": os.getenv("ATLAS_LLM_MODEL", DEFAULT_MODEL_HEAVY),
                    "light": os.getenv("ATLAS_LLM_MODEL_LIGHT", DEFAULT_MODEL_LIGHT),
                },
                "provider_type": "openai_compatible",
                "capabilities": {"max_tokens": 4096},
            },
            "anthropic_cloud": {
                "api_key_env": "ANTHROPIC_API_KEY",
                "base_url": "https://api.anthropic.com/v1",
                "enabled": True,
                "models": {
                    "heavy": "claude-3-5-sonnet-latest",
                    "light": "claude-3-5-haiku-latest",
                },
                "provider_type": "anthropic",
                "capabilities": {"max_tokens": 4096},
            },
            "groq_api": {
                "api_key_env": "GROQ_API_KEY",
                "base_url": "https://api.groq.com/openai/v1",
                "enabled": True,
                "models": {
                    "heavy": "llama3-70b-8192",
                    "light": "llama3-8b-8192",
                },
                "provider_type": "openai_compatible",
                "capabilities": {"max_tokens": 4096},
            },
            "together_ai": {
                "api_key_env": "TOGETHER_API_KEY",
                "base_url": "https://api.together.xyz/v1",
                "enabled": True,
                "models": {
                    "heavy": "meta-llama/Llama-3.1-70B-Instruct-Turbo",
                    "light": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                },
                "provider_type": "openai_compatible",
                "capabilities": {"max_tokens": 4096},
            },
            "lm_studio": {
                "api_key_env": None,
                "base_url": os.getenv("ATLAS_LM_STUDIO_URL", "http://host.docker.internal:1234/v1"),
                "enabled": True,
                "models": {
                    "heavy": os.getenv("ATLAS_LM_STUDIO_MODEL", "local-model"),
                    "light": os.getenv("ATLAS_LM_STUDIO_MODEL_LIGHT", "local-model"),
                },
                "provider_type": "openai_compatible",
                "capabilities": {"max_tokens": 4096},
            },
            "local_ollama": {
                "api_key_env": None,
                "base_url": os.getenv("ATLAS_OLLAMA_URL", "http://host.docker.internal:11434"),
                "enabled": True,
                "models": {
                    "heavy": os.getenv("ATLAS_OLLAMA_MODEL", "qwen2.5:14b"),
                    "light": os.getenv("ATLAS_OLLAMA_MODEL_LIGHT", "qwen2.5:7b"),
                },
                "provider_type": "local_ollama",
                "capabilities": {"max_tokens": 4096},
            },
        },
    }


def load_providers_config() -> dict[str, Any]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    for path in _config_paths():
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict) and loaded.get("providers"):
                # Merge builtin so Ollama/LM Studio/Anthropic always exist unless overridden.
                merged = builtin_config()
                merged_providers = dict(merged["providers"])
                for name, pconf in (loaded.get("providers") or {}).items():
                    if isinstance(pconf, dict):
                        base = dict(merged_providers.get(name) or {})
                        base.update(pconf)
                        merged_providers[name] = base
                merged["providers"] = merged_providers
                if os.getenv("ATLAS_LLM_PROVIDER"):
                    merged["default_provider"] = os.getenv("ATLAS_LLM_PROVIDER")
                else:
                    merged["default_provider"] = (
                        loaded.get("default_provider")
                        or merged.get("default_provider")
                        or DEFAULT_PROVIDER
                    )
                _config_cache = merged
                return _config_cache
    _config_cache = builtin_config()
    return _config_cache


def resolve_api_key(pconf: dict) -> str:
    if pconf.get("api_key"):
        return str(pconf["api_key"])
    env_name = pconf.get("api_key_env")
    if env_name:
        return os.environ.get(str(env_name), "")
    return ""


def local_llm_enabled() -> bool:
    """Keyless local backends (Ollama / LM Studio) count only when opted in.

    ``ATLAS_LOCAL_LLM_ENABLED=1`` next to a running Ollama / LM Studio. Off by
    default: claiming a localhost backend is "available" on a server that has
    none made ``any_provider_configured()`` always true, killed the documented
    offline cache stub, and left keyless deployments answering HTTP 500.
    """
    raw = os.getenv("ATLAS_LOCAL_LLM_ENABLED")
    if raw is not None:
        return raw.strip().lower() not in ("", "0", "false", "no", "off")
    return bool(get_settings().local_llm_enabled)


_LOCAL_HOST_MARKERS = (
    "localhost",
    "127.0.0.1",
    "[::1]",
    "0.0.0.0",
    "host.docker.internal",
    ".local",
    ".internal",
    "192.168.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.2",
    "172.30.",
    "172.31.",
)


def _is_local_provider(pconf: dict) -> bool:
    """Local = Ollama-style, or a keyless endpoint on a private/loopback host.

    Keylessness alone is not enough: a self-hosted OpenAI-compatible gateway on
    a public URL needs no key and must stay usable without the local opt-in.
    """
    ptype = pconf.get("provider_type", "openai_compatible")
    if ptype in ("local_ollama", "ollama"):
        return True
    if pconf.get("api_key_env") or pconf.get("api_key"):
        return False
    base = str(pconf.get("base_url") or "").lower()
    host = base.split("//", 1)[-1].split("/", 1)[0].split("@")[-1]
    return any(marker in host for marker in _LOCAL_HOST_MARKERS)


def provider_available(pconf: dict) -> bool:
    """Cloud needs a key; local backends need the explicit local opt-in."""
    if pconf.get("enabled") is False:
        return False
    if _is_local_provider(pconf):
        return local_llm_enabled()
    if pconf.get("api_key_env") or pconf.get("api_key"):
        return bool(resolve_api_key(pconf))
    # Keyless endpoint on a public host — an explicitly configured remote
    # gateway; usable as-is and not gated by the local opt-in.
    return True


def list_providers() -> dict[str, Any]:
    cfg = load_providers_config()
    default = cfg.get("default_provider") or DEFAULT_PROVIDER
    out: list[dict[str, Any]] = []
    for name, pconf in (cfg.get("providers") or {}).items():
        if not isinstance(pconf, dict) or pconf.get("enabled") is False:
            continue
        ptype = pconf.get("provider_type", "openai_compatible")
        models = pconf.get("models") or {}
        out.append(
            {
                "id": name,
                "provider_type": ptype,
                "base_url": pconf.get("base_url", ""),
                "models": {
                    "heavy": models.get("heavy", DEFAULT_MODEL_HEAVY),
                    "light": models.get("light", DEFAULT_MODEL_LIGHT),
                },
                "available": provider_available(pconf),
                "is_default": name == default,
            }
        )
    out.sort(key=lambda x: (not x["is_default"], x["id"]))
    return {
        "default_provider": default,
        "default_model": DEFAULT_MODEL_HEAVY,
        "providers": out,
    }


def any_provider_configured() -> bool:
    return any(p.get("available") for p in list_providers()["providers"])


async def _chat_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    question: str,
    max_tokens: int,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async def _once() -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": 0.25,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            return (message.get("content") or "").strip()

    return await with_llm_retry(_once, label=f"openai:{model}")


async def _chat_anthropic(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    question: str,
    max_tokens: int,
) -> str:
    if not api_key:
        raise RuntimeError("Anthropic: missing API key (set ANTHROPIC_API_KEY)")

    async def _once() -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": question}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            blocks = data.get("content") or []
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    return await with_llm_retry(_once, label=f"anthropic:{model}")


async def _chat_ollama(
    *,
    base_url: str,
    model: str,
    system_prompt: str,
    question: str,
    max_tokens: int,
) -> str:
    """Native Ollama /api/chat (factory-compatible). Falls back to OpenAI /v1 if base ends with /v1."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        return await _chat_openai_compatible(
            base_url=root,
            api_key="",
            model=model,
            system_prompt=system_prompt,
            question=question,
            max_tokens=max_tokens,
        )

    async def _once() -> str:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{root}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.25},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message") or {}
            return (msg.get("content") or data.get("response") or "").strip()

    return await with_llm_retry(_once, label=f"ollama:{model}")


async def generate_answer(
    *,
    question: str,
    locale: str,
    system_prompt: str,
    provider_id: str | None = None,
    model_role: str = "heavy",
) -> tuple[str, dict[str, Any]]:
    _ = locale
    cfg = load_providers_config()
    pid = provider_id or cfg.get("default_provider") or DEFAULT_PROVIDER
    providers = cfg.get("providers") or {}
    pconf = providers.get(pid)
    if not isinstance(pconf, dict):
        pid = DEFAULT_PROVIDER
        pconf = providers.get(pid) or builtin_config()["providers"][DEFAULT_PROVIDER]

    role = model_role if model_role in ("heavy", "light") else "heavy"
    models = pconf.get("models") or {}
    model = (
        os.getenv("ATLAS_LLM_MODEL")
        if role == "heavy" and os.getenv("ATLAS_LLM_MODEL")
        else None
    ) or models.get(role) or models.get("heavy") or DEFAULT_MODEL_HEAVY
    api_key = resolve_api_key(pconf)
    ptype = pconf.get("provider_type", "openai_compatible")
    base_url = (pconf.get("base_url") or "https://api.deepseek.com/v1").rstrip("/")
    max_tokens = int((pconf.get("capabilities") or {}).get("max_tokens") or 2048)
    max_tokens = min(max(max_tokens, 512), 8192)

    meta = {"provider": pid, "model": model, "model_role": role, "provider_type": ptype}

    if ptype in ("local_ollama", "ollama"):
        text = await _chat_ollama(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            question=question,
            max_tokens=max_tokens,
        )
        return text, meta

    if ptype == "anthropic":
        text = await _chat_anthropic(
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            question=question,
            max_tokens=max_tokens,
        )
        return text, meta

    # openai_compatible — DeepSeek, Groq, Together, LM Studio, …
    if pconf.get("api_key_env") and not api_key:
        raise RuntimeError(
            f"Provider {pid}: missing API key "
            f"(set {pconf.get('api_key_env') or 'API_KEY'})"
        )
    text = await _chat_openai_compatible(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        question=question,
        max_tokens=max_tokens,
    )
    return text, meta
