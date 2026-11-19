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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..entities import EntityPool, common, entity_types
from ..models import Entity
from .org import OrgProfile


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
        self.issue_date = "2026-03-18"
        self.payment_terms_days = rng.choice((15, 30, 45))
        self.incident_id = f"INC-2026-{rng.randint(1000, 9999):04d}"
        self.ticket_id = f"#{rng.randint(10000, 99999)}"
        self.project = rng.choice(org.projects)
        self._seed_cache()

    def _seed_cache(self) -> None:
        def seed(key: str, entity: Entity, domain: str, entity_type: str) -> None:
            if self.negative and not self.ambiguous:
                entity = safe_negative(self.rng, entity_type)
            self._cache[f"{domain}:{entity_type}:{key}"] = self.latinize(entity)

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
        base = _dt.datetime(2026, 3, 18, 9, 12, tzinfo=_dt.timezone.utc)
        return (base + _dt.timedelta(minutes=index * 3, seconds=index * 7)).strftime("%Y-%m-%dT%H:%M:%SZ")

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
        """Keep Latin-only renderers free of silently mangled glyphs."""
        if not self.latin_only or entity.value.isascii():
            return entity
        if entity.entity_type == "thai_name":
            value = common.english_person(self.rng)
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
                      detection_expected=entity.detection_expected, note=entity.note)

    def record_check(self, name: str, passed: bool, details: dict,
                     attachment_id: Optional[str] = None) -> None:
        self.checks.append({
            "check": name,
            "passed": bool(passed),
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
