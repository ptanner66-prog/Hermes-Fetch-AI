from __future__ import annotations

import ipaddress
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import bech32
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ._redaction import SECRET_WORDS
from .audit import default_audit_path, default_state_dir
from .money import MAX_PRICE_BASE, format_fet, parse_fet
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
    # With publish_manifest, also register on the Almanac contract, which can
    # spend from the agent's wallet. Off: register through the Almanac API only.
    ledger_registration: bool = False
    enable_agent_inspector: bool = False
    dev_random_seed: bool = False
    # Accepted only so that a seed in YAML gets a clear error; see validate_cross_fields.
    seed: str | None = None
    endpoint: str | None = None
    description: str = "Hermes Fetch AI bridge"
    # The agent's handle on Agentverse; ASI:One users can write @handle to reach it.
    handle: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{2,19}$")


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


DEFAULT_LEDGER_URL = "https://rest-dorado.fetch.ai"
_SERVICE_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
_ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")


def is_fetch_address(value: str) -> bool:
    """True for a well-formed ``fetch1...`` wallet address."""
    hrp, data = bech32.bech32_decode(value)
    if hrp != "fetch" or data is None:
        return False
    decoded = bech32.convertbits(data, 5, 8, False)
    return decoded is not None and len(decoded) == 20


def is_agent_address(value: str) -> bool:
    """True for a well-formed ``agent1...`` agent address."""
    hrp, data = bech32.bech32_decode(value)
    if hrp != "agent" or data is None:
        return False
    decoded = bech32.convertbits(data, 5, 8, False)
    return decoded is not None and len(decoded) == 33


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class PaymentsConfig(BaseModel):
    """How the bridge is paid. Fetch's testnet only: test FET has no value."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    network: str = "testnet"
    chain_id: Literal["dorado-1"] = "dorado-1"
    denom: Literal["atestfet"] = "atestfet"
    ledger_url: str = DEFAULT_LEDGER_URL
    ledger_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    # Where buyers pay. Unset means the agent's own wallet (from UAGENT_SEED).
    payout_address: str | None = None
    state_dir: str | None = None
    quote_ttl_seconds: int = Field(default=600, ge=60, le=86_400)
    redeem_window_seconds: int = Field(default=86_400, ge=600, le=30 * 86_400)
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_verifications_per_minute_per_sender: int = Field(default=6, ge=1)
    max_global_verifications_per_minute: int = Field(default=60, ge=1)

    @field_validator("network")
    @classmethod
    def _testnet_only(cls, value: str) -> str:
        if value != "testnet":
            raise ValueError(
                "payments run on Fetch's testnet only; mainnet is locked until a security review"
            )
        return value

    @field_validator("ledger_url")
    @classmethod
    def _ledger_url(cls, value: str) -> str:
        parts = urlsplit(value)
        host = parts.hostname or ""
        secure = parts.scheme == "https" or (parts.scheme == "http" and _is_loopback_host(host))
        if not secure or not host or parts.username or parts.password or parts.query:
            raise ValueError(
                "ledger_url must be an https:// address (http:// only on this machine), "
                "without credentials or a query"
            )
        return value.rstrip("/")

    @field_validator("payout_address")
    @classmethod
    def _payout_address(cls, value: str | None) -> str | None:
        if value is not None and not is_fetch_address(value):
            raise ValueError("payout_address must be a fetch1... wallet address")
        return value

    @property
    def state_path(self) -> Path:
        return Path(self.state_dir).expanduser() if self.state_dir else default_state_dir()


class BuyingConfig(BaseModel):
    """Buying from other agents, for testnet FET, always with the owner's approval.

    The limits are enforced by the bridge, whatever Hermes asks for.
    """

    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    # Most a single payment may be, in testnet FET.
    max_payment: str = "1"
    # Most spent in any 24 hours, across all sellers and for one seller.
    max_per_day: str = "5"
    max_per_seller_per_day: str = "2"
    # Agent addresses (agent1...) Hermes may pay; empty means any agent.
    allowed_sellers: list[str] = Field(default_factory=list)
    # How long a message waits for the other agent's reply before returning.
    reply_wait_seconds: float = Field(default=60.0, gt=0, le=600)
    max_message_chars: int = Field(default=4000, ge=1, le=50_000)

    @field_validator("max_payment", "max_per_day", "max_per_seller_per_day")
    @classmethod
    def _amount(cls, value: str) -> str:
        amount = parse_fet(value)
        if amount <= 0:
            raise ValueError("must be more than 0")
        if amount > MAX_PRICE_BASE:
            raise ValueError(f"must be at most {format_fet(MAX_PRICE_BASE)} FET")
        return value

    @field_validator("allowed_sellers")
    @classmethod
    def _sellers(cls, sellers: list[str]) -> list[str]:
        for seller in sellers:
            if not is_agent_address(seller):
                raise ValueError(f"{seller!r} is not an agent address (agent1...)")
        return sellers

    @model_validator(mode="after")
    def _limits_agree(self) -> BuyingConfig:
        payment, day, seller = (
            parse_fet(self.max_payment),
            parse_fet(self.max_per_day),
            parse_fet(self.max_per_seller_per_day),
        )
        if payment > day or seller > day:
            raise ValueError(
                "max_payment and max_per_seller_per_day must not be more than max_per_day"
            )
        return self

    @property
    def max_payment_base(self) -> int:
        return parse_fet(self.max_payment)

    @property
    def max_per_day_base(self) -> int:
        return parse_fet(self.max_per_day)

    @property
    def max_per_seller_per_day_base(self) -> int:
        return parse_fet(self.max_per_seller_per_day)


class ServiceInputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_chars: int = Field(default=4000, ge=1, le=200_000)
    # Turn off for services whose requests are code or text that merely mention
    # local addresses (a code review, for example) and that never fetch URLs.
    check_urls: bool = True


class EchoRunnerConfig(BaseModel):
    """Answers with the request itself; for demos and tests."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["echo"] = "echo"


class CommandRunnerConfig(BaseModel):
    """Runs a program on this machine: the request as JSON on stdin, the answer on stdout."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["command"]
    argv: list[str] = Field(min_length=1)
    timeout_seconds: float = Field(default=300.0, gt=0, le=3600)
    max_output_chars: int = Field(default=20_000, ge=1, le=1_000_000)
    # Names of environment variables the program may see (values are never in config).
    pass_env: list[str] = Field(default_factory=list)

    @field_validator("argv")
    @classmethod
    def _absolute_program(cls, argv: list[str]) -> list[str]:
        if not Path(argv[0]).is_absolute():
            found = shutil.which(argv[0])
            hint = f", such as {found}" if found else ""
            raise ValueError(f"the program (argv[0]) must be an absolute path{hint}")
        if any("\x00" in arg for arg in argv):
            raise ValueError("arguments must not contain NUL characters")
        return argv

    @field_validator("pass_env")
    @classmethod
    def _env_names(cls, names: list[str]) -> list[str]:
        for name in names:
            if not _ENV_NAME_RE.fullmatch(name):
                raise ValueError(f"{name!r} is not an environment variable name")
        return names


# Toolsets a guest Hermes may have. Each reaches only the public internet,
# never this machine's files, terminal, memory, or the owner's accounts.
GUEST_TOOLSETS = ("web",)


class HermesRunnerConfig(BaseModel):
    """Answers with a guest Hermes: a separate Hermes run with its own home folder.

    The guest gets the buyer's request, the owner's instructions, and only the
    toolsets listed here; with none, it can only think and write.
    """

    model_config = ConfigDict(extra="forbid")
    type: Literal["hermes"]
    # A .env file with the keys the guest needs: its model key, and a web search
    # key if you have one. Unset: guests/<service>.env in the bridge's state folder.
    env_file: str | None = Field(default=None, min_length=1)
    toolsets: list[str] = Field(default_factory=list)
    # The model, as Hermes names it with `hermes chat -m`.
    model: str = Field(min_length=1, max_length=200)
    # Hermes' inference provider, such as "openrouter", or "custom" with base_url
    # for a model server like Ollama; unset: Hermes picks one from the keys it has.
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    # The model server's address, for provider "custom", e.g. http://127.0.0.1:11434/v1.
    base_url: str | None = None
    # What the guest is told about the job; the buyer's request follows it.
    instructions: str = Field(default="", max_length=8000)
    max_turns: int = Field(default=8, ge=1, le=50)
    timeout_seconds: float = Field(default=300.0, gt=0, le=3600)
    max_output_chars: int = Field(default=20_000, ge=1, le=1_000_000)
    # Hermes' Python. Unset: the one the fetchai-bridge plugin hands over.
    python: str | None = None
    # Names of environment variables the guest may see, such as HTTPS_PROXY on
    # a network that needs a proxy. Keys belong in env_file instead.
    pass_env: list[str] = Field(default_factory=list)

    @field_validator("env_file")
    @classmethod
    def _absolute_env_file(cls, env_file: str | None) -> str | None:
        if env_file is not None and not Path(env_file).expanduser().is_absolute():
            raise ValueError("env_file must be an absolute path (or start with ~)")
        return env_file

    @field_validator("pass_env")
    @classmethod
    def _guest_env_names(cls, names: list[str]) -> list[str]:
        for name in names:
            if not _ENV_NAME_RE.fullmatch(name):
                raise ValueError(f"{name!r} is not an environment variable name")
            if name.upper().startswith("HERMES_"):
                raise ValueError(f"{name} would change how the guest Hermes behaves")
        return names

    @field_validator("python")
    @classmethod
    def _absolute_python(cls, python: str | None) -> str | None:
        if python is not None and not Path(python).is_absolute():
            found = shutil.which(python)
            hint = f", such as {found}" if found else ""
            raise ValueError(f"python must be an absolute path{hint}")
        return python

    @field_validator("base_url")
    @classmethod
    def _model_url(cls, url: str | None) -> str | None:
        if url is None:
            return None
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("base_url must be an http:// or https:// address")
        if parts.username or parts.password:
            raise ValueError("base_url must not contain a user name or password")
        return url

    @field_validator("toolsets")
    @classmethod
    def _guest_toolsets(cls, toolsets: list[str]) -> list[str]:
        for toolset in toolsets:
            if toolset not in GUEST_TOOLSETS:
                raise ValueError(
                    f"a guest Hermes may use only these toolsets: {', '.join(GUEST_TOOLSETS)} "
                    f"(not {toolset!r}); buyers must never reach this machine's terminal, "
                    "files, browser, or memory"
                )
        return list(dict.fromkeys(toolsets))

    @field_validator("model", "provider")
    @classmethod
    def _plain_name(cls, value: str | None) -> str | None:
        # Model and provider names have no spaces; a leading '-' is an option typed by mistake.
        if value is not None and (value.startswith("-") or any(c.isspace() for c in value)):
            raise ValueError("must not start with '-' or contain spaces")
        return value

    @model_validator(mode="after")
    def _custom_needs_url(self) -> HermesRunnerConfig:
        if self.provider == "custom" and not self.base_url:
            raise ValueError(
                "provider custom needs base_url, the model server's address, "
                "such as http://127.0.0.1:11434/v1"
            )
        return self


RunnerConfig = Annotated[
    EchoRunnerConfig | CommandRunnerConfig | HermesRunnerConfig, Field(discriminator="type")
]


class ServiceConfig(BaseModel):
    """A service this agent sells, offered to other agents as the tool ``service.<name>``."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    # Testnet FET per request, as a string ("0.05"); "0" is free.
    price: str = "0"
    input: ServiceInputConfig = Field(default_factory=ServiceInputConfig)
    runner: RunnerConfig
    # Appended to every answer, e.g. "A first draft for review by a professional."
    disclaimer: str | None = Field(default=None, max_length=500)
    max_runs_per_day: int = Field(default=200, ge=1, le=100_000)
    # Runs at once, and requests that may wait for one; beyond that, callers
    # are told the service is busy before they pay.
    max_running: int = Field(default=1, ge=1, le=32)
    max_waiting: int = Field(default=4, ge=0, le=1000)

    @field_validator("price")
    @classmethod
    def _price(cls, value: str) -> str:
        if parse_fet(value) > MAX_PRICE_BASE:
            raise ValueError(f"price must be at most {format_fet(MAX_PRICE_BASE)} FET")
        return value

    @property
    def price_base(self) -> int:
        return parse_fet(self.price)


class ChatConfig(BaseModel):
    """Fetch's chat protocol, for selling services to ASI:One users in plain language."""

    model_config = ConfigDict(extra="forbid")
    enable_chat: bool = False


class BridgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    agent: AgentConfig = Field(default_factory=AgentConfig)
    hermes_mcp: HermesMCPConfig = Field(default_factory=HermesMCPConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    services: dict[str, ServiceConfig] = Field(default_factory=dict)
    buying: BuyingConfig = Field(default_factory=BuyingConfig)

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
        for name in self.services:
            if not _SERVICE_NAME_RE.fullmatch(name):
                raise ValueError(
                    f"service name {name!r}: use lowercase letters, digits, '_' and '-' "
                    "(at most 40 characters)"
                )
        if self.services and not self.payments.enabled:
            raise ValueError("services need payments.enabled: true")
        if self.chat.enable_chat and not self.services:
            raise ValueError(
                "chat sells the services under `services`; define at least one "
                "(and set payments.enabled: true)"
            )
        if self.payments.enabled and self.agent.network != "testnet":
            raise ValueError("payments run on Fetch's testnet only; set agent.network: testnet")
        if self.buying.enabled and self.agent.network != "testnet":
            raise ValueError("buying runs on Fetch's testnet only; set agent.network: testnet")
        if self.buying.enabled and self.agent.dev_random_seed:
            raise ValueError(
                "buying pays from a wallet that comes from UAGENT_SEED; set "
                "agent.dev_random_seed: false and a stable UAGENT_SEED"
            )
        if (
            self.payments.enabled
            and self.agent.dev_random_seed
            and not self.payments.payout_address
        ):
            raise ValueError(
                "with agent.dev_random_seed: true the agent's wallet changes on every start; "
                "set payments.payout_address or use a stable UAGENT_SEED"
            )
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
        if self.logging.audit_path:
            return Path(self.logging.audit_path).expanduser()
        return default_audit_path()


def _looks_like_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


# Sections keyed by names chosen elsewhere: agent addresses (random strings that
# can contain a word such as "seed") and service names.
_NAME_KEYED_SECTIONS = frozenset({"allowed_senders", "services"})


def _scan_secret_values(
    obj: object, *, under_secret_key: bool = False, keys_are_names: bool = False
) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            if _looks_like_secret(key):
                raise ValueError(_SECRET_MESSAGE)
            secret_key = (
                not keys_are_names
                and key not in _NON_SECRET_KEYS
                and bool(SECRET_KEY_RE.search(key))
            )
            _scan_secret_values(
                v, under_secret_key=secret_key, keys_are_names=key in _NAME_KEYED_SECTIONS
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
