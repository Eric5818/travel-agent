from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOTENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_WEATHER_BASE_URL = "https://wttr.in"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str = field(repr=False)
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    tavily_api_key: str | None = field(default=None, repr=False)
    weather_base_url: str = DEFAULT_WEATHER_BASE_URL

    @property
    def tavily_configured(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def degraded(self) -> bool:
        return not self.tavily_configured


def load(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv(DEFAULT_DOTENV_PATH)
        env = os.environ

    deepseek_api_key = _clean(env.get("DEEPSEEK_API_KEY"))
    if deepseek_api_key is None:
        raise ConfigError(
            "DEEPSEEK_API_KEY 未配置：请在 .env 中设置 DEEPSEEK_API_KEY"
        )

    return Settings(
        deepseek_api_key=deepseek_api_key,
        deepseek_base_url=(
            _clean(env.get("DEEPSEEK_BASE_URL")) or DEFAULT_DEEPSEEK_BASE_URL
        ),
        deepseek_model=_clean(env.get("DEEPSEEK_MODEL")) or DEFAULT_DEEPSEEK_MODEL,
        tavily_api_key=_clean(env.get("TAVILY_API_KEY")),
        weather_base_url=(
            _clean(env.get("WEATHER_BASE_URL")) or DEFAULT_WEATHER_BASE_URL
        ),
    )
