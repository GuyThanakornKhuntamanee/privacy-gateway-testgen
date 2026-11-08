"""Synthetic PII entity factories (Thai-first, English-supported)."""

from __future__ import annotations

import random

from ..models import Entity
from . import common


def _national_id(rng: random.Random, ctx) -> Entity:
    first12 = common.digits(rng, 12)
    value = first12 + common.thai_id_check_digit(first12)
    return Entity("pii", "thai_national_id", value)


def _name(rng: random.Random, ctx) -> Entity:
    value = common.thai_person(rng) if ctx.language != "en" else common.english_person(rng)
    return Entity("pii", "thai_name", value)


def _phone(rng: random.Random, ctx) -> Entity:
    prefix = rng.choice(["06", "08", "09"])
    value = f"{prefix}{common.digits(rng, 1)}-{common.digits(rng, 3)}-{common.digits(rng, 4)}"
    return Entity("pii", "thai_phone", value)


def _email(rng: random.Random, ctx) -> Entity:
    return Entity("pii", "email_address", common.email_value(rng))


def _address(rng: random.Random, ctx) -> Entity:
    house = f"{rng.randint(1, 299)}/{rng.randint(1, 99)}"
    moo = rng.randint(1, 12)
    soi = rng.randint(1, 40)
    road = rng.choice(["สุขุมวิท", "รัตนาธิเบศร์", "พหลโยธิน", "บางนา-ตราด", "เพชรเกษม"])
    tambon = rng.choice(["บางพลีใหญ่", "คลองตัน", "ท่าศาลา", "บางรักน้อย", "หนองปรือ"])
    amphoe = rng.choice(["บางพลี", "คลองเตย", "เมืองเชียงใหม่", "บางใหญ่", "บางละมุง"])
    province = rng.choice(["สมุทรปราการ", "เชียงใหม่", "นนทบุรี", "ชลบุรี", "ปทุมธานี"])
    postal = common.digits(rng, 5)
    value = (
        f"{house} หมู่ {moo} ซอย {soi} ถนน{road} "
        f"ตำบล{tambon} อำเภอ{amphoe} จังหวัด{province} {postal}"
    )
    return Entity("pii", "thai_address", value)


def _postal(rng: random.Random, ctx) -> Entity:
    return Entity("pii", "postal_code", common.digits(rng, 5))


def _dob(rng: random.Random, ctx) -> Entity:
    year = rng.randint(1955, 2005)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return Entity("pii", "date_of_birth", f"{year:04d}-{month:02d}-{day:02d}")


def _personal_ip(rng: random.Random, ctx) -> Entity:
    # RFC 5737 documentation range: safe to publish, used as a synthetic
    # personal device address in a customer record.
    return Entity("pii", "personal_ip_address", f"198.51.100.{rng.randint(1, 254)}")


def _gps(rng: random.Random, ctx) -> Entity:
    lat = rng.uniform(7.0, 20.0)
    lon = rng.uniform(98.0, 105.0)
    return Entity("pii", "gps_coordinates", f"{lat:.5f},{lon:.5f}")


def _vehicle(rng: random.Random, ctx) -> Entity:
    letters = "".join(rng.choice("กขคงจฉชซญฎฏฐฑฒณดตถทธนบปผพภมยรลวศษสหฬอฮ") for _ in range(rng.choice([2, 3])))
    value = f"{rng.randint(1, 9)} {letters} {rng.randint(1, 9999)}"
    return Entity("pii", "vehicle_registration", value)


def _bank_account(rng: random.Random, ctx) -> Entity:
    raw = common.digits(rng, 10)
    value = f"{raw[:3]}-{raw[3]}-{raw[4:9]}-{raw[9]}"
    return Entity("pii", "bank_account_number", value)


def _financial(rng: random.Random, ctx) -> Entity:
    amount = rng.randrange(18000, 120000, 500)
    if ctx.language == "en":
        value = f"monthly income THB {amount:,}"
    else:
        value = f"รายได้ {amount:,} บาทต่อเดือน"
    return Entity("pii", "personal_financial_info", value)


def _sensitive(rng: random.Random, ctx) -> Entity:
    if ctx.language == "en":
        value = rng.choice(["Buddhist", "Christian", "Muslim", "prefer not to say"])
    else:
        value = rng.choice(["ศาสนาพุทธ", "ศาสนาคริสต์", "ศาสนาอิสลาม", "ไม่ระบุศาสนา"])
    return Entity("pii", "sensitive_personal_data", value)


def _health(rng: random.Random, ctx) -> Entity:
    if ctx.language == "en":
        value = rng.choice(["penicillin allergy", "type 2 diabetes", "asthma", "hypertension"])
    else:
        value = rng.choice(["ภูมิแพ้เพนิซิลลิน", "เบาหวานชนิดที่ 2", "หอบหืด", "ความดันโลหิตสูง"])
    return Entity("pii", "health_condition", value)


def _patient_id(rng: random.Random, ctx) -> Entity:
    return Entity("pii", "patient_id", f"HN-{common.digits(rng, 8)}")


def _passport(rng: random.Random, ctx) -> Entity:
    return Entity("pii", "passport_number", f"AA{common.digits(rng, 7)}")


# weight, factory
GENERATORS = {
    "thai_national_id": (18, _national_id),
    "thai_name": (12, _name),
    "thai_phone": (12, _phone),
    "email_address": (10, _email),
    "thai_address": (8, _address),
    "postal_code": (5, _postal),
    "date_of_birth": (6, _dob),
    "personal_ip_address": (5, _personal_ip),
    "gps_coordinates": (5, _gps),
    "vehicle_registration": (5, _vehicle),
    "bank_account_number": (5, _bank_account),
    "personal_financial_info": (4, _financial),
    "sensitive_personal_data": (3, _sensitive),
    "health_condition": (4, _health),
    "patient_id": (3, _patient_id),
    "passport_number": (3, _passport),
}
