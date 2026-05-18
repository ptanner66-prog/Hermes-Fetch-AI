from __future__ import annotations

from .config import BridgeConfig, PaymentFundsConfig
from .policy import normalize_tool_name


def is_payment_required(cfg: BridgeConfig, tool_name: str) -> bool:
    if cfg.payment.mode == "disabled":
        return False
    return normalize_tool_name(tool_name) in cfg.payment.priced_tools


def accepted_funds_for_tool(cfg: BridgeConfig, tool_name: str) -> list[PaymentFundsConfig]:
    safe_tool = normalize_tool_name(tool_name)
    tool_cfg = cfg.payment.priced_tools.get(safe_tool)
    if tool_cfg and tool_cfg.accepted_funds:
        return list(tool_cfg.accepted_funds)
    return list(cfg.payment.accepted_funds)
