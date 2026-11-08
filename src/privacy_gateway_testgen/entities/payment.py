"""Synthetic payment entity factories.

Only documented, non-live test card prefixes are used.  Values are structurally
valid (Luhn) so detectors can be tested, but they are not issued credentials.
"""

from __future__ import annotations

import random

from ..models import Entity
from . import common

TEST_BINS = ["411111", "424242", "555555", "601111", "378282"]


def _card(rng: random.Random, ctx) -> Entity:
    prefix = rng.choice(TEST_BINS)
    length = 15 if prefix.startswith("37") else 16
    partial = prefix + common.digits(rng, length - len(prefix) - 1)
    return Entity("payment", "payment_card_number", partial + common.luhn_check_digit(partial))


def _expiry(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "card_expiry_date", f"{rng.randint(1, 12):02d}/{rng.randint(2027, 2031)}")


def _cvv(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "card_verification_value", common.digits(rng, 3))


def _cardholder(rng: random.Random, ctx) -> Entity:
    name = common.english_person(rng) if rng.random() < 0.6 else common.thai_person(rng)
    return Entity("payment", "cardholder_name", name)


def _bank_account(rng: random.Random, ctx) -> Entity:
    raw = common.digits(rng, 10)
    return Entity("payment", "bank_account_number", f"{raw[:3]}-{raw[3]}-{raw[4:9]}-{raw[9]}")


def _txn_ref(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "payment_transaction_reference", f"TXN-2026-{common.digits(rng, 8)}")


def _auth_code(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "payment_authorization_code", "AUTH-" + common.alnum(rng, 6).upper())


def _payment_token(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "payment_token", "tok_example_fake_" + common.hexstr(rng, 16))


def _gateway_credential(rng: random.Random, ctx) -> Entity:
    return Entity("payment", "payment_gateway_credential", "sk_example_fake_" + common.hexstr(rng, 24))


GENERATORS = {
    "payment_card_number": (22, _card),
    "card_expiry_date": (14, _expiry),
    "card_verification_value": (10, _cvv),
    "cardholder_name": (12, _cardholder),
    "bank_account_number": (8, _bank_account),
    "payment_transaction_reference": (10, _txn_ref),
    "payment_authorization_code": (6, _auth_code),
    "payment_token": (8, _payment_token),
    "payment_gateway_credential": (6, _gateway_credential),
}
