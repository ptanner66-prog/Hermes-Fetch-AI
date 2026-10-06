"""``hermes-fetch-ai setup``: a plain-language wizard that writes the bridge's config.

Run it through Hermes (``hermes fetchai-bridge setup``), which first creates
the agent's secret key (``UAGENT_SEED``) in Hermes' ``.env`` and asks for an
Agentverse API key. The wizard asks what the agent should do, in plain words,
and writes the answers to the managed config (``audit.managed_config_path``).
Running it again offers the current answers as defaults, so it is also how to
change them; settings it does not ask about are kept.
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TextIO

import yaml
from pydantic import ValidationError

from .audit import default_state_dir, managed_config_path
from .config import (
    _SERVICE_NAME_RE,
    MIN_SEED_LENGTH,
    BridgeConfig,
    format_validation_error,
)
from .local_review import on_this_machine
from .money import MAX_PRICE_BASE, format_fet, parse_fet
from .wallet import BUYING_WALLET_INDEX, agent_address, wallet_address

HEADER = (
    "# Your Hermes Fetch AI agent, written by `hermes fetchai-bridge setup`.\n"
    "# Run setup again to change it; it keeps settings you add by hand.\n"
)
DEFAULT_PORT = 8000
HANDLE_HINT = "3 to 20 lowercase letters, digits, or -, starting with a letter or digit"
# Set by the fetchai-bridge plugin: where to tell it what was chosen.
RESULT_VAR = "HERMES_FETCH_AI_SETUP_RESULT"

RESEARCH = "research"
REVIEW = "security-review"
# Hermes' provider name: its name, how to describe the choice, its key's name in .env,
# and a model to suggest.
PROVIDERS: dict[str, tuple[str, str, str | None, str]] = {
    "openrouter": (
        "OpenRouter",
        "OpenRouter: one key for many models (openrouter.ai)",
        "OPENROUTER_API_KEY",
        "anthropic/claude-sonnet-4.6",
    ),
    "anthropic": (
        "Anthropic",
        "Anthropic (console.anthropic.com)",
        "ANTHROPIC_API_KEY",
        "claude-sonnet-4-6",
    ),
    "custom": (
        "your model server",
        "A model server on this computer (Ollama, LM Studio)",
        None,
        "qwen2.5:7b",
    ),
}
LOCAL_MODEL_URL = "http://127.0.0.1:11434/v1"  # Ollama's default
# Buyers pay in free test FET, but each research request uses the owner's model account.
RESEARCH_RUNS_PER_DAY = 20
REVIEW_MODEL = "qwen2.5-coder:7b"

RESEARCH_SERVICE: dict[str, Any] = {
    "title": "Research a topic",
    "description": (
        "Ask a question and get a short answer with its sources. A Hermes agent searches "
        "the public web for you; it cannot reach the seller's computer, files, or accounts."
    ),
    "disclaimer": (
        "Researched by an AI agent from public web pages. Check the sources before you rely on it."
    ),
    "example": "What causes the large tides in the Bay of Fundy?",
}
RESEARCH_INSTRUCTIONS = (
    "Research the client's question with web search, then answer in a few short paragraphs, "
    "followed by the sources you used (title and URL). Say where sources disagree and what "
    "you could not find."
)
REVIEW_SERVICE: dict[str, Any] = {
    "title": "Defensive code security review",
    "description": (
        "Send source code and get its security problems explained, with fixes. An AI model "
        "on the seller's machine reads only the code you send; nothing is scanned, "
        "contacted, or attacked."
    ),
    "disclaimer": (
        "Automated review by an AI model. It can miss problems and is not a penetration "
        "test or a security guarantee."
    ),
    "example": 'def find(name): return db.execute("SELECT * FROM users WHERE name = \'" + name + "\'")',
}


class SetupError(Exception):
    """An answer the wizard cannot use; the message says why, for the owner."""


class Asker(Protocol):
    """How the wizard talks to the owner. ``key`` names each question, for scripted answers."""

    def say(self, text: str = "") -> None: ...

    def ask(
        self, key: str, question: str, default: str = "", check: Callable[[str], str] | None = None
    ) -> str: ...

    def yes(self, key: str, question: str, default: bool) -> bool: ...

    def secret(self, key: str, question: str) -> str: ...

    def choose(self, key: str, question: str, options: Mapping[str, str], default: str) -> str: ...


class ConsoleAsker:
    """Asks at the terminal; Enter takes the suggested answer, and a bad answer is asked again."""

    def __init__(
        self,
        read: Callable[[str], str] = input,
        read_secret: Callable[[str], str] = getpass.getpass,
        out: TextIO | None = None,
    ) -> None:
        self._read = read
        self._read_secret = read_secret
        self._out = out or sys.stdout

    def say(self, text: str = "") -> None:
        print(text, file=self._out)

    def ask(
        self, key: str, question: str, default: str = "", check: Callable[[str], str] | None = None
    ) -> str:
        suffix = f" [{default}]" if default else ""
        while True:
            answer = self._read(f"{question}{suffix}: ").strip() or default
            if check is None:
                return answer
            try:
                return check(answer)
            except SetupError as exc:
                self.say(f"  {exc}")

    def yes(self, key: str, question: str, default: bool) -> bool:
        hint = "Y/n" if default else "y/N"
        while True:
            answer = self._read(f"{question} [{hint}]: ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.say("  Please answer y or n.")

    def secret(self, key: str, question: str) -> str:
        return self._read_secret(f"{question} (hidden as you type): ").strip()

    def choose(self, key: str, question: str, options: Mapping[str, str], default: str) -> str:
        names = list(options)
        self.say(question)
        for number, name in enumerate(names, start=1):
            mark = " (suggested)" if name == default else ""
            self.say(f"  {number}. {options[name]}{mark}")
        while True:
            answer = self._read(f"Choose 1-{len(names)} [{names.index(default) + 1}]: ").strip()
            if not answer:
                return default
            if answer.isdigit() and 1 <= int(answer) <= len(names):
                return names[int(answer) - 1]
            self.say(f"  Please choose a number from 1 to {len(names)}.")


class ScriptedAsker:
    """Answers from a mapping of question keys (for tests and `setup --answers`).

    A question without an answer takes its default; a list answers a question
    that comes up more than once, in order; an answer the wizard cannot use
    raises SetupError instead of being asked again.
    """

    def __init__(self, answers: Mapping[str, Any], *, echo: TextIO | None = None) -> None:
        self.answers = dict(answers)
        self.said: list[str] = []
        self.asked: list[str] = []
        self._echo = echo

    def say(self, text: str = "") -> None:
        self.said.append(text)
        if self._echo is not None:
            print(text, file=self._echo)

    def _get(self, key: str, default: Any) -> Any:
        self.asked.append(key)
        answer = self.answers.get(key, default)
        if isinstance(answer, list):  # one answer each time the question comes up
            return answer.pop(0) if answer else default
        return answer

    def ask(
        self, key: str, question: str, default: str = "", check: Callable[[str], str] | None = None
    ) -> str:
        answer = str(self._get(key, default)).strip()
        return check(answer) if check is not None else answer

    def yes(self, key: str, question: str, default: bool) -> bool:
        return bool(self._get(key, default))

    def secret(self, key: str, question: str) -> str:
        return str(self._get(key, "")).strip()

    def choose(self, key: str, question: str, options: Mapping[str, str], default: str) -> str:
        answer = str(self._get(key, default))
        if answer not in options:
            raise SetupError(f"{key}: choose one of {', '.join(options)}")
        return answer


# -- checks for answers ------------------------------------------------------------------


def check_price(text: str) -> str:
    try:
        amount = parse_fet(text)
    except ValueError:
        raise SetupError("Give a price in FET, like 0.05.") from None
    if not 0 < amount <= MAX_PRICE_BASE:
        raise SetupError(f"Give a price above 0 and at most {format_fet(MAX_PRICE_BASE)} FET.")
    return format_fet(amount)


def check_handle(text: str) -> str:
    handle = text.strip().removeprefix("@").lower()
    if not handle:
        return ""
    if not (3 <= len(handle) <= 20 and handle[0].isalnum()) or any(
        not (c.isalnum() and c.isascii()) and c != "-" for c in handle
    ):
        raise SetupError(f"A handle is {HANDLE_HINT}.")
    return handle


def check_service_name(text: str) -> str:
    name = text.strip().lower()
    if not _SERVICE_NAME_RE.fullmatch(name):
        raise SetupError("Use lowercase letters, digits, - and _ (at most 40), like legal-draft.")
    if name in (RESEARCH, REVIEW):
        raise SetupError(f"{name} is taken by a built-in service; pick another name.")
    return name


def check_local_url(text: str) -> str:
    if not on_this_machine(text):
        raise SetupError(
            "The model server must be on this computer, like http://127.0.0.1:11434/v1."
        )
    return text.rstrip("/")


def check_program(text: str) -> str:
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise SetupError("Give the full path, starting with / (or C:\\ on Windows).")
    if not path.is_file():
        raise SetupError(f"There is no file at {path}.")
    if path.suffix != ".py" and not os.access(path, os.X_OK):
        raise SetupError(f"{path} is not executable; make it so (chmod +x) and try again.")
    return str(path)


def check_runs_per_day(text: str) -> str:
    try:
        runs = int(text)
    except ValueError:
        raise SetupError("Give a whole number, like 20.") from None
    if not 1 <= runs <= 100_000:
        raise SetupError("Give a number from 1 to 100000.")
    return str(runs)


def check_seconds(text: str) -> str:
    try:
        seconds = float(text)
    except ValueError:
        raise SetupError("Give a number of seconds, like 300.") from None
    if not 0 < seconds <= 3600:
        raise SetupError("Give a number of seconds from 1 to 3600.")
    return text


def check_text(limit: int) -> Callable[[str], str]:
    def check(text: str) -> str:
        if not text.strip():
            raise SetupError("This cannot be empty.")
        if len(text) > limit:
            raise SetupError(f"Keep it under {limit} characters.")
        return text.strip()

    return check


def check_optional_text(limit: int) -> Callable[[str], str]:
    def check(text: str) -> str:
        if len(text) > limit:
            raise SetupError(f"Keep it under {limit} characters.")
        return text.strip()

    return check


def agent_name(text: str) -> str:
    """The name, as uAgents and Agentverse take it: lowercase words joined by '_'."""
    words = "".join(c if c.isascii() and c.isalnum() else " " for c in text.lower()).split()
    name = "_".join(words)[:40]
    if not name:
        raise SetupError("Give your agent a name with letters or digits.")
    return name


# -- helpers with side effects (replaceable in tests) ------------------------------------


def port_is_free(port: int) -> bool:
    """True if the agent could listen on ``port`` (on every interface, as it does) with
    nothing else answering there."""
    # macOS and Windows let a program listen on every interface while another listens on
    # 127.0.0.1, which then gets this computer's own connections: so try that address too.
    for host in ("", "127.0.0.1"):
        with socket.socket() as s:
            if os.name != "nt":  # as the agent's server does: a port just let go of is free
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except OSError:
                return False
    return True


def probe_model_server(url: str) -> str | None:
    """None if the model server on this computer answers; else what went wrong."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url.rstrip("/") + "/models", timeout=3) as response:
            json.load(response)
    except (OSError, ValueError):
        return f"nothing answers at {url} yet"
    return None


def read_keys(path: Path) -> dict[str, str]:
    """The NAME=value lines of a keys file (no values are printed)."""
    keys: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return keys
    for line in text.splitlines():
        name, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and name.strip():
            keys[name.strip()] = value.strip().strip("'\"")
    return keys


def write_private(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` readable only by its owner, replacing it in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


# -- the wizard ------------------------------------------------------------------------------


class Wizard:
    def __init__(
        self,
        asker: Asker,
        path: Path,
        *,
        environ: Mapping[str, str],
        fund: Callable[[str], bool] | None = None,
        list_on_agentverse: Callable[[BridgeConfig, str, str], None] | None = None,
        probe: Callable[[str], str | None] = probe_model_server,
        free_port: Callable[[int], bool] = port_is_free,
    ) -> None:
        self.asker = asker
        self.path = path
        self.environ = environ
        self.fund = fund
        self.list_on_agentverse = list_on_agentverse
        self.probe = probe
        self.free_port = free_port
        self.old: dict[str, Any] = {}

    # The previous answers, if any.
    def _old(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.old
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def run(self) -> int:
        say = self.asker.say
        seed = self.environ.get("UAGENT_SEED", "").strip()
        if len(seed) < MIN_SEED_LENGTH:
            say("Your agent needs its own secret key first. Run setup through Hermes:")
            say("  hermes fetchai-bridge setup")
            say("It creates the key and keeps it in Hermes' .env file.")
            return 1
        if not self._load_old():
            return 1
        self._identity(seed)
        config = dict(self.old)
        config["version"] = 1
        agent = self._agent()
        services = self._services(mailbox=agent["mode"] == "mailbox")
        buying = self._buying(mailbox=agent["mode"] == "mailbox")
        config["agent"] = {**(self._old("agent", default={}) or {}), **agent}
        config.setdefault("policy", {"public_tools": []})
        payments = dict(self._old("payments", default={}) or {})
        payments["enabled"] = bool(services)
        config["payments"] = payments
        config["chat"] = {"enable_chat": bool(services) and agent["mode"] == "mailbox"}
        config["services"] = services
        config["buying"] = {**(self._old("buying", default={}) or {}), **buying}
        cfg = self._validate(config, seed)
        if cfg is None:
            return 1
        self._write(config)
        say(f"Saved your choices to {self.path}")
        self._check(cfg)
        self._after(cfg, seed)
        self._next_steps(cfg)
        self._report(cfg)
        return 0

    def _report(self, cfg: BridgeConfig) -> None:
        """Tell the plugin what was chosen, so it can line up its own settings."""
        target = self.environ.get(RESULT_VAR)
        if target:
            result = {
                "config": str(self.path),
                "selling": bool(cfg.services),
                "buying": cfg.buying.enabled,
            }
            Path(target).write_text(json.dumps(result), encoding="utf-8")

    def _load_old(self) -> bool:
        if not self.path.exists():
            return True
        try:
            text = self.path.read_text(encoding="utf-8")
            loaded = yaml.safe_load(text) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.asker.say(f"Your config at {self.path} cannot be read ({exc}).")
            loaded, text = {}, ""
        if not isinstance(loaded, dict):
            loaded = {}
        if not text.startswith(HEADER.splitlines()[0]):
            self.asker.say(f"There is already a config at {self.path} that setup did not write.")
            if not self.asker.yes(
                "replace", "Replace it? The old one is kept next to it as bridge.yaml.bak", False
            ):
                self.asker.say("Nothing was changed.")
                return False
        self.old = loaded
        return True

    def _identity(self, seed: str) -> None:
        say = self.asker.say
        say("Your agent")
        say(f"  Address:        {agent_address(seed)}")
        say("                  (other agents, and ASI:One users, reach your agent by this)")
        say(f"  Income wallet:  {wallet_address(seed)}  (what your services earn arrives here)")
        say(
            f"  Buying wallet:  {wallet_address(seed, BUYING_WALLET_INDEX)}  "
            "(pays other agents, if you let Hermes buy)"
        )
        say("Your agent's secret key is UAGENT_SEED in Hermes' .env file. Keep a copy somewhere")
        say("safe and private: without it, this agent's address, its ratings, and the test FET")
        say("in its wallets are gone for good. Anyone who has it controls the agent.")
        say()

    def _agent(self) -> dict[str, Any]:
        ask, say = self.asker, self.asker.say
        name = ask.ask(
            "name",
            "What should your agent be called? (shown to other agents)",
            default=self._old("agent", "name", default="hermes_agent"),
            check=agent_name,
        )
        description = ask.ask(
            "description",
            "Describe it in one sentence (shown on Agentverse)",
            default=self._old(
                "agent", "description", default="Services from a Hermes agent, paid in test FET."
            ),
            check=check_text(300),
        )
        agent: dict[str, Any] = {
            "name": name,
            "description": description,
            "network": "testnet",
            "dev_random_seed": False,
            "enable_agent_inspector": False,
        }
        port = int(self._old("agent", "port", default=DEFAULT_PORT))
        if not self.free_port(port):
            port = next((p for p in range(port + 1, port + 50) if self.free_port(p)), port)
        agent["port"] = port
        has_key = bool(self.environ.get("AGENTVERSE_API_KEY", "").strip())
        mailbox = False
        if has_key:
            mailbox = ask.yes(
                "agentverse",
                "Let ASI:One users and agents everywhere reach your agent, through your "
                "Agentverse account? (recommended)",
                self._old("agent", "mode", default="mailbox") == "mailbox",
            )
        else:
            say("Without an Agentverse API key, your agent can only be reached from this computer,")
            say("which is good for trying it out. To reach ASI:One users later, run setup again")
            say("and give it the key when asked.")
        if mailbox:
            agent["mode"] = "mailbox"
            agent["publish_manifest"] = True
            agent["endpoint"] = None
            agent["handle"] = (
                ask.ask(
                    "handle",
                    f"A short handle ASI:One users can type, like @hermes-research ({HANDLE_HINT}),"
                    " or leave it empty",
                    default=self._old("agent", "handle", default="") or "",
                    check=check_handle,
                )
                or None
            )
        else:
            agent["mode"] = "endpoint"
            agent["publish_manifest"] = False
            agent["endpoint"] = f"http://127.0.0.1:{port}/submit"
            agent["handle"] = None
        say()
        return agent

    def _services(self, *, mailbox: bool) -> dict[str, Any]:
        ask, say = self.asker, self.asker.say
        old: dict[str, Any] = dict(self._old("services", default={}) or {})
        if not ask.yes(
            "sell",
            "Sell services to other agents for FET? (test FET only: free test money)",
            bool(old) or not self.old,
        ):
            say()
            return {}
        if not mailbox:
            say("Note: until your agent can be reached through Agentverse, only agents on this")
            say("computer can buy from it.")
        services: dict[str, Any] = {}
        research = self._research(old.get(RESEARCH))
        if research:
            services[RESEARCH] = research
        review = self._review(old.get(REVIEW))
        if review:
            services[REVIEW] = review
        services.update(self._own_programs(old))
        if not services:
            say("No services chosen, so nothing is for sale.")
        say()
        return services

    def _research(self, old: Any) -> dict[str, Any] | None:
        ask, say = self.asker, self.asker.say
        if not ask.yes(
            "research",
            "Offer research? A separate Hermes searches the web and answers; it cannot reach "
            "your files, accounts, or terminal",
            old is not None,
        ):
            return None
        old_runner = old.get("runner", {}) if isinstance(old, dict) else {}
        old_provider = str(old_runner.get("provider") or "")
        provider = ask.choose(
            "research.provider",
            "Which AI service should do the research?",
            {name: choice for name, (_, choice, _, _) in PROVIDERS.items()},
            old_provider if old_provider in PROVIDERS else "openrouter",
        )
        label, _, key_name, suggested = PROVIDERS[provider]
        if old_provider == provider and old_runner.get("model"):
            suggested = str(old_runner["model"])
        model = ask.ask(
            "research.model",
            "Which model? (as that service names it)",
            default=suggested,
            check=check_text(200),
        )
        runner: dict[str, Any] = {
            "type": "hermes",
            "toolsets": ["web"],
            "provider": provider,
            "model": model,
            "instructions": old_runner.get("instructions") or RESEARCH_INSTRUCTIONS,
            "max_turns": old_runner.get("max_turns", 8),
            "timeout_seconds": old_runner.get("timeout_seconds", 300),
        }
        if provider == "custom":
            runner["base_url"] = ask.ask(
                "research.url",
                "The model server's address",
                default=old_runner.get("base_url") or LOCAL_MODEL_URL,
                check=check_local_url,
            )
        if key_name and not self._research_key(key_name, label):
            say("Research is not offered until it has a key; run setup again to add one.")
            return None
        price = ask.ask(
            "research.price",
            "Price for one research request, in FET",
            default=str(old.get("price", "0.05")) if isinstance(old, dict) else "0.05",
            check=check_price,
        )
        if key_name:
            say("Buyers pay in test FET, which is free, but each research request uses your")
            say(f"{label} account, which costs real money. Set a spending limit with {label},")
            say("and choose how many requests a day to take.")
        per_day = ask.ask(
            "research.per_day",
            "Most research requests a day",
            default=str(old.get("max_runs_per_day", RESEARCH_RUNS_PER_DAY))
            if isinstance(old, dict)
            else str(RESEARCH_RUNS_PER_DAY),
            check=check_runs_per_day,
        )
        return {
            **RESEARCH_SERVICE,
            "price": price,
            "max_runs_per_day": int(per_day),
            "runner": runner,
        }

    def _research_key(self, key_name: str, label: str) -> bool:
        """Make sure the research guest has its own model key; True if it does."""
        ask, say = self.asker, self.asker.say
        path = self._state_dir() / "guests" / f"{RESEARCH}.env"
        keys = read_keys(path)
        if keys.get(key_name) and ask.yes(
            "research.keep_key", f"Keep the {key_name} already saved for research?", True
        ):
            return True
        say(f"Research needs its own key for {label}. It is kept in {path},")
        say("readable only by you, and used only for buyers' research; your own Hermes keys")
        say("are never shared.")
        key = ask.secret("research.key", f"Paste the {key_name}, or press Enter to skip")
        if not key:
            return False
        keys[key_name] = key
        write_private(path, "".join(f"{name}={value}\n" for name, value in keys.items()))
        return True

    def _review(self, old: Any) -> dict[str, Any] | None:
        ask, say = self.asker, self.asker.say
        if not ask.yes(
            "review",
            "Offer a defensive code security review by an AI model on this computer? Buyers' "
            "code never leaves your machine (needs Ollama, LM Studio, or another local model "
            "server)",
            old is not None,
        ):
            return None
        argv = old.get("runner", {}).get("argv", []) if isinstance(old, dict) else []
        old_url = argv[argv.index("--url") + 1] if "--url" in argv[:-1] else LOCAL_MODEL_URL
        old_model = argv[argv.index("--model") + 1] if "--model" in argv[:-1] else REVIEW_MODEL
        url = ask.ask(
            "review.url", "The model server's address", default=old_url, check=check_local_url
        )
        model = ask.ask("review.model", "Which model?", default=old_model, check=check_text(200))
        problem = self.probe(url)
        if problem:
            say(f"Note: {problem}. Start your model server before buyers arrive; with Ollama:")
            say(f"  ollama pull {model}   (once), then keep Ollama running")
            say("A review that fails keeps the buyer's payment for another try.")
        price = ask.ask(
            "review.price",
            "Price for one review, in FET",
            default=str(old.get("price", "0.1")) if isinstance(old, dict) else "0.1",
            check=check_price,
        )
        return {
            **REVIEW_SERVICE,
            "price": price,
            "input": {"max_chars": 20000, "check_urls": False},
            "runner": {
                "type": "command",
                "argv": [
                    sys.executable,
                    "-m",
                    "hermes_fetch_ai.local_review",
                    "--url",
                    url,
                    "--model",
                    model,
                ],
                "timeout_seconds": 900,
            },
        }

    def _own_programs(self, old: dict[str, Any]) -> dict[str, Any]:
        ask, say = self.asker, self.asker.say
        services: dict[str, Any] = {}
        for name, svc in old.items():
            if name in (RESEARCH, REVIEW) or not isinstance(svc, dict):
                continue
            if ask.yes(f"keep.{name}", f"Keep selling {svc.get('title', name)} ({name})?", True):
                services[name] = svc
        while ask.yes(
            "own",
            "Sell your own program as a service? It gets each buyer's request, and what it "
            "prints is the answer",
            False,
        ):
            say('The program reads the request as JSON on its input, {"request": "..."},')
            say("and prints the answer. It runs without a shell, in an empty folder.")
            program = ask.ask("own.program", "Full path to the program", check=check_program)
            name = ask.ask(
                "own.name", "A short name buyers type, like legal-draft", check=check_service_name
            )
            if name in services:
                say(f"You already sell a service called {name}; this one replaces it.")
            title = ask.ask("own.title", "Its title, like Draft a motion", check=check_text(80))
            description = ask.ask(
                "own.description", "What it does, in one or two sentences", check=check_text(500)
            )
            price = ask.ask(
                "own.price", "Price for one request, in FET", default="0.1", check=check_price
            )
            disclaimer = ask.ask(
                "own.disclaimer",
                "A note added to every answer, or leave it empty (for example: A first draft "
                "for review by a licensed attorney; not legal advice.)",
                check=check_optional_text(500),
            )
            example = ask.ask(
                "own.example",
                "An example request buyers can try, shown on Agentverse (or leave it empty)",
                check=check_optional_text(200),
            )
            seconds = ask.ask(
                "own.timeout",
                "Most seconds one request may take",
                default="300",
                check=check_seconds,
            )
            argv = [sys.executable, program] if program.endswith(".py") else [program]
            service: dict[str, Any] = {
                "title": title,
                "description": description,
                "price": price,
                "runner": {"type": "command", "argv": argv, "timeout_seconds": float(seconds)},
            }
            if disclaimer:
                service["disclaimer"] = disclaimer
            if example:
                service["example"] = example
            services[name] = service
        return services

    def _buying(self, *, mailbox: bool) -> dict[str, Any]:
        ask, say = self.asker, self.asker.say
        old = self._old("buying", default={}) or {}
        if not ask.yes(
            "buy",
            "Let Hermes buy services from other agents? It asks you before every payment, and "
            "never while YOLO mode is on",
            bool(old.get("enabled")),
        ):
            say()
            return {"enabled": False}
        if not mailbox:
            say("Note: agents elsewhere can answer Hermes only once your agent can be reached")
            say("through Agentverse; until then Hermes can buy only from agents on this computer.")
        while True:
            max_payment = ask.ask(
                "buy.max_payment",
                "Most Hermes may pay at once, in test FET",
                default=str(old.get("max_payment", "1")),
                check=check_price,
            )
            max_per_day = ask.ask(
                "buy.max_per_day",
                "Most it may spend in a day, in test FET",
                default=str(old.get("max_per_day", "5")),
                check=check_price,
            )
            if parse_fet(max_payment) <= parse_fet(max_per_day):
                break
            problem = "The most for one payment cannot be more than the most for a day."
            if isinstance(ask, ScriptedAsker):
                raise SetupError(problem)
            say(problem)
        per_seller = min(
            parse_fet(str(old.get("max_per_seller_per_day", "2"))), parse_fet(max_per_day)
        )
        say()
        return {
            "enabled": True,
            "max_payment": max_payment,
            "max_per_day": max_per_day,
            "max_per_seller_per_day": format_fet(per_seller),
        }

    def _state_dir(self) -> Path:
        configured = self._old("payments", "state_dir")
        return Path(configured).expanduser() if configured else default_state_dir()

    def _validate(self, config: dict[str, Any], seed: str) -> BridgeConfig | None:
        previous = os.environ.get("UAGENT_SEED")
        os.environ["UAGENT_SEED"] = seed
        try:
            return BridgeConfig.model_validate(config)
        except ValidationError as exc:
            self.asker.say(f"These choices do not work together: {format_validation_error(exc)}")
            self.asker.say("Nothing was saved.")
            return None
        finally:
            if previous is None:
                os.environ.pop("UAGENT_SEED", None)
            else:
                os.environ["UAGENT_SEED"] = previous

    def _write(self, config: dict[str, Any]) -> None:
        if self.path.exists() and not self.path.read_text(encoding="utf-8").startswith(
            HEADER.splitlines()[0]
        ):
            backup = self.path.with_name(self.path.name + ".bak")
            write_private(backup, self.path.read_text(encoding="utf-8"))
        ordered: dict[str, Any] = {
            key: config[key]
            for key in ("version", "agent", "policy", "payments", "chat", "services", "buying")
            if key in config
        }
        ordered.update({key: value for key, value in config.items() if key not in ordered})
        body = yaml.safe_dump(_drop_none(ordered), sort_keys=False, allow_unicode=True)
        write_private(self.path, HEADER + body)

    def _check(self, cfg: BridgeConfig) -> None:
        from .services import program_problems

        problems = program_problems(cfg)
        if problems:
            self.asker.say("Before you start selling, fix these:")
            for problem in problems:
                self.asker.say(f"  - {problem}")

    def _after(self, cfg: BridgeConfig, seed: str) -> None:
        ask, say = self.asker, self.asker.say
        if cfg.buying.enabled and self.fund is not None:
            buying = wallet_address(seed, BUYING_WALLET_INDEX)
            if ask.yes(
                "fund", "Get free test FET for the buying wallet from Fetch's faucet now?", True
            ):
                self.fund(buying)
            else:
                say("Later: hermes fetchai-bridge wallet --fund")
        api_key = self.environ.get("AGENTVERSE_API_KEY", "").strip()
        if cfg.agent.mode == "mailbox" and api_key and self.list_on_agentverse is not None:
            say("Your agent reaches others through a mailbox on Agentverse, which it needs once.")
            if ask.yes(
                "list",
                "Create its mailbox and public listing on Agentverse now?",
                True,
            ):
                try:
                    self.list_on_agentverse(cfg, seed, api_key)
                except Exception as exc:  # noqa: BLE001 - any failure gets the same advice
                    say(f"Agentverse did not take it ({exc}). Try again later with:")
                    say("  hermes fetchai-bridge agentverse register")
                else:
                    say("Done: your agent is listed on Agentverse.")
            else:
                say("Later: hermes fetchai-bridge agentverse register")
        say()

    def _next_steps(self, cfg: BridgeConfig) -> None:
        say = self.asker.say
        say("Next:")
        say("  hermes fetchai-bridge start    start your agent; it keeps running in the background")
        say("  hermes fetchai-bridge status   see what it is doing")
        if cfg.buying.enabled and not self.environ.get(RESULT_VAR):
            say('  In Hermes\' plugin settings, turn on "Let Hermes buy from other agents".')


def _drop_none(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _drop_none(value) for key, value in node.items() if value is not None}
    if isinstance(node, list):
        return [_drop_none(value) for value in node]
    return node


def run_setup(
    asker: Asker | None = None,
    path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    fund: Callable[[str], bool] | None = None,
    list_on_agentverse: Callable[[BridgeConfig, str, str], None] | None = None,
) -> int:
    wizard = Wizard(
        asker or ConsoleAsker(),
        path or managed_config_path(),
        environ=os.environ if environ is None else environ,
        fund=fund,
        list_on_agentverse=list_on_agentverse,
    )
    try:
        return wizard.run()
    except SetupError as exc:
        wizard.asker.say(f"setup: {exc}")
        return 1
