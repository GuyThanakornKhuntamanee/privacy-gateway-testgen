"""Shared synthetic-value helpers.

Everything here is fictional.  Domains use reserved example names
(``example.com``, ``.invalid``, ``.example``), networks use RFC 1918 / RFC 5737
ranges, and credential values are built so they are non-functional.
"""

from __future__ import annotations

import base64
import json
import random
import string

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
HEX = "0123456789abcdef"

THAI_FIRST_NAMES = [
    "สมชาย", "สมหญิง", "ณัฐพล", "ปรีชา", "กมลชนก", "ศิริพร", "อารีย์",
    "วิชัย", "ธนกร", "พิมพ์ชนก", "รัตนา", "อนุชา", "จุฑามาศ", "พงศกร",
    "ลลิตา", "ธีรภัทร", "มณีรัตน์", "ชัยวัฒน์", "อรทัย", "ปิยะดา",
]
THAI_LAST_NAMES = [
    "ใจดี", "ศรีสุข", "วงศ์ไทย", "พัฒนกิจ", "รุ่งเรือง", "สายทอง",
    "สุขสวัสดิ์", "จันทร์เพ็ญ", "ธีรวงศ์", "บุญมี", "แสงทอง", "ชัยมงคล",
    "นาคสุข", "ภักดี", "อินทรีย์", "พูลสวัสดิ์", "ทองคำ", "วิริยะ",
]

EN_FIRST_NAMES = [
    "Anan", "Siriporn", "Kittipong", "Naree", "Prasert", "Chanida",
    "Wichai", "Lalita", "Thiraphat", "Maneerat", "Piyada", "Somchai",
]
EN_LAST_NAMES = [
    "Jaidee", "Srisuk", "Wongthai", "Pattanakit", "Rungruang", "Saitong",
    "Suksawat", "Chanpen", "Theerawong", "Boonmee", "Saengthong", "Chaichana",
]

ASCI_ALIASES = [
    "anan", "siriporn", "kittipong", "naree", "prasert", "chanida",
    "wichai", "lalita", "thiraphat", "maneerat", "piyada", "somchai",
]

ORGS = [
    {"name": "Nimbus Lotus", "slug": "nimbus-lotus"},
    {"name": "Siam Meridian", "slug": "siam-meridian"},
    {"name": "Aurora Teak", "slug": "aurora-teak"},
    {"name": "Kata Cloudworks", "slug": "kata-cloudworks"},
    {"name": "Mekong Byte", "slug": "mekong-byte"},
    {"name": "Lanna Systems", "slug": "lanna-systems"},
    {"name": "Orchid Vector", "slug": "orchid-vector"},
    {"name": "Bangkok Beacon", "slug": "bangkok-beacon"},
]

DEPARTMENTS = {
    "th": ["ฝ่ายการเงิน", "ฝ่ายลูกค้าสัมพันธ์", "ฝ่ายไอที", "ฝ่ายปฏิบัติการ", "ฝ่ายทรัพยากรบุคคล"],
    "en": ["Finance", "Customer Support", "IT Operations", "Platform Engineering", "People Operations"],
}

SERVICES = [
    "api", "auth", "billing", "orders", "inventory", "payments", "notify",
    "search", "reporting", "gateway", "scheduler", "warehouse",
]

PRODUCTS = [
    "Wireless Keyboard", "USB-C Dock", "Noise-cancelling Headset",
    "27-inch Monitor", "Ergonomic Chair", "Portable SSD 1TB",
    "Network Switch 24-port", "Laptop Stand", "Webcam 1080p",
]


def hexstr(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(HEX) for _ in range(n))


def digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def alnum(rng: random.Random, n: int) -> str:
    pool = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(rng.choice(pool) for _ in range(n))


def thai_person(rng: random.Random) -> str:
    return rng.choice(THAI_FIRST_NAMES) + " " + rng.choice(THAI_LAST_NAMES)


def english_person(rng: random.Random) -> str:
    return rng.choice(EN_FIRST_NAMES) + " " + rng.choice(EN_LAST_NAMES)


def email_value(rng: random.Random) -> str:
    local = rng.choice(ASCI_ALIASES) + "." + rng.choice(ASCI_ALIASES)
    if rng.random() < 0.5:
        local += str(rng.randint(1, 99))
    domain = rng.choice(["example.com", "example.org", "example.net"])
    return f"{local}@{domain}"


def luhn_check_digit(partial: str) -> str:
    total = 0
    for index, char in enumerate(reversed(partial)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def luhn_valid(number: str) -> bool:
    if not number.isdigit() or len(number) < 12:
        return False
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def thai_id_check_digit(first12: str) -> str:
    total = sum(int(d) * (13 - i) for i, d in enumerate(first12))
    return str((11 - total % 11) % 10)


def thai_id_valid(value: str) -> bool:
    cleaned = value.replace("-", "").replace(" ", "")
    if len(cleaned) != 13 or not cleaned.isdigit():
        return False
    return thai_id_check_digit(cleaned[:12]) == cleaned[12]


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def fake_jwt(rng: random.Random, subject: str = "user_example_fake") -> str:
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(
        json.dumps(
            {
                "sub": subject,
                "iss": "https://auth.example.invalid",
                "role": "demo",
                "exp": 1893456000,
            },
            separators=(",", ":"),
        ).encode()
    )
    return f"{header}.{payload}.example-fake-signature"


def fake_pem(rng: random.Random, label: str) -> str:
    body = base64.b64encode(
        b"SYNTHETIC EXAMPLE KEY - NOT A REAL PRIVATE KEY - DO NOT USE"
    ).decode("ascii")
    return f"-----BEGIN {label}-----\n{body}\n-----END {label}-----"
