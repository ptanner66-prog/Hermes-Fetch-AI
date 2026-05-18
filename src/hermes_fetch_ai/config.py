from __future__ import annotations

import os
import re
import secrets
import unicodedata
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .audit import default_audit_path

SECRET_RE = re.compile(
    r"(?i)(bearer\s+|sk-|pk-|api[_-]?key|token|secret|seed\s*[:=]|password|"
    r"private[_-]?key|recovery[_-]?phrase|mnemonic|mailbox[_-]?key|auth|"
    r"credential|wallet|[a-f0-9]{48,})"
)
SECRET_ENV_NAME_RE = re.compile(
    r"(?i)(seed|secret|token|api[_-]?key|password|private[_-]?key|"
    r"recovery[_-]?phrase|mnemonic|mailbox[_-]?key|auth|credential|wallet)"
)
ENV_VAR_RE = re.compile(
    r"\$(?:{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))|"
    r"%(?P<win>[A-Za-z_][A-Za-z0-9_]*)%"
)
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}
SECRET_KEY_RE = re.compile(
    r"(?i)(seed|secret|token|api[_-]?key|password|private[_-]?key|"
    r"recovery[_-]?phrase|mnemonic|mailbox[_-]?key|auth|credential|wallet)"
)


def _validate_tool_name(name: str) -> str:
    raw = str(name)
    normalized = unicodedata.normalize("NFKC", raw)
    if raw != normalized:
        raise ValueError("unsafe tool name normalization")
    if any(ch in raw for ch in ZERO_WIDTH) or "\x1b" in raw:
        raise ValueError("unsafe tool name control character")
    if any(unicodedata.category(ch)[0] == "C" for ch in raw):
        raise ValueError("unsafe tool name control character")
    if not raw or not TOOL_NAME_RE.fullmatch(raw):
        raise ValueError("unsafe tool name")
    return raw


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

    @field_validator("seed", "mailbox_key")
    @classmethod
    def reject_inline_identity_secrets(cls, v: str | None) -> str | None:
        if v is not None:
            raise ValueError(
                "agent.seed and agent.mailbox_key are not supported in config; "
                "use process-local operator environment flow such as UAGENT_SEED"
            )
        return v


class HermesMCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fake", "in_process_hermes_tools", "stdio"] = "fake"
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
    trusted_shell_tools: list[str] = Field(default_factory=list)

    @field_validator("public_tools", "denied_tools", "trusted_shell_tools")
    @classmethod
    def validate_tool_list(cls, names: list[str]) -> list[str]:
        return [_validate_tool_name(name) for name in names]

    @field_validator("allowed_senders")
    @classmethod
    def validate_allowed_sender_tools(cls, mapping: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            str(sender): [_validate_tool_name(name) for name in names]
            for sender, names in mapping.items()
        }


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


class PaymentFundsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: str
    currency: str
    payment_method: str = "fet_direct"


class PricedToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted_funds: list[PaymentFundsConfig] = Field(default_factory=list)
    description: str | None = None


class PaymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["disabled", "dry_run", "testnet", "real_operator_approved"] = "disabled"
    accepted_funds: list[PaymentFundsConfig] = Field(default_factory=list)
    priced_tools: dict[str, PricedToolConfig] = Field(default_factory=dict)
    deadline_seconds: int = 300
    recipient: str | None = None
    allow_real_fet_movement: bool = False

    @field_validator("priced_tools")
    @classmethod
    def validate_priced_tool_names(
        cls, mapping: dict[str, PricedToolConfig]
    ) -> dict[str, PricedToolConfig]:
        return {_validate_tool_name(name): value for name, value in mapping.items()}

    @model_validator(mode="after")
    def validate_payment(self) -> "PaymentConfig":
        if self.deadline_seconds <= 0:
            raise ValueError("payment.deadline_seconds must be positive")
        if self.allow_real_fet_movement and self.mode != "real_operator_approved":
            raise ValueError(
                "real fund movement can only be considered in real_operator_approved mode"
            )
        if self.mode == "testnet":
            raise ValueError(
                "testnet payment mode is an operator stop; "
                "this proof implements disabled and dry_run payment modes only"
            )
        if self.mode == "real_operator_approved":
            raise ValueError(
                "real_operator_approved payment mode is an operator stop; "
                "this proof never moves real funds"
            )
        return self


class BridgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1

    agent: AgentConfig = Field(default_factory=AgentConfig)
    hermes_mcp: HermesMCPConfig = Field(default_factory=HermesMCPConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    payment: PaymentConfig = Field(default_factory=PaymentConfig)

    @model_validator(mode="after")
    def validate_cross_fields(self, info: ValidationInfo) -> "BridgeConfig":
        require_runtime_secrets = True
        if isinstance(info.context, dict):
            require_runtime_secrets = bool(info.context.get("require_runtime_secrets", True))
        if self.version != 1:
            raise ValueError("only config version 1 is supported")
        if self.hermes_mcp.mode == "stdio" and not self.hermes_mcp.command:
            raise ValueError("hermes_mcp.command is required for stdio mode")
        if self.agent.mode in {"mailbox", "proxy"} and self.agent.dev_random_seed:
            raise ValueError("mailbox/proxy modes require a stable UAGENT_SEED")
        if self.agent.seed or self.agent.mailbox_key:
            raise ValueError(
                "agent.seed and agent.mailbox_key are not supported in config; "
                "use process-local operator environment flow such as UAGENT_SEED"
            )
        if not self.agent.dev_random_seed and require_runtime_secrets:
            seed = os.environ.get("UAGENT_SEED")
            if not seed or not seed.strip():
                raise ValueError("UAGENT_SEED is required when agent.dev_random_seed=false")
        return self

    def effective_seed(self) -> str:
        if self.agent.dev_random_seed:
            return "dev-ephemeral-" + secrets.token_urlsafe(32)
        seed = os.environ.get("UAGENT_SEED")
        if not seed or not seed.strip():
            raise ValueError("UAGENT_SEED is required when agent.dev_random_seed=false")
        return seed

    @property
    def audit_path(self) -> Path:
        return Path(self.logging.audit_path) if self.logging.audit_path else default_audit_path()


def _scan_secret_values(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                value_has_secret = bool(SECRET_RE.search(v)) and not ENV_VAR_RE.search(v)
                key_is_secret = bool(SECRET_KEY_RE.search(str(k)))
                if value_has_secret or key_is_secret:
                    raise ValueError(
                        "secret-shaped YAML values are not allowed; "
                        "use environment flow for seed/token material"
                    )
            _scan_secret_values(v)
    elif isinstance(obj, list):
        for v in obj:
            _scan_secret_values(v)


def _expandvars_safely(value: str) -> str:
    matches = list(ENV_VAR_RE.finditer(value))
    for match in matches:
        var_name = next(group for group in match.groupdict().values() if group)
        if SECRET_ENV_NAME_RE.search(var_name):
            raise ValueError("secret-shaped environment variables may not be expanded into config")
        if var_name not in os.environ:
            raise ValueError(f"environment variable {var_name} referenced in config is not set")
    expanded = os.path.expandvars(value)
    if expanded != value and SECRET_RE.search(expanded):
        raise ValueError("secret-shaped environment expansion is not allowed")
    return expanded


def load_config(path: str | Path, *, require_runtime_secrets: bool = True) -> BridgeConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _scan_secret_values(data)
    hermes_mcp = data.get("hermes_mcp")
    if isinstance(hermes_mcp, dict):
        for key in ("command", "url"):
            if isinstance(hermes_mcp.get(key), str):
                hermes_mcp[key] = _expandvars_safely(hermes_mcp[key])
        if isinstance(hermes_mcp.get("args"), list):
            hermes_mcp["args"] = [
                _expandvars_safely(v) if isinstance(v, str) else v for v in hermes_mcp["args"]
            ]
    _scan_secret_values(data)
    return BridgeConfig.model_validate(
        data, context={"require_runtime_secrets": require_runtime_secrets}
    )


def validate_config_file(
    path: str | Path, *, require_runtime_secrets: bool = True
) -> tuple[bool, str]:
    try:
        load_config(path, require_runtime_secrets=require_runtime_secrets)
        return True, "ok"
    except (ValidationError, ValueError) as e:
        return False, str(e)
