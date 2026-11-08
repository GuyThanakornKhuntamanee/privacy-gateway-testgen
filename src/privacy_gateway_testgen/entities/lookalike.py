"""Lookalike values for negative and false-positive testing.

They are annotated in the dataset with ``detection_expected: false`` so a
detector's false-positive rate can be measured.  Some are deliberately
ambiguous (a 13-digit order number, a card number that fails Luhn); the
``note`` field records that ambiguity.
"""

from __future__ import annotations

import random

from ..models import Entity
from . import common

PUBLIC_IPS = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "203.0.113.10"]
DOC_IPS = ["192.0.2.10", "198.51.100.25", "203.0.113.77"]
PLACEHOLDERS = ["YOUR_API_KEY_HERE", "<REDACTED>", "changeme", "********", "${DB_PASSWORD}"]


def _order_id(rng, ctx):
    return Entity("lookalike", "order_id", f"ORD-2026-{common.digits(rng, 6)}", valid=True,
                  detection_expected=False, note="ordinary business identifier")


def _invoice(rng, ctx):
    return Entity("lookalike", "invoice_number", f"INV-2026-{common.digits(rng, 5)}", valid=True,
                  detection_expected=False, note="ordinary business identifier")


def _sku(rng, ctx):
    return Entity("lookalike", "product_code", f"SKU-{common.digits(rng, 4)}-{rng.choice('ABCDEFG')}",
                  detection_expected=False, note="ordinary business identifier")


def _amount(rng, ctx):
    return Entity("lookalike", "monetary_amount", f"THB {rng.randrange(100, 90000, 50):,}.00",
                  detection_expected=False, note="ordinary business data")


def _timestamp(rng, ctx):
    return Entity("lookalike", "timestamp", f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T09:12:44Z",
                  detection_expected=False, note="ordinary business data")


def _version(rng, ctx):
    return Entity("lookalike", "version_string", f"v{rng.randint(1, 9)}.{rng.randint(0, 20)}.{rng.randint(0, 50)}",
                  detection_expected=False, note="software version, not an identifier")


def _build_hash(rng, ctx):
    return Entity("lookalike", "build_hash", common.hexstr(rng, 7), detection_expected=False,
                  note="git short hash")


def _public_ip(rng, ctx):
    return Entity("lookalike", "public_ip_address", rng.choice(PUBLIC_IPS), detection_expected=False,
                  note="public service address, not internal infrastructure")


def _doc_ip(rng, ctx):
    return Entity("lookalike", "documentation_ip_address", rng.choice(DOC_IPS), detection_expected=False,
                  note="RFC 5737 documentation range")


def _loopback(rng, ctx):
    return Entity("lookalike", "loopback_ip_address", "127.0.0.1", detection_expected=False,
                  note="loopback address")


def _placeholder(rng, ctx):
    return Entity("lookalike", "placeholder_secret", rng.choice(PLACEHOLDERS), valid=False,
                  detection_expected=False, note="placeholder, no secret value present")


def _malformed_id(rng, ctx):
    raw = common.digits(rng, rng.choice([11, 12, 14]))
    return Entity("lookalike", "malformed_national_id", raw, valid=False,
                  detection_expected=False, note="wrong length, cannot be a valid Thai national ID")


def _invalid_national_id(rng, ctx):
    raw = common.digits(rng, 13)
    if common.thai_id_valid(raw):
        raw = raw[:12] + str((int(raw[12]) + 1) % 10)
    return Entity("lookalike", "invalid_national_id", raw, valid=False,
                  detection_expected=False, note="13 digits but fails the Thai national ID checksum")


def _invalid_card(rng, ctx):
    partial = "411111" + common.digits(rng, 9)
    value = partial + common.luhn_check_digit(partial)
    # Break the check digit deliberately.
    value = value[:-1] + str((int(value[-1]) + 1) % 10)
    return Entity("lookalike", "invalid_card_number", value, valid=False,
                  detection_expected=False, note="fails Luhn check; pattern resembles a card")


def _reserved_phone(rng, ctx):
    return Entity("lookalike", "reserved_fictional_phone", f"+1-555-01{rng.randint(0, 99):02d}", valid=True,
                  detection_expected=False, note="reserved fictional telephone range")


def _public_domain(rng, ctx):
    return Entity("lookalike", "public_domain", rng.choice(["www.example.com", "docs.example.org"]),
                  detection_expected=False, note="reserved example domain")


def _uuid(rng, ctx):
    raw = common.hexstr(rng, 32)
    value = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return Entity("lookalike", "random_uuid", value, detection_expected=False,
                  note="non-sensitive opaque identifier")


GENERATORS = {
    "order_id": (10, _order_id),
    "invoice_number": (8, _invoice),
    "product_code": (8, _sku),
    "monetary_amount": (8, _amount),
    "timestamp": (8, _timestamp),
    "version_string": (6, _version),
    "build_hash": (6, _build_hash),
    "public_ip_address": (7, _public_ip),
    "documentation_ip_address": (6, _doc_ip),
    "loopback_ip_address": (4, _loopback),
    "placeholder_secret": (9, _placeholder),
    "malformed_national_id": (7, _malformed_id),
    "invalid_national_id": (7, _invalid_national_id),
    "invalid_card_number": (6, _invalid_card),
    "reserved_fictional_phone": (4, _reserved_phone),
    "public_domain": (5, _public_domain),
    "random_uuid": (5, _uuid),
}
