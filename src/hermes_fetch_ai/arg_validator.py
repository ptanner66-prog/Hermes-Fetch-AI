from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from .config import BridgeConfig

SHELL_META = re.compile(r"[;&|`$<>\\]|\$\(|\${")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
ALLOWED_URL_SCHEMES = {"https"}


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
    except Exception:
        return None

    return None


def _is_private_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        weird = _parse_weird_ipv4(value)
        if weird is None:
            return False
        ip = weird
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved
    )


def _reject_url(value: str) -> None:
    if not URL_RE.match(value):
        return

    parsed = urlparse(value)
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise ValueError("URL scheme is not allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("URL host is required")
    if _is_private_ip(host) or host.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("URL targets private or local address")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror:
        addresses = []
    for item in addresses:
        sockaddr = item[4]
        if sockaddr and _is_private_ip(str(sockaddr[0])):
            raise ValueError("URL resolves to private or local address")


def _walk_strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        out: list[str] = []
        for v in obj.values():
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
        raise ValueError("tool args must be an object")

    name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", "")
    schema = normalize_schema(
        tool.get("inputSchema") if isinstance(tool, dict) else getattr(tool, "inputSchema", None)
    )
    Draft202012Validator(schema).validate(args)

    encoded = json.dumps(args, sort_keys=True).encode("utf-8")
    if len(encoded) > cfg.policy.max_args_bytes:
        raise ValueError("args exceed max_args_bytes")

    for s in _walk_strings(args):
        _reject_url(s)
        if name not in cfg.policy.trusted_shell_tools and (
            SHELL_META.search(s) or CONTROL_CHARS.search(s)
        ):
            raise ValueError("shell metacharacters are not allowed")
    return args
