"""Case-level scenario plan shared by every attachment in one test case.

A bundle must tell one story: the database endpoint in ``prod.env`` is the one
named in the incident report and in the deployment log, the same people appear
in the employee list and the payroll, and the same transaction reference links
an invoice to a transaction export.  Builders therefore draw shared values from
this plan instead of generating a fresh value per document.
"""

from __future__ import annotations

import datetime as _dt
import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..entities import EntityPool, common, entity_types
from ..models import Entity
from .org import OrgProfile

CHECK_STATUSES = ("passed", "failed", "not_applicable", "not_evaluated")
LOG_BASE = _dt.datetime(2026, 3, 18, 9, 12, tzinfo=_dt.timezone.utc)
_LOG_PATTERNS = (
    # ISO-8601, the generator's default: 2026-03-18T09:12:00Z or +07:00
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))"),
    # syslog/nginx style: 2026/03/18 09:12:00 +0000
    re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})"),
    # nginx clf style: 18/Mar/2026:09:12:00 +0000
    re.compile(r"(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})"),
)


def parse_log_timestamp(text: str) -> Optional[_dt.datetime]:
    """Parse the first timestamp this generator can emit inside one log line."""
    for pattern in _LOG_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1)
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y/%m/%d %H:%M:%S %z", "%d/%b/%Y:%H:%M:%S %z"):
            try:
                parsed = _dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
            return parsed.replace(tzinfo=parsed.tzinfo or _dt.timezone.utc).astimezone(_dt.timezone.utc)
    return None


def validate_log_order(lines: Sequence[str]) -> dict:
    """Chronological validation of rendered log lines.  Never assumes success."""
    stamps = [parse_log_timestamp(line) for line in lines]
    parsed = [stamp for stamp in stamps if stamp is not None]
    if len(lines) < 2 or len(parsed) < 2:
        return {"status": "not_evaluated", "evaluated_items": 0,
                "reason": "fewer than two parseable timestamps",
                "lines": len(lines), "parsed": len(parsed)}
    unparsed = [index for index, stamp in enumerate(stamps) if stamp is None]
    if unparsed:
        return {"status": "failed", "evaluated_items": len(parsed),
                "reason": "log line without a parseable timestamp",
                "unparsed_lines": unparsed[:5], "lines": len(lines)}
    out_of_order = [index for index in range(1, len(parsed)) if parsed[index] < parsed[index - 1]]
    status = "failed" if out_of_order else "passed"
    return {
        "status": status,
        "evaluated_items": len(parsed),
        "reason": "timestamp goes backwards" if out_of_order else "",
        "out_of_order_lines": out_of_order[:5],
        "lines": len(lines),
        "first": parsed[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last": parsed[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }



def safe_negative(rng: random.Random, entity_type: str) -> Entity:
    """A hard negative that resembles the field but is not sensitive data."""
    if entity_type in ("email_address",):
        return Entity("lookalike", "public_contact_email", "contact@example.com",
                      detection_expected=False, note="reserved example domain, public contact")
    if entity_type in ("thai_phone",):
        return Entity("lookalike", "reserved_fictional_phone", "+1-555-0100",
                      detection_expected=False, note="reserved fictional telephone range")
    if entity_type in ("thai_name",):
        return Entity("lookalike", "placeholder_person_name", "Example Contact",
                      detection_expected=False, note="placeholder, not a real person")
    if entity_type in ("thai_national_id", "patient_id", "passport_number"):
        value = rng.choice(["1234567890123", "ORD-2026-441920", "DOC-EXAMPLE-001"])
        return Entity("lookalike", "identifier_lookalike", value, detection_expected=False,
                      note="identifier-shaped value with no personal-data context")
    if entity_type == "thai_address":
        return Entity("lookalike", "public_address_example", "Example Tower, 1 Example Road",
                      detection_expected=False, note="fictional public place")
    if entity_type == "date_of_birth":
        return Entity("lookalike", "document_date", "2026-01-15",
                      detection_expected=False, note="ordinary document date")
    if entity_type == "payment_card_number":
        return Entity("lookalike", "invalid_card_number", "4111 1111 1111 1112",
                      valid=False, detection_expected=False, note="card-shaped but fails Luhn")
    if entity_type in ("card_expiry_date", "card_verification_value"):
        return Entity("lookalike", "document_number", "REF-2026-0192",
                      detection_expected=False, note="ordinary reference number")
    if entity_type in ("bank_account_number", "payment_transaction_reference"):
        return Entity("lookalike", "order_id", f"ORD-2026-{rng.randint(100000, 999999)}",
                      detection_expected=False, note="ordinary business identifier")
    if entity_type in ("api_key", "access_token", "refresh_token", "oauth_client_secret",
                       "password", "database_credential", "connection_string",
                       "cloud_access_key", "cloud_secret_key", "webhook_secret",
                       "encryption_key", "env_var_secret", "config_credential",
                       "jwt_token", "service_account_credential", "ssh_private_key", "tls_private_key"):
        return Entity("lookalike", "placeholder_secret", rng.choice(
            ["YOUR_API_KEY_HERE", "<REDACTED>", "changeme", "${DB_PASSWORD}", "********"]
        ), valid=False, detection_expected=False, note="placeholder, no secret value present")
    if entity_type in ("internal_ipv4", "internal_ipv6", "private_network"):
        return Entity("lookalike", "documentation_ip_address", rng.choice(
            ["192.0.2.10", "198.51.100.25", "203.0.113.77"]
        ), detection_expected=False, note="RFC 5737 documentation range")
    if entity_type in ("internal_hostname", "internal_dns_name", "database_endpoint"):
        return Entity("lookalike", "public_domain", "docs.example.org",
                      detection_expected=False, note="reserved example domain")
    if entity_type in ("internal_url",):
        return Entity("lookalike", "public_domain", "https://www.example.org/help",
                      detection_expected=False, note="public documentation URL")
    return Entity("lookalike", "example_identifier", f"EXAMPLE-{rng.randint(1000, 9999)}",
                  detection_expected=False, note="non-sensitive example value")


def _english_address(rng: random.Random) -> str:
    return (
        f"{rng.randint(1, 299)} Example Road, Example District, "
        f"Bangkok {rng.randint(10000, 10999)}"
    )


def finance_checks(plan: "ScenarioPlan") -> List[dict]:
    """Cross-file financial validators over values actually rendered."""
    def values(key: str) -> List[dict]:
        return plan.observations.get(key, [])

    checks: List[dict] = []
    totals = values("finance.total")
    if len(totals) >= 2:
        distinct = {item["value"] for item in totals}
        checks.append({
            "check": "linked_amount_matches",
            "status": "passed" if len(distinct) == 1 else "failed",
            "passed": len(distinct) == 1, "evaluated_items": len(totals),
            "attachment_id": None,
            "details": {"values": [item["value"] for item in totals],
                        "attachments": [item["attachment_id"] for item in totals]},
        })
    else:
        checks.append({
            "check": "linked_amount_matches", "status": "not_applicable", "passed": False,
            "evaluated_items": 0, "attachment_id": None,
            "details": {"reason": "fewer than two rendered amounts in this bundle",
                        "observed_values": [item["value"] for item in totals]},
        })
    currencies = values("finance.currency")
    if len(currencies) >= 2:
        distinct = {item["value"] for item in currencies}
        checks.append({
            "check": "linked_currency_matches",
            "status": "passed" if len(distinct) == 1 else "failed",
            "passed": len(distinct) == 1, "evaluated_items": len(currencies),
            "attachment_id": None,
            "details": {"values": [item["value"] for item in currencies]},
        })
    else:
        checks.append({
            "check": "linked_currency_matches", "status": "not_applicable", "passed": False,
            "evaluated_items": 0, "attachment_id": None,
            "details": {"reason": "fewer than two rendered currencies in this bundle",
                        "observed_values": [item["value"] for item in currencies]},
        })
    references = values("finance.transaction_reference")
    if len(references) >= 2:
        distinct = {item["value"] for item in references}
        checks.append({
            "check": "linked_transaction_reference_matches",
            "status": "passed" if len(distinct) == 1 else "failed",
            "passed": len(distinct) == 1, "evaluated_items": len(references),
            "attachment_id": None,
            "details": {"values": [item["value"] for item in references]},
        })
    else:
        checks.append({
            "check": "linked_transaction_reference_matches", "status": "not_applicable",
            "passed": False, "evaluated_items": 0, "attachment_id": None,
            "details": {"reason": "fewer than two rendered references in this bundle",
                        "observed_values": [item["value"] for item in references]},
        })
    return checks


class ScenarioPlan:
    """Shared identities, systems and identifiers for one test case."""

    def __init__(self, scenario_id: str, rng: random.Random, org: OrgProfile,
                 pool: EntityPool, language: str, negative: bool, ambiguous: bool,
                 latin_only: bool = False, thai_date_mode: str = "be",
                 currency_mode: str = "thb") -> None:
        self.scenario_id = scenario_id
        self.rng = rng
        self.org = org
        self.pool = pool
        self.language = language
        self.negative = negative
        self.ambiguous = ambiguous
        self.latin_only = latin_only
        self.thai_date_mode = thai_date_mode
        self.currency_mode = currency_mode
        self._cache: Dict[str, Entity] = {}
        self.checks: List[dict] = []
        self.observations: Dict[str, List[dict]] = {}
        self.issue_date = "2026-03-18"
        self.payment_terms_days = rng.choice((15, 30, 45))
        self.incident_id = f"INC-2026-{rng.randint(1000, 9999):04d}"
        self.ticket_id = f"#{rng.randint(10000, 99999)}"
        self.project = rng.choice(org.projects)
        self._finance: Optional[dict] = None
        self._seed_cache()

    def _seed_cache(self) -> None:
        def seed(key: str, entity: Entity, domain: str, entity_type: str) -> None:
            if self.negative and not self.ambiguous:
                entity = safe_negative(self.rng, entity_type)
            self._cache[f"{domain}:{entity_type}:{key}"] = (
                self.latinize(entity) if self.latin_only else entity)

        seed("db_endpoint", self.org.database_endpoint, "infrastructure", "database_endpoint")
        seed("url", self.org.internal_url, "infrastructure", "internal_url")
        seed("network", self.org.private_network, "infrastructure", "private_network")
        for index, host in enumerate(self.org.hosts):
            seed(f"host_{index}", host, "infrastructure", "internal_hostname")
        for index, address in enumerate(self.org.internal_ips):
            seed(f"ip_{index}", address, "infrastructure", "internal_ipv4")

    @property
    def due_date(self) -> str:
        issue = _dt.date.fromisoformat(self.issue_date)
        return (issue + _dt.timedelta(days=self.payment_terms_days)).isoformat()

    def invoice_number(self, kind: str) -> str:
        prefix = {"invoice": "INV", "quotation": "QT", "purchase_order": "PO"}.get(kind, "DOC")
        slot = f"id:{prefix}"
        current = self._cache.get(slot)
        if current is None:
            value = f"{prefix}-2026-{self.rng.randint(1000, 9999):04d}"
            current = Entity("__id__", prefix, value, detection_expected=False)
            self._cache[slot] = current
        return current.value

    def request_id(self, index: int = 0) -> str:
        slot = f"id:request_{index}"
        current = self._cache.get(slot)
        if current is None:
            current = Entity("__id__", "request_id", f"req-{self.rng.randint(10000, 99999)}",
                             detection_expected=False)
            self._cache[slot] = current
        return current.value

    def timestamp(self, index: int = 0) -> str:
        return self.timestamp_value(index).strftime("%Y-%m-%dT%H:%M:%SZ")

    def timestamp_value(self, index: int = 0) -> _dt.datetime:
        """One monotonic timeline shared by every log and report in the case."""
        return LOG_BASE + _dt.timedelta(minutes=index * 3, seconds=index * 7)

    def format_timestamp(self, index: int, style: str = "iso") -> str:
        moment = self.timestamp_value(index)
        if style == "bracket":
            return moment.strftime("%Y/%m/%d %H:%M:%S +0000")
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    def finance(self, item_count: int = 4) -> dict:
        """Shared financial facts: an invoice and its transaction export agree."""
        if self._finance is not None:
            return self._finance
        products = list(common.PRODUCTS)
        chosen = self.rng.sample(products, k=min(item_count, len(products)))
        items = []
        for name in chosen:
            quantity = self.rng.randint(1, 8)
            unit = self.rng.randrange(1200, 18000)
            items.append({"description": name, "quantity": quantity,
                          "unit_price": unit, "line_total": quantity * unit})
        subtotal = sum(item["line_total"] for item in items)
        tax = int(round(subtotal * 0.07))
        total = subtotal + tax
        self._finance = {
            "transaction_id": self.shared("payment", "payment_transaction_reference", "txn_0").value,
            "invoice_number": self.invoice_number("invoice"),
            "currency": "THB" if self.currency_mode == "thb" else "XXX",
            "items": items,
            "subtotal": subtotal, "tax": tax, "total": total,
            "tax_rate": 0.07,
            "invoice_date": self.issue_date, "due_date": self.due_date,
            # payment_date == invoice_date: one settled transaction, not an
            # installment plan, so invoice total == transaction amount.
            "payment_date": self.issue_date,
            "payment_schedule": "single_payment",
        }
        return self._finance

    def observe(self, key: str, value, attachment_id: str, role: str) -> None:
        """Record a rendered value so cross-file agreement is checked, not assumed."""
        self.observations.setdefault(key, []).append(
            {"value": value, "attachment_id": attachment_id, "role": role})

    def shared(self, domain: str, entity_type: Optional[str] = None,
               key: Optional[str] = None) -> Entity:
        if entity_type is None:
            entity_type = entity_types(domain)[0]
        cache_key = f"{domain}:{entity_type}:{key or entity_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self.negative and not self.ambiguous:
            entity = safe_negative(self.rng, entity_type)
        elif self.ambiguous and self.rng.random() < 0.3:
            entity = safe_negative(self.rng, entity_type)
        else:
            entity = self.pool.draw(domain, entity_type)
        entity = self.latinize(entity)
        self._cache[cache_key] = entity
        return entity

    def latinize(self, entity: Entity) -> Entity:
        """Give a Latin-only renderer a linked Latin representation of the identity."""
        if entity.value.isascii():
            return entity
        canonical = entity.canonical_value or entity.value
        if entity.entity_type == "thai_name":
            value = common.romanize_thai_name(canonical)
        elif entity.entity_type == "thai_address":
            value = _english_address(self.rng)
        elif entity.entity_type == "vehicle_registration":
            value = f"{self.rng.randint(1, 9)} AB {self.rng.randint(1, 9999)}"
        elif entity.entity_type == "health_condition":
            value = self.rng.choice(["penicillin allergy", "type 2 diabetes", "asthma", "hypertension"])
        elif entity.entity_type == "sensitive_personal_data":
            value = self.rng.choice(["Buddhist", "Christian", "Muslim", "prefer not to say"])
        elif entity.entity_type == "personal_financial_info":
            value = f"monthly income THB {self.rng.randrange(18000, 120000, 500):,}"
        else:
            value = "EXAMPLE-" + common.digits(self.rng, 8)
        return Entity(entity.domain, entity.entity_type, value, valid=entity.valid,
                      detection_expected=entity.detection_expected, note=entity.note,
                      canonical_value=canonical)

    def record_check(self, name: str, status, details: dict,
                     attachment_id: Optional[str] = None,
                     evaluated_items: Optional[int] = None) -> None:
        """Structured check: passed, failed, not_applicable or not_evaluated."""
        if isinstance(status, bool):
            status = "passed" if status else "failed"
        if status not in CHECK_STATUSES:
            raise ValueError(f"invalid consistency status: {status!r}")
        if evaluated_items is None:
            evaluated_items = 1 if status in ("passed", "failed") else 0
        self.checks.append({
            "check": name,
            "status": status,
            "passed": status == "passed",
            "evaluated_items": int(evaluated_items),
            "attachment_id": attachment_id,
            "details": details,
        })


def make_scenario(test_id: str, rng: random.Random, org: OrgProfile, pool: EntityPool,
                  language: str, negative: bool, ambiguous: bool,
                  latin_only: bool = False, thai_date_mode: str = "be",
                  currency_mode: str = "thb") -> ScenarioPlan:
    return ScenarioPlan(
        scenario_id=f"SCN-{test_id.split('-')[-1]}",
        rng=rng,
        org=org,
        pool=pool,
        language=language,
        negative=negative,
        ambiguous=ambiguous,
        latin_only=latin_only,
        thai_date_mode=thai_date_mode,
        currency_mode=currency_mode,
    )
