"""Configuration loading: ``config.yaml`` + ``.env`` -> typed settings.

Secrets come from the environment (``.env``); everything else from
``config.yaml``. ``${VAR}`` references inside the YAML are expanded from the
environment so tokens never have to be written into the config file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is a core dep, but degrade gracefully
    def load_dotenv(*_a: Any, **_k: Any) -> bool:  # type: ignore
        return False


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


# --- Typed config models -----------------------------------------------------


class _Strict(BaseModel):
    """Base for all config models. Rejects unknown keys so a typo'd or misplaced
    block (e.g. an `openai:` block put in the wrong place) errors loudly instead
    of being silently ignored."""

    model_config = ConfigDict(extra="forbid")


class TelegramConfig(_Strict):
    token: str = ""
    allowed_users: str = ""  # comma-separated user IDs

    @property
    def allowed_user_ids_ordered(self) -> list[int]:
        """Allowed user IDs in the order listed in ``allowed_users`` (deduped).

        Order matters: the first id is the default recipient for proactive
        messages, so this must follow the config, not set-iteration order.
        """
        seen: dict[int, None] = {}
        for x in self.allowed_users.split(","):
            if x.strip().isdigit():
                seen.setdefault(int(x), None)
        return list(seen)

    @property
    def allowed_user_ids(self) -> set[int]:
        return set(self.allowed_user_ids_ordered)


class ChatConfig(_Strict):
    adapter: str = "console"
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class OllamaConfig(_Strict):
    host: str = "http://localhost:11434"
    model: str = "llama3.1"
    options: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(_Strict):
    backend: str = "ollama"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


class AgentConfig(_Strict):
    system_prompt: str = "You are RemoteToolbox, a helpful self-hosted assistant."
    history_limit: int = 20
    # Max tool-call -> result -> model rounds per user message before a forced
    # final answer. Backend-neutral (lives here, not on a specific LLM config).
    max_tool_rounds: int = 6


class MCPServerConfig(_Strict):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class ToolsConfig(_Strict):
    paths: list[str] = Field(default_factory=lambda: ["./tools"])
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    # Seconds before a single tool call is abandoned (0 = no limit). Stops one
    # hung tool from wedging a chat (and, since updates are sequential, all chats).
    call_timeout: float = 60.0


class LoggingConfig(_Strict):
    level: str = "INFO"


class Config(_Strict):
    chat: ChatConfig = Field(default_factory=ChatConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# --- Loading -----------------------------------------------------------------


def _expand_env(value: Any) -> Any:
    """Recursively expand ``${VAR}`` references using os.environ."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_config(
    config_path: str | os.PathLike[str] | None = None,
    env_path: str | os.PathLike[str] | None = None,
) -> Config:
    """Load .env into the environment, then parse config.yaml into a Config.

    Resolution order for the config file:
      1. ``config_path`` argument
      2. ``$RTB_CONFIG`` environment variable
      3. ``./config.yaml``
      4. built-in defaults (if no file exists at all)
    """
    load_dotenv(env_path or ".env")

    path = Path(config_path or os.environ.get("RTB_CONFIG", "config.yaml"))
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    else:
        raw = {}

    return Config.model_validate(_expand_env(raw))
