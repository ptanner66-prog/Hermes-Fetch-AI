from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .config import BridgeConfig

SHELL_META = re.compile(r"[;&|`$<>\\]\n?|\$\(|\${")
SHELL_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")
_SCHEME_PREFIX = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
# URLs that appear anywhere inside a longer string, e.g. "see http://10.0.0.1/x".
_EMBEDDED_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\"'<>]+")
_TRAILING_PUNCTUATION = ".,;:!?)}'\""
# A whole string that is only a local or literal-IP host, optionally with a port
# or path ("localhost:8080", "169.254.169.254/latest", "[::1]:80"). Tools that
# add a missing "http://" would otherwise turn these into local requests.
_BARE_LITERAL_HOST = re.compile(
    r"^(?:localhost|\d{1,3}(?:\.\d{1,3}){3}|\[[0-9A-Fa-f:.]+\])(?::\d{1,5})?(?:[/?#]\S*)?$",
    re.IGNORECASE,
)
# Schemes treated as URLs even without "//", such as "file:/etc/passwd" or
# "data:text/plain,x". Any other "word:" prefix (e.g. "Note: hello") is plain text.
_URL_SCHEMES_WITHOUT_SLASHES = frozenset(
    {"data", "file", "javascript", "vbscript", "mailto", "jar", "blob", "view-source"}
)
_ALLOWED_URL_SCHEMES = {"http", "https"}


def normalize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    return schema or {"type": "object", "properties": {}}


def _parse_weird_ipv4(host: str) -> ipaddress.IPv4Address | None:
    try:
        return ipaddress.IPv4Address(host)
    except ValueError:
        pass

    try:
        if host.isdigit():
            return ipaddress.IPv4Address(int(host, 10))
        if host.lower().startswith("0x"):
            return ipaddress.IPv4Address(int(host, 16))
        parts = host.split(".")
        if all(p for p in parts) and any(
            p.startswith("0") or p.lower().startswith("0x") for p in parts
        ):
            nums = [
                int(p, 16 if p.lower().startswith("0x") else 8 if p.startswith("0") else 10)
                for p in parts
            ]
            while len(nums) < 4:
                nums.append(0)
            return ipaddress.IPv4Address(".".join(map(str, nums[:4])))
    except ValueError:
        return None
    return None


def _is_non_global_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        weird = _parse_weird_ipv4(value)
        if weird is None:
            return False
        ip = weird
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return bool(
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_multicast
    )


def _is_url_like(value: str) -> bool:
    match = _SCHEME_PREFIX.match(value)
    if not match:
        return False
    after_colon = value[match.end() :]
    return after_colon.startswith("/") or match.group(1).lower() in _URL_SCHEMES_WITHOUT_SLASHES


def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        raise ValueError("unsupported URL scheme")

    host = parsed.hostname
    if not host:
        raise ValueError("URL host is required")

    host_lower = host.rstrip(".").lower()
    if _is_non_global_ip(host) or host_lower in {"localhost", "localhost.localdomain"}:
        raise ValueError("URL targets private or local address")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError("URL host could not be resolved") from None

    for info in infos:
        resolved = str(info[4][0])
        if _is_non_global_ip(resolved):
            raise ValueError("URL resolves to private or local address")


def _reject_url(value: str) -> None:
    candidate = value.strip()
    checked: set[str] = set()
    if _is_url_like(candidate):
        if candidate != value:
            raise ValueError("URL must not contain leading or trailing whitespace")
        _check_url(candidate)
        checked.add(candidate)
    elif _BARE_LITERAL_HOST.match(candidate):
        _check_url("http://" + candidate)

    for match in _EMBEDDED_URL.finditer(value):
        url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        if url not in checked:
            _check_url(url)
            checked.add(url)


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


def validate_args(tool: Any, args: dict[str, Any], cfg: BridgeConfig) -> dict[str, Any]:
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

    encoded = json.dumps(args, sort_keys=True).encode("utf-8")
    if len(encoded) > cfg.policy.max_args_bytes:
        raise ValueError("args exceed max_args_bytes")

    for s in _walk_strings(args):
        _reject_url(s)
        # Deliberately strict: tools that legitimately need these characters
        # (query strings, multi-line text) must be listed in trusted_shell_tools.
        if name not in cfg.policy.trusted_shell_tools and (
            SHELL_META.search(s) or SHELL_CONTROL.search(s)
        ):
            raise ValueError("shell metacharacters or control characters are not allowed")

    return args
