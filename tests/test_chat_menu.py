"""The chat menu and how a plain-text message picks a service."""

import pytest

from hermes_fetch_ai.chat_menu import ask_for_request, menu, pick_service
from hermes_fetch_ai.config import ServiceConfig


def service(title, price="0.1", description="Does a thing."):
    return ServiceConfig.model_validate(
        {"title": title, "description": description, "price": price, "runner": {"type": "echo"}}
    )


SERVICES = {
    "security-review": service("Defensive code security review", "0.1", "Reviews your code."),
    "review": service("Quick review", "0.02"),
    "word-count": service("Word count", "0"),
}


def test_menu_lists_services_prices_and_how_to_order():
    text = menu("hermes_seller", SERVICES)
    assert text.startswith("Hi! I'm hermes_seller, a Hermes agent.")
    assert "1. **Defensive code security review** (`security-review`), 0.1 testnet FET" in text
    assert "   Reviews your code." in text
    assert "3. **Word count** (`word-count`), free" in text
    assert "`security-review: <your request>`" in text
    assert "approve the payment before anything runs" in text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("security-review: def f(): pass", ("security-review", "def f(): pass")),
        ("  Security-Review\nimport os\n", ("security-review", "import os")),
        ("defensive code security review - check this", ("security-review", "check this")),
        ("review: short", ("review", "short")),
        ("word-count", ("word-count", "")),
        ("Word count — hello there", ("word-count", "hello there")),
        ("@hermes-reviews security-review: x = 1", ("security-review", "x = 1")),
        ("@agent1qabc, review: short", ("review", "short")),
    ],
)
def test_a_message_orders_by_name_or_title(text, expected):
    assert pick_service(text, SERVICES) == expected


@pytest.mark.parametrize(
    "text", ["hi", "menu", "reviewer: x", "please review this", "", "   ", "@hermes-reviews hi"]
)
def test_other_messages_order_nothing(text):
    assert pick_service(text, SERVICES) is None


def test_asking_for_the_request_names_the_format():
    text = ask_for_request("review", SERVICES["review"])
    assert "**Quick review** (0.02 testnet FET)" in text and "`review: <your request>`" in text
