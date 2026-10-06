from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .config import BridgeConfig

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

SHELL_META = re.compile(r"[;&|`$<>\\]")
# ASCII control characters, plus the Unicode line and paragraph separators.
SHELL_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")
_SCHEME_PREFIX = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
# URLs that appear anywhere inside a longer string, e.g. "see http://10.0.0.1/x",
# including web URLs written without slashes ("http:10.0.0.1/x").
_EMBEDDED_URL = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\"'<>]+|\bhttps?:[^\s\"'<>/][^\s\"'<>]*", re.IGNORECASE
)
_TRAILING_PUNCTUATION = ".,;:!?)}'\""
# Schemes treated as URLs even without "//", such as "file:/etc/passwd" or
# "data:text/plain,x". Any other "word:" prefix (e.g. "Note: hello") is plain text.
_URL_SCHEMES_WITHOUT_SLASHES = frozenset(
    {"data", "file", "javascript", "vbscript", "mailto", "jar", "blob", "view-source"}
    | {"http", "https"}
)
_ALLOWED_URL_SCHEMES = {"http", "https"}
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}
# A whole string that is only a host, optionally with a port or path
# ("localhost:8080", "169.254.169.254/latest", "[::1]:80"). Tools that add a
# missing "http://" would turn these into requests.
_BARE_HOST = re.compile(
    r"^(?P<host>\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(?P<rest>(?::\d{1,5})?(?:[/?#]\S*)?)$"
)
_DOTTED_QUAD = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
_IPV4_LITERAL_CHARS = frozenset("0123456789abcdefxABCDEFX.")
# The most distinct host names one call may make the bridge resolve.
MAX_URL_HOSTS = 16


def normalize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    return schema or {"type": "object", "properties": {}}


def _ipv4_literal(host: str) -> ipaddress.IPv4Address | None:
    """Parse an IPv4 address in any form the C library accepts.

    Besides 127.0.0.1 that includes 2130706433, 0x7f000001, 0177.0.0.1 and
    127.1, all of which HTTP clients connect to without a DNS lookup.
    """
    if not host or not set(host) <= _IPV4_LITERAL_CHARS:
        return None
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


def _ip_literal(host: str) -> IPAddress | None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return _ipv4_literal(host)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def _is_non_global(ip: IPAddress) -> bool:
    return bool(
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_multicast
    )


def _host_needing_dns(host: str) -> str | None:
    """Reject local names and non-global IP literals; return a name to resolve, if any."""
    name = host.rstrip(".").lower()
    if name in _LOCAL_HOSTNAMES:
        raise ValueError("URL targets private or local address")
    literal = _ip_literal(name)
    if literal is None:
        return name
    if _is_non_global(literal):
        raise ValueError("URL targets private or local address")
    return None


def _check_url(url: str) -> str | None:
    """Check one URL; return its host name if that still needs a DNS check."""
    if any(ch == "\\" or ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        # Parsers disagree about these (WHATWG reads "\" as "/"), so a URL could
        # pass this check yet reach a different host.
        raise ValueError("URL must not contain backslashes, whitespace, or control characters")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        raise ValueError("unsupported URL scheme")
    if not parsed.hostname:
        raise ValueError("URL host is required")
    return _host_needing_dns(parsed.hostname)


def _is_url_like(value: str) -> bool:
    match = _SCHEME_PREFIX.match(value)
    if not match:
        return False
    after_colon = value[match.end() :]
    return after_colon.startswith("/") or match.group(1).lower() in _URL_SCHEMES_WITHOUT_SLASHES


def _looks_like_encoded_ipv4(host: str) -> bool:
    """True for "127.1", "0x7f000001" or "2130706433", but not "12" (as in "12:30")."""
    return "." in host or host.startswith("0x") or len(host) >= 8


def _bare_host(value: str) -> str | None:
    """The host of a string that is nothing but a local name or IP literal.

    Ordinary words are text, and so are numbers such as "42", "10.5" or the
    time "12:30": other than a dotted quad, a number only counts as a host
    when it has a port or path and looks like an encoded address, as in
    "2130706433:80" or "127.1/admin".
    """
    match = _BARE_HOST.match(value)
    if not match:
        return None
    host = match.group("host").strip("[]").rstrip(".").lower()
    if host in _LOCAL_HOSTNAMES:
        return host
    if _ip_literal(host) is None:
        return None
    if ":" in host or _DOTTED_QUAD.fullmatch(host):
        return host
    if match.group("rest") and _looks_like_encoded_ipv4(host):
        return host
    return None


def _url_hosts(value: str) -> set[str]:
    """Check every URL in ``value``; return the host names that still need DNS checks."""
    hosts: set[str] = set()
    candidate = value.strip()
    if _is_url_like(candidate):
        if candidate != value:
            raise ValueError("URL must not contain leading or trailing whitespace")
        hosts.add(_check_url(candidate) or "")
    else:
        bare = _bare_host(candidate)
        if bare is not None:
            hosts.add(_host_needing_dns(bare) or "")
    for match in _EMBEDDED_URL.finditer(value):
        hosts.add(_check_url(match.group(0).rstrip(_TRAILING_PUNCTUATION)) or "")
    hosts.discard("")
    return hosts


def _check_resolved(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        raise ValueError("URL host could not be resolved") from None
    for info in infos:
        resolved = _ip_literal(str(info[4][0]))
        if resolved is None or _is_non_global(resolved):
            raise ValueError("URL resolves to private or local address")


def _walk_strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        out: list[str] = []
        for k, v in obj.items():
            out.extend(_walk_strings(k))
            out.extend(_walk_strings(v))
        return out
    if isinstance(obj, list):
        list_out: list[str] = []
        for v in obj:
            list_out.extend(_walk_strings(v))
        return list_out
    return []


def validate_args(
    tool: Any,
    args: dict[str, Any],
    cfg: BridgeConfig,
    *,
    shell_checks: bool = True,
    url_checks: bool = True,
) -> dict[str, Any]:
    """Check a call's arguments against the tool's schema and the bridge's URL and shell rules.

    The cheap checks run first, so a call that fails them causes no DNS
    lookups, and one call can make the bridge resolve at most MAX_URL_HOSTS
    distinct names. Services turn the shell checks off (their requests never
    reach a shell) and may turn the URL checks off (a code review quotes local
    addresses without fetching them).
    """
    if not isinstance(args, dict):
        raise TypeError("tool args must be an object")

    name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", "")
    schema = normalize_schema(
        tool.get("inputSchema") if isinstance(tool, dict) else getattr(tool, "inputSchema", None)
    )
    try:
        Draft202012Validator(schema).validate(args)
    except JsonSchemaValidationError:
        raise ValueError("schema validation failed") from None

    strings = _walk_strings(args)
    # Deliberately strict: tools that legitimately need these characters (query
    # strings, multi-line text) must be listed in trusted_shell_tools.
    if (
        shell_checks
        and name not in cfg.policy.trusted_shell_tools
        and any(SHELL_META.search(s) or SHELL_CONTROL.search(s) for s in strings)
    ):
        raise ValueError("shell metacharacters or control characters are not allowed")
    if not url_checks:
        return args

    hosts: set[str] = set()
    for s in strings:
        hosts |= _url_hosts(s)
    if len(hosts) > MAX_URL_HOSTS:
        raise ValueError("too many URL hosts in one call")
    for host in sorted(hosts):
        _check_resolved(host)
    return args
