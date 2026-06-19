from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .audit import default_audit_path

SECRET_RE = re.compile(
    r"(?i)(bearer\s+|sk-|pk-|api[_-]?key|token|secret|seed\s*[:=]|password|[a-f0-9]{48,})"
)
SECRET_KEY_RE = re.compile(r"(?i)(seed|secret|token|api[_-]?key|password|mailbox[_-]?key)")


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "hermes_fetch_bridge"
    port: int = 8000
    network: str = "testnet"
    mode: Literal["endpoint", "mailbox", "proxy"] = "endpoint"
    publish_manifest: bool = False
    enable_agent_inspector: bool = False
    dev_random_seed: bool = False
    seed: str | None = None
    endpoint: str | None = None
    mailbox_key: str | None = None
    description: str = "Hermes Fetch AI bridge"


class HermesMCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["fake", "in_process_hermes_tools", "stdio", "sse", "http"] = "fake"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    timeout_seconds: float = 10.0


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_tools: list[str] = Field(default_factory=list)
    allowed_senders: dict[str, list[str]] = Field(default_factory=dict)
    denied_tools: list[str] = Field(default_factory=list)
    max_args_bytes: int = 65536
    max_output_bytes: int = 65536
    max_list_tools_response_bytes: int = 65536
    max_calls_per_minute_per_sender: int = 30
    max_list_tools_per_minute_per_sender: int = 30
    max_global_calls_per_minute: int = 300
    max_global_list_tools_per_minute: int = 300
    max_tracked_senders: int = 4096
    require_replay_metadata: bool = True
    replay_ttl_seconds: float = 300.0
    max_replay_entries: int = 8192
    max_replay_clock_skew_seconds: float = 60.0
    trusted_shell_tools: list[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redaction: bool = True
    audit_path: str | None = None


class ChatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enable_chat: bool = False

    @field_validator("enable_chat")
    @classmethod
    def no_chat(cls, v: bool) -> bool:
        if v:
            raise ValueError("chat is out of v1 scope")
        return v


class BridgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    agent: AgentConfig = Field(default_factory=AgentConfig)
    hermes_mcp: HermesMCPConfig = Field(default_factory=HermesMCPConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "BridgeConfig":
        if self.version != 1:
            raise ValueError("only config version 1 is supported")
        if self.hermes_mcp.mode == "stdio" and not self.hermes_mcp.command:
            raise ValueError("hermes_mcp.command is required for stdio mode")
        if self.agent.mode == "mailbox" and self.agent.dev_random_seed:
            raise ValueError("mailbox mode requires a stable UAGENT_SEED")
        if self.agent.seed:
            raise ValueError("agent.seed is not allowed in config; use UAGENT_SEED")
        if not self.agent.dev_random_seed:
            seed = os.environ.get("UAGENT_SEED")
            if not seed:
                raise ValueError("UAGENT_SEED is required when agent.dev_random_seed=false")
        return self

    def effective_seed(self) -> str:
        if self.agent.dev_random_seed:
            return "dev-ephemeral-" + secrets.token_urlsafe(32)
        return os.environ["UAGENT_SEED"]

    @property
    def audit_path(self) -> Path:
        return Path(self.logging.audit_path) if self.logging.audit_path else default_audit_path()


def _scan_secret_values(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (SECRET_RE.search(v) or SECRET_KEY_RE.search(str(k))):
                raise ValueError("secret-shaped YAML values are not allowed")
            _scan_secret_values(v)
    elif isinstance(obj, list):
        for v in obj:
            _scan_secret_values(v)


def load_config(path: str | Path) -> BridgeConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _scan_secret_values(data)
    return BridgeConfig.model_validate(data)


def validate_config_file(path: str | Path) -> tuple[bool, str]:
    try:
        load_config(path)
        return True, "ok"
    except (ValidationError, ValueError) as e:
        return False, str(e)
