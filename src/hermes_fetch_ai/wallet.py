"""The agent's identity and wallet keys, derived from its seed as uAgents does.

uAgents derives two different keys from ``UAGENT_SEED``: the agent identity
(``agent1...``, signs messages) and a wallet (``fetch1...``, holds FET). The
wallet at index 0 is the one uAgents itself uses; buying from other agents
will use a separate index so spending never touches the income wallet.
"""

from __future__ import annotations

from cosmpy.aerial.wallet import LocalWallet
from cosmpy.crypto.keypairs import PrivateKey
from uagents_core.identity import Identity, derive_key_from_seed

LEDGER_PREFIX = "fetch"
INCOME_WALLET_INDEX = 0


def agent_address(seed: str) -> str:
    """The ``agent1...`` address an agent with this seed has."""
    return str(Identity.from_seed(seed, 0).address)


def wallet_for(seed: str, index: int = INCOME_WALLET_INDEX) -> LocalWallet:
    key = PrivateKey(derive_key_from_seed(seed, LEDGER_PREFIX, index))
    return LocalWallet(key, prefix=LEDGER_PREFIX)


def wallet_address(seed: str, index: int = INCOME_WALLET_INDEX) -> str:
    """The ``fetch1...`` wallet address for this seed and key index."""
    return str(wallet_for(seed, index).address())
