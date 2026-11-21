"""Coherent synthetic organisations reused within one test case.

A case never mixes unrelated fake identities.  Employees, customers, vendors,
hosts, database endpoints and project names come from one organisation profile,
so an incident report, its log and its config can refer to the same people and
machines.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..entities import EntityPool
from ..entities import common
from ..models import Entity

VENDOR_NAMES = [
    "Mekong Office Supply", "Lotus Print House", "Siam Data Logistics",
    "Northern Cloud Broker", "Andaman Support Services", "Isan Facilities",
]
PROJECT_NAMES = [
    "Project Orchid", "Project Meridian", "Project Lanna", "Project Beacon",
    "Project Kite", "Project Mango",
]
INDUSTRIES = ["retail", "logistics", "financial services", "healthcare", "software"]
ROLES = {
    "th": ["นักพัฒนาซอฟต์แวร์", "ผู้ดูแลระบบ", "เจ้าหน้าที่การเงิน", "เจ้าหน้าที่ HR", "ผู้จัดการโครงการ", "นักวิเคราะห์ข้อมูล"],
    "en": ["software engineer", "system administrator", "finance officer", "HR specialist", "project manager", "data analyst"],
}


@dataclass
class Person:
    name: Entity
    email: Entity
    phone: Entity
    address: Optional[Entity]
    national_id: Optional[Entity]
    dob: Optional[Entity]
    bank: Optional[Entity]
    role: str
    department: str

    def identity(self) -> List[Entity]:
        return [item for item in (self.name, self.email, self.phone) if item is not None]


@dataclass
class OrgProfile:
    name: str
    slug: str
    domain: str
    industry: str
    departments: List[str]
    services: List[str]
    projects: List[str]
    vendors: List[str]
    employees: List[Person]
    customers: List[Person]
    vendor_contacts: List[Person]
    hosts: List[Entity]
    internal_ips: List[Entity]
    database_endpoint: Entity
    private_network: Entity
    internal_url: Entity
    cluster: str
    bucket: str
    cost_center: str
    metadata: Dict[str, str] = field(default_factory=dict)

    def as_pool_org(self) -> dict:
        return {"name": self.name, "slug": self.slug, "domain": self.domain}


def _person(rng: random.Random, pool: EntityPool, language: str, role: str, department: str,
            with_identity: bool = True) -> Person:
    name = pool.draw("pii", "thai_name")
    email = pool.draw("pii", "email_address")
    phone = pool.draw("pii", "thai_phone")
    address = pool.draw("pii", "thai_address") if with_identity and rng.random() < 0.6 else None
    national_id = pool.draw("pii", "thai_national_id") if with_identity and rng.random() < 0.5 else None
    dob = pool.draw("pii", "date_of_birth") if with_identity and rng.random() < 0.4 else None
    bank = pool.draw("payment", "bank_account_number") if with_identity and rng.random() < 0.5 else None
    return Person(name, email, phone, address, national_id, dob, bank, role, department)


def make_org(rng: random.Random, language: str = "th", size: str = "normal") -> OrgProfile:
    base = dict(rng.choice(common.ORGS))
    slug = base["slug"]
    name = base["name"]
    industry = rng.choice(INDUSTRIES)
    org_dict = {"name": name, "slug": slug, "domain": f"{slug}.example"}
    pool = EntityPool(rng, language, org_dict)
    departments = list(common.DEPARTMENTS["th" if language == "th" else "en"])
    services = rng.sample(common.SERVICES, k=min(5, len(common.SERVICES)))
    projects = rng.sample(PROJECT_NAMES, k=3)
    vendors = rng.sample(VENDOR_NAMES, k=3)
    role_bank = ROLES["th" if language == "th" else "en"]

    employee_count = 4 if size == "small" else 6
    employees = [
        _person(rng, pool, language, role_bank[index % len(role_bank)],
                departments[index % len(departments)])
        for index in range(employee_count)
    ]
    customers = [
        _person(rng, pool, language, "customer", "external", with_identity=True)
        for _ in range(4)
    ]
    vendor_contacts = [
        _person(rng, pool, language, "vendor contact", "external", with_identity=False)
        for _ in range(2)
    ]
    hosts = [pool.draw("infrastructure", "internal_hostname") for _ in range(4)]
    internal_ips = [pool.draw("infrastructure", "internal_ipv4") for _ in range(4)]
    return OrgProfile(
        name=name,
        slug=slug,
        domain=org_dict["domain"],
        industry=industry,
        departments=departments,
        services=services,
        projects=projects,
        vendors=vendors,
        employees=employees,
        customers=customers,
        vendor_contacts=vendor_contacts,
        hosts=hosts,
        internal_ips=internal_ips,
        database_endpoint=pool.draw("infrastructure", "database_endpoint"),
        private_network=pool.draw("infrastructure", "private_network"),
        internal_url=pool.draw("infrastructure", "internal_url"),
        cluster=f"{slug}-prod",
        bucket=f"{slug}-example-data",
        cost_center=f"CC-{rng.randint(1000, 9999)}",
    )
