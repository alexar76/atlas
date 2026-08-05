"""LLM provider registry + DeepSeek/OpenAI-compatible chat calls."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import yaml

DEFAULT_PROVIDER = "deepseek_api"
DEFAULT_MODEL_HEAVY = "deepseek-v4-pro"
DEFAULT_MODEL_LIGHT = "deepseek-v4-flash"

_HERE = Path(__file__).resolve().parent
_ATLAS_ROOTS = [_HERE.parents[1], _HERE.parents[2]]
_AICOM_ROOT = _HERE.parents[3] if len(_HERE.parents) > 3 else _HERE.parents[2]

_config_cache: dict[str, Any] | None = None


def _config_paths() -> list[Path]:
    custom = (
        os.getenv("ATLAS_LLM_CONFIG", "").strip()
        or os.getenv("ALIEN_LLM_CONFIG", "").strip()
    )
    paths: list[Path] = []
    if custom:
        paths.append(Path(custom))
    paths.append(_AICOM_ROOT / "data" / "config" / "model_providers.yaml")
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
    return {
        "default_provider": DEFAULT_PROVIDER,
        "providers": {
            DEFAULT_PROVIDER: {
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
                if not os.getenv("ATLAS_LLM_PROVIDER"):
                    loaded["default_provider"] = loaded.get("default_provider") or DEFAULT_PROVIDER
                else:
                    loaded["default_provider"] = os.getenv("ATLAS_LLM_PROVIDER")
                _config_cache = loaded
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


def list_providers() -> dict[str, Any]:
    cfg = load_providers_config()
    default = cfg.get("default_provider") or DEFAULT_PROVIDER
    out: list[dict[str, Any]] = []
    for name, pconf in (cfg.get("providers") or {}).items():
        if not isinstance(pconf, dict) or pconf.get("enabled") is False:
            continue
        ptype = pconf.get("provider_type", "openai_compatible")
        if ptype == "local_ollama":
            continue
        api_key = resolve_api_key(pconf)
        available = bool(api_key) if pconf.get("api_key_env") else True
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
                "available": available,
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
    max_tokens = min(max(max_tokens, 512), 4096)

    meta = {"provider": pid, "model": model, "model_role": role}

    if not api_key and ptype == "openai_compatible":
        raise RuntimeError(
            f"Provider {pid}: missing API key "
            f"(set {pconf.get('api_key_env') or 'DEEPSEEK_API_KEY'})"
        )

    if ptype == "anthropic":
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
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            return text.strip(), meta

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
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
        text = message.get("content") or ""
        return text.strip(), meta
