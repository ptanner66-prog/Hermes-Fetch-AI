from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ._redaction import SECRET_WORDS
from .audit import default_audit_path
from .tool_names import validate_tool_name

MIN_SEED_LENGTH = 32
# Set by the fetchai-bridge Hermes plugin (hermes-plugin/fetchai-bridge): the
# interpreter and import path Hermes itself runs on, used to start Hermes' tools
# MCP server when hermes_mcp.command is left unset.
HERMES_PYTHON_VAR = "HERMES_FETCH_AI_HERMES_PYTHON"
HERMES_PYTHONPATH_VAR = "HERMES_FETCH_AI_HERMES_PYTHONPATH"
SEED_HINT = 'generate one with: python -c "import secrets; print(secrets.token_hex(32))"'

_SECRET_WORDS = rf"(?:{SECRET_WORDS})"
# Credential formats and key=value assignments. Plain words such as "token" in a
# description are not flagged; values that look like actual secrets are.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b[sp]k-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(rf"(?i)\b{_SECRET_WORDS}\s*[:=]\s*\S"),
    re.compile(r"\b(?:0x)?[a-fA-F0-9]{48,}\b"),
)
# A command-line flag that introduces a secret, e.g. ["--api-key", "..."].
_SECRET_FLAG_RE = re.compile(rf"(?i)^--?{_SECRET_WORDS}$")
SECRET_KEY_RE = re.compile(rf"(?i){_SECRET_WORDS}")
_NON_SECRET_KEYS = frozenset({"dev_random_seed"})
_SECRET_MESSAGE = (
    "secret-shaped YAML values are not allowed; supply secrets through the environment "
    "(for example UAGENT_SEED)"
)


class ConfigError(ValueError):
    """A config file could not be read or parsed."""


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "hermes_fetch_bridge"
    port: int = Field(default=8000, ge=1, le=65535)
    network: Literal["testnet", "mainnet"] = "testnet"
    mode: Literal["endpoint", "mailbox", "proxy"] = "endpoint"
    publish_manifest: bool = False
    enable_agent_inspector: bool = False
    dev_random_seed: bool = False
    # Accepted only so that a seed in YAML gets a clear error; see validate_cross_fields.
    seed: str | None = None
    endpoint: str | None = None
    description: str = "Hermes Fetch AI bridge"


class HermesMCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["fake", "in_process_hermes_tools", "stdio"] = "fake"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=10.0, gt=0)


def _check_tool_names(names: list[str]) -> list[str]:
    for name in names:
        try:
            validate_tool_name(name)
        except ValueError:
            raise ValueError(
                f"{name!r} is not a valid tool name (letters, digits, '_', '.', '-'; "
                "at most 128 characters)"
            ) from None
    return names


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_tools: list[str] = Field(default_factory=list)
    allowed_senders: dict[str, list[str]] = Field(default_factory=dict)
    denied_tools: list[str] = Field(default_factory=list)
    max_args_bytes: int = Field(default=65536, gt=0)
    max_output_bytes: int = Field(default=65536, gt=0)
    max_list_tools_response_bytes: int = Field(default=65536, gt=0)
    # A rate limit of 0 blocks that request type entirely.
    max_calls_per_minute_per_sender: int = Field(default=30, ge=0)
    max_list_tools_per_minute_per_sender: int = Field(default=30, ge=0)
    max_global_calls_per_minute: int = Field(default=300, ge=0)
    max_global_list_tools_per_minute: int = Field(default=300, ge=0)
    max_tracked_senders: int = Field(default=4096, gt=0)
    require_replay_metadata: bool = True
    replay_ttl_seconds: float = Field(default=300.0, gt=0)
    max_replay_entries: int = Field(default=8192, gt=0)
    max_replay_clock_skew_seconds: float = Field(default=60.0, ge=0)
    trusted_shell_tools: list[str] = Field(default_factory=list)

    @field_validator("public_tools", "denied_tools", "trusted_shell_tools")
    @classmethod
    def _tool_names(cls, names: list[str]) -> list[str]:
        return _check_tool_names(names)

    @field_validator("allowed_senders")
    @classmethod
    def _sender_tool_names(cls, senders: dict[str, list[str]]) -> dict[str, list[str]]:
        for names in senders.values():
            _check_tool_names(names)
        return senders


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    def validate_cross_fields(self) -> BridgeConfig:
        if self.version != 1:
            raise ValueError("only config version 1 is supported")
        if (
            self.hermes_mcp.mode == "stdio"
            and not self.hermes_mcp.command
            and not os.environ.get(HERMES_PYTHON_VAR)
        ):
            raise ValueError(
                "hermes_mcp.command is required for stdio mode unless the bridge runs "
                "through `hermes fetchai-bridge`, which supplies Hermes' own interpreter"
            )
        if self.agent.mode == "mailbox" and self.agent.dev_random_seed:
            raise ValueError("mailbox mode requires a stable UAGENT_SEED")
        if self.agent.seed:
            raise ValueError("agent.seed is not allowed in config; use UAGENT_SEED")
        if not self.agent.dev_random_seed:
            runtime_identity = os.environ.get("UAGENT_SEED")
            if not runtime_identity:
                raise ValueError("UAGENT_SEED is required when agent.dev_random_seed=false")
            # The agent's signing key is derived from this value, so a short seed
            # is a guessable private key.
            if len(runtime_identity) < MIN_SEED_LENGTH:
                raise ValueError(
                    f"UAGENT_SEED must be at least {MIN_SEED_LENGTH} characters; {SEED_HINT}"
                )
        return self

    def effective_seed(self) -> str:
        if self.agent.dev_random_seed:
            return "dev-ephemeral-" + secrets.token_urlsafe(32)
        return os.environ["UAGENT_SEED"]

    def ignored_seed_warning(self) -> str | None:
        """Explain when a configured UAGENT_SEED will not be used."""
        if self.agent.dev_random_seed and os.environ.get("UAGENT_SEED"):
            return (
                "UAGENT_SEED is set but agent.dev_random_seed is true, so it is ignored and the "
                "bridge gets a new random address on every start; set "
                "agent.dev_random_seed: false to use UAGENT_SEED"
            )
        return None

    @property
    def audit_path(self) -> Path:
        return Path(self.logging.audit_path) if self.logging.audit_path else default_audit_path()


def _looks_like_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _scan_secret_values(
    obj: object, *, under_secret_key: bool = False, keys_are_addresses: bool = False
) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            if _looks_like_secret(key):
                raise ValueError(_SECRET_MESSAGE)
            # Agent addresses (keys of policy.allowed_senders) are random strings
            # that can contain a word such as "seed", so the key-name check skips them.
            secret_key = (
                not keys_are_addresses
                and key not in _NON_SECRET_KEYS
                and bool(SECRET_KEY_RE.search(key))
            )
            _scan_secret_values(
                v, under_secret_key=secret_key, keys_are_addresses=key == "allowed_senders"
            )
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, str) and _SECRET_FLAG_RE.match(v.strip()):
                raise ValueError(_SECRET_MESSAGE)
            _scan_secret_values(v, under_secret_key=under_secret_key)
    elif isinstance(obj, str) and ((under_secret_key and obj) or _looks_like_secret(obj)):
        raise ValueError(_SECRET_MESSAGE)


def _yaml_problem(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None)
    mark = getattr(exc, "problem_mark", None)
    where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark is not None else ""
    return f"{where}: {problem}" if problem else where


def load_config(path: str | Path) -> BridgeConfig:
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except OSError as exc:
        raise ConfigError(f"cannot read {config_path}: {exc.strerror or exc}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {config_path}{_yaml_problem(exc)}") from None
    _scan_secret_values(data)
    return BridgeConfig.model_validate(data)


def format_validation_error(exc: ValidationError) -> str:
    """Summarize a pydantic error without echoing the submitted values."""
    parts = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "invalid value")).removeprefix("Value error, ")
        parts.append(f"{location}: {message}" if location else message)
    return "; ".join(parts)


def validate_config_file(path: str | Path) -> tuple[bool, str]:
    try:
        load_config(path)
    except ValidationError as e:
        return False, format_validation_error(e)
    except ValueError as e:
        return False, str(e)
    return True, "ok"
