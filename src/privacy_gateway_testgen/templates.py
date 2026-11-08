"""Prompt templates for every requested style and domain combination.

Each template appends text and already-generated entity values to a
:class:`PromptBuilder`, so ground-truth spans are recorded during construction
instead of being guessed afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from .builder import PromptBuilder
from .entities import EntityPool
from .language import L

TemplateFn = Callable[[PromptBuilder, object, str, EntityPool, int], None]


@dataclass(frozen=True)
class Template:
    id: str
    length_class: str
    difficulty: int
    domains: Tuple[str, ...]
    structure: str
    context_complexity: str
    detection_mode: str
    negative: bool
    adversarial: bool
    contextual: bool
    rationale: str
    tags: Tuple[str, ...]
    fn: TemplateFn

    @property
    def family(self) -> str:
        return self.id


PAD_SENTENCES = [
    (
        "ข้อมูลส่วนนี้เป็นบริบทประกอบการทดสอบ ไม่มีผลต่อการตัดสินใจของระบบ",
        "This section is background context and does not affect the system decision.",
    ),
    (
        "ทีมปฏิบัติการได้ตรวจสอบบันทึกการเปลี่ยนแปลงและยืนยันว่าไม่มีผลกระทบต่อบริการ",
        "The operations team reviewed the change log and confirmed there was no service impact.",
    ),
    (
        "รายงานฉบับนี้จัดทำขึ้นเพื่อการทดสอบภายในเท่านั้น ข้อมูลทั้งหมดเป็นข้อมูลสังเคราะห์",
        "This report is for internal testing only; all data is synthetic.",
    ),
    (
        "กรุณาตรวจสอบความถูกต้องของข้อมูลก่อนนำไปใช้ในขั้นตอนถัดไป",
        "Please verify the data before using it in the next step.",
    ),
    (
        "ระบบสำรองข้อมูลทำงานตามกำหนดและไม่พบข้อผิดพลาดในช่วงเวลาที่ตรวจสอบ",
        "The backup job ran on schedule and no errors were found during the review window.",
    ),
    (
        "ผลการทดสอบก่อนหน้าอยู่ในเกณฑ์ปกติ และไม่มีการเปลี่ยนแปลงการตั้งค่าที่สำคัญ",
        "Previous test results were within the expected range and no significant configuration changed.",
    ),
]


def _t(rng, language, thai, english):
    return L(rng, language, thai, english)


def _pad(b: PromptBuilder, rng, language: str, target: int) -> None:
    """Append harmless context until the prompt reaches ``target`` characters.

    Long prompts need to be genuinely long; padding avoids overfitting the
    length label to a particular sentence bank.  Padding is never sensitive and
    is inserted before the final request so the prompt still ends with a task.
    """
    sentences = list(PAD_SENTENCES)
    rng.shuffle(sentences)
    index = 0
    while len(b.build()) < target:
        thai, english = sentences[index % len(sentences)]
        b.line(_t(rng, language, thai, english))
        index += 1
        if index % len(sentences) == 0:
            rng.shuffle(sentences)


def _heading(b: PromptBuilder, rng, language: str, thai: str, english: str) -> None:
    b.line(_t(rng, language, thai, english))
    b.line()


# --------------------------------------------------------------------------
# Short prompts (difficulty 1)
# --------------------------------------------------------------------------


def t_short_customer_check(b, rng, language, pool, density):
    entity = pool.draw("pii", rng.choice(["thai_national_id", "thai_phone", "email_address"]))
    b.text(_t(rng, language, "ช่วยตรวจข้อมูลลูกค้ารายนี้ให้หน่อย ", "Please check this customer record: "))
    b.entity(entity)
    b.text(_t(rng, language, " แล้วบอกว่าเป็นข้อมูลประเภทใด", " and tell me what kind of data it is."))


def t_short_send_api_key(b, rng, language, pool, density):
    entity = pool.draw("secrets", rng.choice(["api_key", "access_token", "refresh_token"]))
    b.text(_t(rng, language, "ส่ง credential นี้ให้โมเดลภายนอก: ", "Send this credential to the external model: "))
    b.entity(entity)


def t_short_summarize_payment(b, rng, language, pool, density):
    entity = pool.draw("payment", "payment_card_number")
    b.text(_t(rng, language, "สรุปการชำระเงินด้วยบัตร ", "Summarize payment "))
    b.entity(entity)
    b.text(_t(rng, language, " ให้หน่อย", "."))


def t_short_explain_server(b, rng, language, pool, density):
    entity = pool.draw("infrastructure", "internal_ipv4")
    b.text(_t(rng, language, "อธิบายเซิร์ฟเวอร์ภายใน ", "Explain this internal server "))
    b.entity(entity)
    b.text(_t(rng, language, " ว่าทำหน้าที่อะไร", " and what it does."))


def t_short_email_forward(b, rng, language, pool, density):
    entity = pool.draw("pii", "email_address")
    b.text(_t(rng, language, "ส่งต่ออีเมลนี้ให้ vendor: ", "Forward this email to the vendor: "))
    b.entity(entity)


def t_short_gps(b, rng, language, pool, density):
    entity = pool.draw("pii", "gps_coordinates")
    b.text(_t(rng, language, "ลูกค้าอยู่ที่พิกัด ", "The customer is at "))
    b.entity(entity)
    b.text(_t(rng, language, " ช่วยหาสาขาที่ใกล้ที่สุด", ". Find the nearest branch."))


def t_short_negative_order(b, rng, language, pool, density):
    entity = pool.draw_lookalike("order_id")
    b.text(_t(rng, language, "สถานะคำสั่งซื้อ ", "What is the status of order "))
    b.entity(entity)
    b.text(_t(rng, language, " เป็นอย่างไร", "?"))


def t_short_negative_placeholder(b, rng, language, pool, density):
    entity = pool.draw_lookalike("placeholder_secret")
    b.text(_t(rng, language, "ตั้งค่า API_KEY=", "Set API_KEY="))
    b.entity(entity)
    b.text(_t(rng, language, " ในไฟล์ .env", " in the .env file."))


def t_short_negative_public_ip(b, rng, language, pool, density):
    entity = pool.draw_lookalike("public_ip_address")
    b.text(_t(rng, language, "ทำไม ", "Why does "))
    b.entity(entity)
    b.text(_t(rng, language, " ถึงตอบ ping ได้", " respond to ping?"))


# --------------------------------------------------------------------------
# Medium prompts (difficulties 2-4)
# --------------------------------------------------------------------------


def t_medium_support_ticket(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    phone = pool.draw("pii", "thai_phone")
    b.line(_t(rng, language, "จาก: support@example.com", "From: support@example.com"))
    b.line(_t(rng, language, "เรื่อง: คำสั่งซื้อล่าช้า", "Subject: delayed order"))
    b.line()
    b.text(_t(rng, language, "ลูกค้า ", "Customer "))
    b.entity(name)
    b.text(_t(rng, language, " โทรศัพท์ ", " phone "))
    b.entity(phone)
    b.text(
        _t(
            rng,
            language,
            " แจ้งว่าได้รับสินค้าไม่ครบและต้องการให้ติดต่อกลับภายในวันนี้",
            " reports that the order arrived incomplete and asks for a callback today.",
        )
    )
    b.line()
    if density >= 2:
        national_id = pool.draw("pii", "thai_national_id")
        b.text(_t(rng, language, "เลขบัตรประชาชนที่ให้ไว้คือ ", "The national ID provided is "))
        b.entity(national_id)
        b.line()
    b.line(
        _t(
            rng,
            language,
            "ช่วยร่างคำตอบกลับลูกค้าอย่างสุภาพและสรุปขั้นตอนถัดไปให้ชัดเจน",
            "Draft a polite reply and clearly summarize the next steps.",
        )
    )


def t_medium_payment_verify(b, rng, language, pool, density):
    card = pool.draw("payment", "payment_card_number")
    expiry = pool.draw("payment", "card_expiry_date")
    cvv = pool.draw("payment", "card_verification_value")
    txn = pool.draw("payment", "payment_transaction_reference")
    holder = pool.draw("payment", "cardholder_name")
    auth = pool.draw("payment", "payment_authorization_code")
    b.line(_t(rng, language, "ลูกค้าแจ้งว่าชำระเงินไม่สำเร็จและขอให้ตรวจสอบรายการ", "A customer reports a failed payment and asks us to verify the transaction."))
    b.line()
    b.text(_t(rng, language, "ชื่อผู้ถือบัตร: ", "Cardholder: "))
    b.entity(holder)
    b.line()
    b.text(_t(rng, language, "บัตร: ", "Card: "))
    b.entity(card)
    b.line()
    b.text(_t(rng, language, "วันหมดอายุ: ", "Expiry: "))
    b.entity(expiry)
    b.line()
    b.text(_t(rng, language, "CVV: ", "CVV: "))
    b.entity(cvv)
    b.line()
    b.text(_t(rng, language, "รหัสธุรกรรม: ", "Transaction reference: "))
    b.entity(txn)
    b.line()
    b.text(_t(rng, language, "รหัสอนุมัติ: ", "Authorization code: "))
    b.entity(auth)
    b.line()
    b.line(_t(rng, language, "ช่วยตรวจสอบว่าข้อมูลใดควรถูกปกปิดก่อนส่งต่อให้ทีมภายนอก", "Identify which fields must be protected before sharing with the external team."))


def t_medium_debug_log(b, rng, language, pool, density):
    token = pool.draw("secrets", rng.choice(["jwt_token", "api_key", "access_token"]))
    b.line(_t(rng, language, "ระบบแจ้ง error ขณะเรียก API ภายนอก ช่วยวิเคราะห์ log ต่อไปนี้:", "The system reported an error calling an external API. Analyze this log:"))
    b.line()
    b.line("```text")
    b.line("2026-03-14T09:12:44Z INFO  request_id=req-8841 upstream=api.example.invalid")
    b.line("2026-03-14T09:12:44Z DEBUG authorization header present")
    b.line("2026-03-14T09:12:45Z ERROR status=401 message=upstream rejected credential")
    b.text("Authorization: Bearer ")
    b.entity(token)
    b.line()
    b.line("```")
    b.line()
    b.line(_t(rng, language, "ข้อความ error บอกอะไร และควรเริ่มแก้จากจุดใด", "What does the error mean and where should debugging start?"))


def t_medium_sysadmin(b, rng, language, pool, density):
    host = pool.draw("infrastructure", "internal_hostname")
    ip = pool.draw("infrastructure", "internal_ipv4")
    endpoint = pool.draw("infrastructure", "database_endpoint")
    b.line(_t(rng, language, "ผู้ดูแลระบบขอความช่วยเหลือเรื่องเซิร์ฟเวอร์ภายใน", "An administrator needs help with an internal server."))
    b.line()
    b.text(_t(rng, language, "โฮสต์ ", "Host "))
    b.entity(host)
    b.text(_t(rng, language, " อยู่ที่ ", " is at "))
    b.entity(ip)
    b.line()
    b.text(_t(rng, language, "ฐานข้อมูลหลักคือ ", "The primary database is "))
    b.entity(endpoint)
    b.line()
    b.line(_t(rng, language, "บริการเชื่อมต่อช้าเฉพาะช่วงเช้า ช่วยเสนอวิธีตรวจสอบเบื้องต้นโดยไม่เปิดเผยข้อมูลภายใน", "Connections are slow only in the morning. Suggest initial checks without exposing internal details."))


def t_medium_summarize_email(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    email = pool.draw("pii", "email_address")
    phone = pool.draw("pii", "thai_phone")
    b.line(_t(rng, language, "ช่วยสรุปอีเมลด้านล่างและระบุสิ่งที่ต้องดำเนินการต่อ", "Summarize the email below and list the required follow-ups."))
    b.line()
    b.line("> " + _t(rng, language, "เรียนทีมบริการลูกค้า", "Dear Customer Support,"))
    b.line("> ")
    b.text("> " + _t(rng, language, "ดิฉัน ", "I am "))
    b.entity(name)
    b.text(_t(rng, language, " ติดต่อเรื่องการคืนสินค้า โทร ", " and I am writing about a return. My phone is "))
    b.entity(phone)
    b.line()
    b.text("> " + _t(rng, language, "อีเมลติดต่อกลับคือ ", "My contact email is "))
    b.entity(email)
    b.line()
    b.line("> " + _t(rng, language, "ขอบคุณ", "Thank you,"))
    b.line()
    b.line(_t(rng, language, "ต้องการคำตอบสั้น ๆ ไม่เกิน 5 ข้อ", "Keep the response to at most five bullet points."))


def t_medium_json_payload(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    national_id = pool.draw("pii", "thai_national_id")
    email = pool.draw("pii", "email_address")
    card = pool.draw("payment", "payment_card_number")
    expiry = pool.draw("payment", "card_expiry_date")
    txn = pool.draw("payment", "payment_transaction_reference")
    payment_token = pool.draw("payment", "payment_token")
    b.line(_t(rng, language, "ตรวจสอบ payload นี้ก่อนส่งไปยังผู้ให้บริการภายนอก", "Review this payload before sending it to an external provider."))
    b.line()
    b.line("```json")
    b.line("{")
    b.line('  "customer": {')
    b.text('    "name": "')
    b.entity(name)
    b.line('",')
    b.text('    "national_id": "')
    b.entity(national_id)
    b.line('",')
    b.text('    "email": "')
    b.entity(email)
    b.line('"')
    b.line("  },")
    b.line('  "payment": {')
    b.text('    "card": "')
    b.entity(card)
    b.line('",')
    b.text('    "expiry": "')
    b.entity(expiry)
    b.line('",')
    b.text('    "transaction": "')
    b.entity(txn)
    b.line('",')
    b.text('    "token": "')
    b.entity(payment_token)
    b.line('"')
    b.line("  }")
    b.line("}")
    b.line("```")
    b.line()
    b.line(_t(rng, language, "ระบุว่าฟิลด์ใดเป็นข้อมูลส่วนบุคคล ข้อมูลชำระเงิน หรือทั้งสองอย่าง", "State which fields are personal data, payment data, or both."))
    b.line(_t(rng, language, "ตอบเป็นขั้นตอน: 1) ระบุฟิลด์ข้อมูลส่วนบุคคล 2) ระบุฟิลด์ข้อมูลชำระเงิน 3) เสนอ action ที่เหมาะสมสำหรับแต่ละฟิลด์", "Answer in steps: 1) list personal-data fields 2) list payment-data fields 3) recommend an appropriate action for each field."))


def t_medium_table(b, rng, language, pool, density):
    rows = 2 + min(density, 2)
    b.line(_t(rng, language, "ตารางลูกค้าต่อไปนี้ถูกส่งมาจากทีมขาย ช่วยตรวจสอบว่ามีข้อมูลอ่อนไหวใดบ้าง", "The sales team sent this customer table. Identify any sensitive data."))
    b.line()
    b.line("| # | " + _t(rng, language, "ชื่อ", "Name") + " | " + _t(rng, language, "โทรศัพท์", "Phone") + " | Email | " + _t(rng, language, "เลขบัตรประชาชน", "National ID") + " |")
    b.line("|---|---|---|---|---|")
    for index in range(1, rows + 1):
        name = pool.draw("pii", "thai_name")
        phone = pool.draw("pii", "thai_phone")
        email = pool.draw("pii", "email_address")
        national_id = pool.draw("pii", "thai_national_id")
        b.text(f"| {index} | ")
        b.entity(name)
        b.text(" | ")
        b.entity(phone)
        b.text(" | ")
        b.entity(email)
        b.text(" | ")
        b.entity(national_id)
        b.line(" |")
    b.line()
    b.line(_t(rng, language, "สรุปเป็นรายการและเตือนว่าข้อมูลใดไม่ควรถูกส่งออกภายนอก", "Summarize the findings and flag data that should not leave the organisation."))


def t_medium_email_signature(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    phone = pool.draw("pii", "thai_phone")
    email = pool.draw("pii", "email_address")
    b.line(_t(rng, language, "ตรวจสอบอีเมลและลายเซ็นด้านล่าง แล้วระบุข้อมูลติดต่อส่วนบุคคล", "Review the email and signature below and identify personal contact data."))
    b.line()
    b.line("Subject: " + _t(rng, language, "นัดประชุมสัปดาห์หน้า", "Meeting next week"))
    b.line()
    b.line(_t(rng, language, "เรียนทีมที่เกี่ยวข้อง ตามที่ได้คุยกันเมื่อวานนี้ ขอยืนยันวันประชุมเดิมและส่งวาระประกอบ", "Hello team, following yesterday's call I confirm the original meeting date and attach the agenda."))
    b.line()
    b.line(_t(rng, language, "ขอแสดงความนับถือ", "Best regards,"))
    b.entity(name)
    b.line()
    b.text(_t(rng, language, "โทร ", "Phone: "))
    b.entity(phone)
    b.line()
    b.text("Email: ")
    b.entity(email)
    b.line()
    b.line(_t(rng, language, "ข้อมูลใดในลายเซ็นนี้ถือเป็นข้อมูลส่วนบุคคล", "Which parts of this signature are personal data?"))


def t_medium_negative_business(b, rng, language, pool, density):
    order = pool.draw_lookalike("order_id")
    invoice = pool.draw_lookalike("invoice_number")
    amount = pool.draw_lookalike("monetary_amount")
    sku = pool.draw_lookalike("product_code")
    timestamp = pool.draw_lookalike("timestamp")
    b.line(_t(rng, language, "ช่วยสรุปรายงานยอดขายประจำสัปดาห์", "Summarize the weekly sales report."))
    b.line()
    b.text(_t(rng, language, "คำสั่งซื้อ ", "Order "))
    b.entity(order)
    b.text(_t(rng, language, " ออกใบแจ้งหนี้ ", " was invoiced as "))
    b.entity(invoice)
    b.text(_t(rng, language, " ยอดรวม ", " for a total of "))
    b.entity(amount)
    b.line(".")
    b.text(_t(rng, language, "สินค้า ", "Product "))
    b.entity(sku)
    b.text(_t(rng, language, " บันทึกเมื่อ ", " recorded at "))
    b.entity(timestamp)
    b.line(".")
    b.line(_t(rng, language, "ต้องการเฉพาะยอดรวมและจำนวนรายการ ไม่ต้องแสดงข้อมูลลูกค้า", "I only need totals and item counts; do not show customer data."))


def t_medium_negative_ambiguous(b, rng, language, pool, density):
    possible_id = pool.draw_lookalike("invalid_national_id")
    possible_card = pool.draw_lookalike("invalid_card_number")
    phone = pool.draw_lookalike("reserved_fictional_phone")
    malformed = pool.draw_lookalike("malformed_national_id")
    b.line(_t(rng, language, "ตรวจสอบรายการอ้างอิงเหล่านี้ว่าเป็นข้อมูลอ่อนไหวหรือไม่", "Check whether these reference values contain sensitive data."))
    b.line()
    b.text(_t(rng, language, "เลขคำสั่งซื้อ 13 หลัก: ", "Thirteen-digit order reference: "))
    b.entity(possible_id)
    b.line()
    b.text(_t(rng, language, "หมายเลขอ้างอิงการชำระเงิน 16 หลัก: ", "Sixteen-digit payment reference: "))
    b.entity(possible_card)
    b.line()
    b.text(_t(rng, language, "เบอร์ติดต่อสำรอง: ", "Secondary contact number: "))
    b.entity(phone)
    b.line()
    b.text(_t(rng, language, "รหัสลูกค้าที่กรอกไม่ครบ: ", "Incomplete customer identifier: "))
    b.entity(malformed)
    b.line()
    b.line(_t(rng, language, "อธิบายว่าค่าใดดูคล้ายข้อมูลส่วนบุคคลแต่ไม่ผ่านการตรวจสอบความถูกต้อง", "Explain which values look like personal data but fail validation."))


def t_medium_health(b, rng, language, pool, density):
    patient = pool.draw("pii", "patient_id")
    condition = pool.draw("pii", "health_condition")
    name = pool.draw("pii", "thai_name")
    dob = pool.draw("pii", "date_of_birth")
    b.line(_t(rng, language, "ทีมคลินิกขอให้สรุปข้อมูลผู้ป่วยเพื่อเตรียมการนัดหมาย", "The clinic team asks for a patient summary ahead of an appointment."))
    b.line()
    b.text(_t(rng, language, "ผู้ป่วย ", "Patient "))
    b.entity(name)
    b.line()
    b.text(_t(rng, language, "ไฟล์แนบ: medical_record_", "Attachment: medical_record_"))
    b.entity(patient)
    b.line(".pdf")
    b.text(_t(rng, language, "วันเกิด ", "Date of birth: "))
    b.entity(dob)
    b.line()
    b.text(_t(rng, language, "ข้อมูลสุขภาพ: ", "Health information: "))
    b.entity(condition)
    b.line()
    b.line(_t(rng, language, "ข้อมูลใดถือเป็นข้อมูลสุขภาพอ่อนไหว และควรใช้มาตรการใดก่อนส่งต่อ", "Which fields are sensitive health data, and what protection is appropriate before sharing?"))


def t_medium_env_secrets(b, rng, language, pool, density):
    api_key = pool.draw("secrets", "api_key")
    webhook = pool.draw("secrets", "webhook_secret")
    db = pool.draw("secrets", "database_credential")
    b.line(_t(rng, language, "ไฟล์ .env นี้ถูกแนบมาใน ticket ช่วยตรวจว่ามีความลับใดหลุดออกมา", "This .env file was attached to a ticket. Identify any leaked secrets."))
    b.line()
    b.line("```dotenv")
    b.text("API_KEY=")
    b.entity(api_key)
    b.line()
    b.text("WEBHOOK_SECRET=")
    b.entity(webhook)
    b.line()
    b.text("DATABASE_CREDENTIALS=")
    b.entity(db)
    b.line()
    b.line("LOG_LEVEL=info")
    b.line("```")
    b.line()
    b.line(_t(rng, language, "ระบุชนิดของความลับแต่ละรายการและแนะนำว่าต้อง rotate อะไร", "Identify each secret type and recommend what must be rotated."))


def t_medium_terraform(b, rng, language, pool, density):
    terraform = pool.draw("infrastructure", "terraform_configuration")
    host = pool.draw("infrastructure", "internal_hostname")
    ip = pool.draw("infrastructure", "internal_ipv4")
    b.line(_t(rng, language, "ตรวจสอบ Terraform ต่อไปนี้ก่อนนำไปใช้ในสภาพแวดล้อมจริง", "Review this Terraform before it is applied to a real environment."))
    b.line()
    b.line("```hcl")
    b.entity(terraform)
    b.line()
    b.line("```")
    b.line()
    b.text(_t(rng, language, "แอปพลิเคชันจะรันบน ", "The application will run on "))
    b.entity(host)
    b.text(_t(rng, language, " ซึ่งอยู่ใน subnet ", " in subnet "))
    b.entity(ip)
    b.line()
    b.line(_t(rng, language, "มีข้อมูลโครงสร้างพื้นฐานใดบ้างที่ถูกเปิดเผยในข้อความนี้", "What infrastructure details are exposed in this prompt?"))


# --------------------------------------------------------------------------
# Long prompts (difficulties 4-5)
# --------------------------------------------------------------------------


def t_long_enterprise_report(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    national_id = pool.draw("pii", "thai_national_id")
    phone = pool.draw("pii", "thai_phone")
    address = pool.draw("pii", "thai_address")
    card = pool.draw("payment", "payment_card_number")
    expiry = pool.draw("payment", "card_expiry_date")
    txn = pool.draw("payment", "payment_transaction_reference")
    email = pool.draw("pii", "email_address")

    _heading(b, rng, language, "รายงานสรุปปฏิบัติการไตรมาส 1/2569", "Quarterly Operations Report Q1/2026")
    b.line(_t(rng, language, "ภาพรวม: ทีมปฏิบัติการได้ปิดรายการร้องเรียนหลักและปรับปรุงขั้นตอนการติดต่อลูกค้า เอกสารนี้ใช้สำหรับการทดสอบระบบภายในเท่านั้น", "Overview: the operations team closed the main complaint queue and improved the customer contact workflow. This document is for internal system testing only."))
    b.line()
    _heading(b, rng, language, "กรณีลูกค้า", "Customer case")
    b.text(_t(rng, language, "ลูกค้า ", "Customer "))
    b.entity(name)
    b.text(_t(rng, language, " เลขบัตรประชาชน ", " national ID "))
    b.entity(national_id)
    b.line()
    b.text(_t(rng, language, "ที่อยู่สำหรับจัดส่ง ", "Shipping address: "))
    b.entity(address)
    b.line()
    b.text(_t(rng, language, "เบอร์ติดต่อ ", "Contact phone: "))
    b.entity(phone)
    b.text(_t(rng, language, " อีเมล ", " email "))
    b.entity(email)
    b.line()
    b.line()
    _heading(b, rng, language, "รายการชำระเงิน", "Payment record")
    b.text(_t(rng, language, "ลูกค้าชำระด้วยบัตร ", "The customer paid with card "))
    b.entity(card)
    b.text(_t(rng, language, " หมดอายุ ", " expiring "))
    b.entity(expiry)
    b.line()
    b.text(_t(rng, language, "รหัสธุรกรรม ", "Transaction reference: "))
    b.entity(txn)
    b.line()
    b.line(_t(rng, language, "ยอดชำระตรงกับใบแจ้งหนี้และไม่มีการร้องขอคืนเงินในรอบนี้", "The amount matches the invoice and no refund was requested in this cycle."))
    b.line()
    _pad(b, rng, language, 900)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ช่วยสรุปรายงานนี้สำหรับผู้บริหาร โดยระบุข้อมูลที่ต้องปิดก่อนส่งออกภายนอก และแยกประเภทข้อมูลส่วนบุคคลกับข้อมูลการชำระเงินให้ชัดเจน", "Summarize this report for executives, list what must be protected before external sharing, and separate personal data from payment data."))


def t_long_chat_transcript(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    phone = pool.draw("pii", "thai_phone")
    national_id = pool.draw("pii", "thai_national_id")
    email = pool.draw("pii", "email_address")
    address = pool.draw("pii", "thai_address")

    _heading(b, rng, language, "บันทึกการสนทนากับลูกค้า", "Customer chat transcript")
    b.line(_t(rng, language, "ช่องทาง: แชทบนเว็บไซต์ | วันที่: 14 มีนาคม 2569", "Channel: website chat | Date: 14 March 2026"))
    b.line()
    b.text("09:12 " + _t(rng, language, "ลูกค้า: สวัสดีค่ะ ดิฉันชื่อ ", "Customer: Hello, my name is "))
    b.entity(name)
    b.line()
    b.text("09:13 " + _t(rng, language, "ลูกค้า: เบอร์ติดต่อ ", "Customer: My phone number is "))
    b.entity(phone)
    b.line()
    b.line("09:14 " + _t(rng, language, "เจ้าหน้าที่: สวัสดีค่ะ ขอเลขบัตรประชาชนเพื่อค้นหาใบสั่งซื้อ", "Agent: Hello, may I have your national ID to look up the order?"))
    b.text("09:15 " + _t(rng, language, "ลูกค้า: ", "Customer: "))
    b.entity(national_id)
    b.line()
    b.text("09:16 " + _t(rng, language, "ลูกค้า: อีเมล ", "Customer: My email is "))
    b.entity(email)
    b.line()
    b.text("09:18 " + _t(rng, language, "เจ้าหน้าที่: พบรายการแล้วค่ะ ที่อยู่จัดส่งคือ ", "Agent: I found the record. The shipping address is "))
    b.entity(address)
    b.line()
    b.line("09:20 " + _t(rng, language, "ลูกค้า: ต้องการเปลี่ยนที่อยู่และขอให้ยืนยันทางอีเมลภายในวันนี้", "Customer: I need to change the address and want email confirmation today."))
    b.line("09:21 " + _t(rng, language, "เจ้าหน้าที่: รับทราบค่ะ จะส่งเรื่องให้ทีมดำเนินการ", "Agent: Understood. I will forward this to the handling team."))
    b.line()
    _pad(b, rng, language, 900)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ช่วยสรุปประเด็นสำคัญของบทสนทนา ระบุข้อมูลส่วนบุคคลทั้งหมด และเสนอวิธีปกปิดข้อมูลก่อนเก็บถาวร", "Summarize the key points, identify all personal data, and propose how to protect it before archival."))


def t_long_meeting_notes(b, rng, language, pool, density):
    api_key = pool.draw("secrets", "api_key")
    connection = pool.draw("secrets", "connection_string")
    host = pool.draw("infrastructure", "internal_hostname")
    ip = pool.draw("infrastructure", "internal_ipv4")
    endpoint = pool.draw("infrastructure", "database_endpoint")
    firewall = pool.draw("infrastructure", "firewall_rule")

    _heading(b, rng, language, "บันทึกการประชุมทีมแพลตฟอร์ม", "Platform Team Meeting Notes")
    b.line(_t(rng, language, "ผู้เข้าร่วม: ทีมแพลตฟอร์ม ฝ่ายความปลอดภัย และตัวแทนผู้ดูแลระบบ", "Attendees: platform team, security office, and system administrators."))
    b.line()
    _heading(b, rng, language, "สถานะระบบ", "System status")
    b.text(_t(rng, language, "เซิร์ฟเวอร์ ", "Server "))
    b.entity(host)
    b.text(_t(rng, language, " อยู่ที่ ", " is at "))
    b.entity(ip)
    b.line()
    b.text(_t(rng, language, "ฐานข้อมูล ", "Database "))
    b.entity(endpoint)
    b.line(_t(rng, language, " มี latency เพิ่มขึ้นในช่วงเช้า แต่ยังอยู่ในเกณฑ์ที่ยอมรับได้", " showed higher latency in the morning but stayed within the accepted range."))
    b.line()
    _heading(b, rng, language, "การเปลี่ยนแปลงที่ต้องอนุมัติ", "Changes awaiting approval")
    b.text(_t(rng, language, "ต้องหมุน API key ", "The API key "))
    b.entity(api_key)
    b.text(_t(rng, language, " และตรวจสอบ connection string ", " must be rotated, and the connection string "))
    b.entity(connection)
    b.line(_t(rng, language, " ก่อนเปิดใช้บริการใหม่", " must be checked before the new service goes live."))
    b.line()
    b.text(_t(rng, language, "ไฟร์วอลล์มีกฎใหม่: ", "Firewall change: "))
    b.entity(firewall)
    b.line()
    b.line(_t(rng, language, "Action items: 1) หมุน credential 2) ตรวจสอบ routing 3) อัปเดตเอกสาร 4) นัดทบทวนสัปดาห์หน้า", "Action items: 1) rotate credentials 2) verify routing 3) update documentation 4) schedule a review next week."))
    b.line()
    _pad(b, rng, language, 950)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "สรุปบันทึกนี้และระบุความลับกับรายละเอียดโครงสร้างพื้นฐานที่ต้องถูกจำกัดก่อนแชร์ให้ทีมภายนอก", "Summarize the notes and identify secrets and infrastructure details that must be restricted before sharing externally."))


def t_long_architecture_doc(b, rng, language, pool, density):
    host = pool.draw("infrastructure", "internal_hostname")
    url = pool.draw("infrastructure", "internal_url")
    ip = pool.draw("infrastructure", "internal_ipv4")
    endpoint = pool.draw("infrastructure", "database_endpoint")
    connection = pool.draw("secrets", "connection_string")
    cloud_key = pool.draw("secrets", "cloud_access_key")
    cloud_id = pool.draw("infrastructure", "cloud_resource_id")

    _heading(b, rng, language, "เอกสารสถาปัตยกรรมระบบ", "System Architecture Document")
    b.line(_t(rng, language, "ระบบนี้ให้บริการผ่าน API ภายในและเชื่อมต่อกับฐานข้อมูลส่วนกลาง เอกสารใช้สำหรับการทดสอบการออกแบบและตรวจสอบเส้นทางข้อมูล", "The system exposes internal APIs and connects to a central database. This document supports design testing and data-flow review."))
    b.line()
    _heading(b, rng, language, "องค์ประกอบหลัก", "Core components")
    b.text(_t(rng, language, "บริการหลักทำงานบน ", "The main service runs on "))
    b.entity(host)
    b.text(_t(rng, language, " และเปิดให้เข้าถึงผ่าน ", " and is reachable at "))
    b.entity(url)
    b.line()
    b.text(_t(rng, language, "โหนดแอปพลิเคชันอยู่ใน subnet ", "Application nodes sit in subnet "))
    b.entity(ip)
    b.text(_t(rng, language, " และเชื่อมต่อกับ ", " and connect to "))
    b.entity(endpoint)
    b.line(".")
    b.text(_t(rng, language, "สตริงการเชื่อมต่อที่ใช้ในสภาพแวดล้อมทดสอบคือ ", "The test environment connection string is "))
    b.entity(connection)
    b.line()
    b.line()
    _heading(b, rng, language, "ทรัพยากรคลาวด์", "Cloud resources")
    b.text(_t(rng, language, "ระบบใช้ access key ", "The system uses access key "))
    b.entity(cloud_key)
    b.text(_t(rng, language, " สำหรับทรัพยากร ", " for resource "))
    b.entity(cloud_id)
    b.line()
    b.line(_t(rng, language, "ควรตรวจสอบสิทธิ์ขั้นต่ำและแยกบัญชีบริการตามหน้าที่", "Verify least privilege and separate service accounts by function."))
    b.line()
    _pad(b, rng, language, 950)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ช่วยทบทวนสถาปัตยกรรมนี้ ระบุข้อมูลโครงสร้างพื้นฐานและความลับที่ปรากฏ และเสนอแนวทางลดการเปิดเผยข้อมูลเมื่อต้องส่งเอกสารให้ผู้ตรวจสอบภายนอก", "Review this architecture, identify infrastructure details and secrets, and propose how to reduce exposure when sharing with an external auditor."))


def t_long_log_export(b, rng, language, pool, density):
    email = pool.draw("pii", "email_address")
    national_id = pool.draw("pii", "thai_national_id")
    ip1 = pool.draw("infrastructure", "internal_ipv4")
    host = pool.draw("infrastructure", "internal_hostname")
    token = pool.draw("secrets", "access_token")
    api_key = pool.draw("secrets", "api_key")
    jwt = pool.draw("secrets", "jwt_token")

    _heading(b, rng, language, "ไฟล์ log ที่ export จากระบบ", "Exported system log")
    b.line(_t(rng, language, "ทีมตอบสนองเหตุการณ์ต้องการให้วิเคราะห์ log ต่อไปนี้จากเหตุการณ์เมื่อคืน", "The incident response team needs the following log analysed after last night's event."))
    b.line()
    b.line("```text")
    b.line("2026-03-14T01:02:11Z INFO  gateway started pid=4412")
    b.text("2026-03-14T01:03:02Z INFO  auth user=")
    b.entity(email)
    b.line(" result=ok")
    b.text("2026-03-14T01:03:07Z DEBUG customer_profile national_id=")
    b.entity(national_id)
    b.line(" source=crm")
    b.text("2026-03-14T01:04:15Z INFO  request routed to ")
    b.entity(ip1)
    b.line()
    b.text("2026-03-14T01:04:20Z INFO  upstream host=")
    b.entity(host)
    b.line(" status=200")
    b.text("2026-03-14T01:05:33Z WARN  outbound token=")
    b.entity(token)
    b.line()
    b.text("2026-03-14T01:06:01Z ERROR provider rejected api_key=")
    b.entity(api_key)
    b.line()
    b.text("2026-03-14T01:06:44Z DEBUG session jwt=")
    b.entity(jwt)
    b.line()
    b.line("2026-03-14T01:07:10Z INFO  fallback cache enabled ttl=300")
    b.line("```")
    b.line()
    _pad(b, rng, language, 1000)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ช่วยหา root cause และระบุว่าบรรทัดใดมีข้อมูลส่วนบุคคล ความลับ หรือรายละเอียดโครงสร้างพื้นฐาน พร้อมอธิบายความเสี่ยงหาก log นี้ถูกส่งออกภายนอกโดยไม่ปกปิด", "Find the root cause and identify which lines contain personal data, secrets, or infrastructure details. Explain the risk if this log leaves the organisation unredacted."))


def t_long_sql_dump(b, rng, language, pool, density):
    name1 = pool.draw("pii", "thai_name")
    name2 = pool.draw("pii", "thai_name")
    id1 = pool.draw("pii", "thai_national_id")
    id2 = pool.draw("pii", "thai_national_id")
    email1 = pool.draw("pii", "email_address")
    email2 = pool.draw("pii", "email_address")
    card = pool.draw("payment", "payment_card_number")
    expiry = pool.draw("payment", "card_expiry_date")
    txn = pool.draw("payment", "payment_transaction_reference")

    _heading(b, rng, language, "ตัวอย่างข้อมูลจากฐานข้อมูลสำหรับทดสอบ", "Sample database export for testing")
    b.line(_t(rng, language, "ไฟล์ SQL นี้เป็นข้อมูลสังเคราะห์จากสภาพแวดล้อมทดสอบ ใช้ตรวจสอบว่าคำสั่งวิเคราะห์ใดปลอดภัย", "This SQL file contains synthetic test-environment data. Use it to check which analysis queries are safe."))
    b.line()
    b.line("```sql")
    b.line("CREATE TABLE customers (id INT, full_name VARCHAR(120), national_id CHAR(13), email VARCHAR(120));")
    b.line("CREATE TABLE payments (id INT, card_number VARCHAR(19), expiry CHAR(5), txn_ref VARCHAR(24));")
    b.text("INSERT INTO customers VALUES (1, '")
    b.entity(name1)
    b.text("', '")
    b.entity(id1)
    b.text("', '")
    b.entity(email1)
    b.line("');")
    b.text("INSERT INTO customers VALUES (2, '")
    b.entity(name2)
    b.text("', '")
    b.entity(id2)
    b.text("', '")
    b.entity(email2)
    b.line("');")
    b.text("INSERT INTO payments VALUES (1, '")
    b.entity(card)
    b.text("', '")
    b.entity(expiry)
    b.text("', '")
    b.entity(txn)
    b.line("');")
    b.line("```")
    b.line()
    _pad(b, rng, language, 950)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "เขียนคำสั่ง SQL ที่สรุปยอดชำระโดยไม่เปิดเผยเลขบัตรหรือข้อมูลส่วนบุคคล และระบุว่าคอลัมน์ใดต้องถูกปกปิดก่อนแชร์ผลลัพธ์", "Write a SQL query that summarizes payments without exposing card numbers or personal data, and state which columns must be protected before sharing results."))


def t_long_k8s_manifest(b, rng, language, pool, density):
    host = pool.draw("infrastructure", "internal_hostname")
    ip = pool.draw("infrastructure", "internal_ipv4")
    endpoint = pool.draw("infrastructure", "database_endpoint")
    api_key = pool.draw("secrets", "api_key")
    connection = pool.draw("secrets", "connection_string")

    _heading(b, rng, language, "ไฟล์ Manifest สำหรับตรวจสอบก่อน deploy", "Manifest review before deployment")
    b.line(_t(rng, language, "ทีมแพลตฟอร์มขอให้ตรวจสอบ YAML นี้และระบุข้อมูลที่ไม่ควรอยู่ใน source control", "The platform team asks for a review of this YAML and a list of data that should not be in source control."))
    b.line()
    b.line("```yaml")
    b.line("apiVersion: v1")
    b.line("kind: Secret")
    b.line("metadata:")
    b.line("  name: app-secrets")
    b.line("  namespace: example-prod")
    b.line("stringData:")
    b.text("  API_KEY: \"")
    b.entity(api_key)
    b.line("\"")
    b.text("  DATABASE_URL: \"")
    b.entity(connection)
    b.line("\"")
    b.line("---")
    b.line("apiVersion: apps/v1")
    b.line("kind: Deployment")
    b.line("metadata:")
    b.line("  name: orders-api")
    b.line("spec:")
    b.line("  replicas: 3")
    b.line("  template:")
    b.line("    spec:")
    b.line("      containers:")
    b.line("      - name: api")
    b.text("        image: registry.")
    b.entity(host)
    b.line("/platform/orders-api:1.4.2")
    b.text("        hostAliases:")
    b.line("        - ip: ")
    b.entity(ip)
    b.text("          hostnames: [\"")
    b.entity(endpoint)
    b.line("\"]")
    b.line("```")
    b.line()
    _pad(b, rng, language, 950)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ระบุความลับและรายละเอียดโครงสร้างพื้นฐานใน manifest นี้ พร้อมเสนอวิธีใช้ secret manager แทนการฝังค่าโดยตรง", "Identify the secrets and infrastructure details in this manifest and propose using a secret manager instead of embedding values."))


def t_long_all_four(b, rng, language, pool, density):
    name = pool.draw("pii", "thai_name")
    national_id = pool.draw("pii", "thai_national_id")
    phone = pool.draw("pii", "thai_phone")
    card = pool.draw("payment", "payment_card_number")
    txn = pool.draw("payment", "payment_transaction_reference")
    api_key = pool.draw("secrets", "api_key")
    ssh_key = pool.draw("secrets", "ssh_private_key")
    ip = pool.draw("infrastructure", "internal_ipv4")
    host = pool.draw("infrastructure", "internal_hostname")
    endpoint = pool.draw("infrastructure", "database_endpoint")

    _heading(b, rng, language, "รายงานเหตุการณ์ความปลอดภัย", "Security Incident Report")
    b.line(_t(rng, language, "เหตุการณ์นี้ถูกสร้างขึ้นเพื่อการทดสอบเท่านั้น ข้อมูลทั้งหมดเป็นข้อมูลสังเคราะห์", "This incident is generated for testing only. All data is synthetic."))
    b.line()
    _heading(b, rng, language, "ข้อมูลลูกค้าที่ได้รับผลกระทบ", "Affected customer")
    b.text(_t(rng, language, "ลูกค้า ", "Customer "))
    b.entity(name)
    b.text(_t(rng, language, " เลขบัตรประชาชน ", " national ID "))
    b.entity(national_id)
    b.text(_t(rng, language, " เบอร์โทร ", " phone "))
    b.entity(phone)
    b.line()
    b.line()
    _heading(b, rng, language, "รายการชำระเงิน", "Payment record")
    b.text(_t(rng, language, "บัตรที่ใช้ ", "Card used: "))
    b.entity(card)
    b.text(_t(rng, language, " รหัสธุรกรรม ", " transaction "))
    b.entity(txn)
    b.line()
    b.line()
    _heading(b, rng, language, "ความลับที่อาจรั่วไหล", "Potentially exposed secrets")
    b.text(_t(rng, language, "พบ API key ใน log: ", "An API key was found in the log: "))
    b.entity(api_key)
    b.line()
    b.line(_t(rng, language, "และพบ private key ในเครื่องที่ถูกตรวจยึด:", "A private key was also found on the seized host:"))
    b.entity(ssh_key)
    b.line()
    _heading(b, rng, language, "โครงสร้างพื้นฐานที่เกี่ยวข้อง", "Affected infrastructure")
    b.text(_t(rng, language, "เครื่องที่ได้รับผลกระทบ ", "Affected host "))
    b.entity(host)
    b.text(_t(rng, language, " อยู่ที่ ", " at "))
    b.entity(ip)
    b.text(_t(rng, language, " และเชื่อมต่อกับ ", " and connects to "))
    b.entity(endpoint)
    b.line()
    b.line()
    _pad(b, rng, language, 1100)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "จัดทำแผนตอบสนองเหตุการณ์ที่แยกข้อมูลสี่ประเภทออกจากกัน ระบุ action ที่เข้มงวดที่สุดที่ต้องใช้ และอธิบายว่าเหตุใดจึงไม่ควรส่งข้อมูลใดออกภายนอกโดยไม่มีการป้องกัน", "Produce an incident response plan that separates the four data categories, identify the strictest action that applies, and explain why no data should leave without protection."))


def t_long_negative_report(b, rng, language, pool, density):
    order1 = pool.draw_lookalike("order_id")
    order2 = pool.draw_lookalike("order_id")
    invoice = pool.draw_lookalike("invoice_number")
    amount = pool.draw_lookalike("monetary_amount")
    version = pool.draw_lookalike("version_string")
    build = pool.draw_lookalike("build_hash")
    public_ip = pool.draw_lookalike("public_ip_address")
    doc_ip = pool.draw_lookalike("documentation_ip_address")
    placeholder = pool.draw_lookalike("placeholder_secret")
    domain = pool.draw_lookalike("public_domain")
    uuid = pool.draw_lookalike("random_uuid")

    _heading(b, rng, language, "รายงานภาพรวมธุรกิจประจำสัปดาห์", "Weekly Business Overview")
    b.line(_t(rng, language, "รายงานนี้สรุปคำสั่งซื้อและสถานะการเปิดตัวซอฟต์แวร์ โดยไม่มีข้อมูลลูกค้าที่ระบุตัวบุคคล", "This report summarizes orders and software release status without identifying customers."))
    b.line()
    _heading(b, rng, language, "คำสั่งซื้อ", "Orders")
    b.text(_t(rng, language, "คำสั่งซื้อ ", "Order "))
    b.entity(order1)
    b.text(_t(rng, language, " และ ", " and "))
    b.entity(order2)
    b.text(_t(rng, language, " ออกใบแจ้งหนี้ ", " were invoiced as "))
    b.entity(invoice)
    b.text(_t(rng, language, " ยอดรวม ", " for a total of "))
    b.entity(amount)
    b.line(".")
    b.line()
    _heading(b, rng, language, "การเปิดตัวซอฟต์แวร์", "Software release")
    b.text(_t(rng, language, "เวอร์ชัน ", "Version "))
    b.entity(version)
    b.text(_t(rng, language, " สร้างจาก commit ", " was built from commit "))
    b.entity(build)
    b.text(_t(rng, language, " และตรวจสอบผ่าน ", " and verified via "))
    b.entity(domain)
    b.line(".")
    b.line()
    _heading(b, rng, language, "บันทึกโครงข่ายสาธารณะ", "Public network notes")
    b.text(_t(rng, language, "บริการสาธารณะตอบสนองที่ ", "The public service responds at "))
    b.entity(public_ip)
    b.text(_t(rng, language, " และมีตัวอย่างในเอกสารที่ ", " and documentation examples use "))
    b.entity(doc_ip)
    b.line(".")
    b.text(_t(rng, language, "ค่าตัวอย่างในคู่มือคือ ", "The manual uses the placeholder "))
    b.entity(placeholder)
    b.text(_t(rng, language, " และรหัสอ้างอิง ", " and reference "))
    b.entity(uuid)
    b.line(".")
    b.line()
    _pad(b, rng, language, 950)
    _heading(b, rng, language, "คำขอ", "Request")
    b.line(_t(rng, language, "ช่วยตรวจว่ามีข้อมูลส่วนบุคคล ข้อมูลชำระเงิน ความลับ หรือโครงสร้างพื้นฐานภายในที่ต้องปกป้องหรือไม่ ถ้าไม่มีให้ระบุว่าไม่มีและอธิบายเหตุผล", "Check whether this contains personal data, payment data, secrets, or internal infrastructure. If none is present, say so and explain why."))


TEMPLATES: List[Template] = [
    Template("short_customer_check", "short", 1, ("pii",), "unstructured", "low", "deterministic", False, False, False,
             "A single valid PII identifier in a brief request.", ("pii", "short", "single-entity"), t_short_customer_check),
    Template("short_send_api_key", "short", 1, ("secrets",), "unstructured", "low", "deterministic", False, False, False,
             "A credential is sent to an external model in a short instruction.", ("secrets", "short", "external-routing"), t_short_send_api_key),
    Template("short_summarize_payment", "short", 1, ("payment",), "unstructured", "low", "deterministic", False, False, False,
             "A payment card number in a short summarization request.", ("payment", "short"), t_short_summarize_payment),
    Template("short_explain_server", "short", 1, ("infrastructure",), "unstructured", "low", "deterministic", False, False, False,
             "An internal IPv4 address in a short operations question.", ("infrastructure", "short"), t_short_explain_server),
    Template("short_email_forward", "short", 1, ("pii",), "unstructured", "low", "deterministic", False, False, False,
             "A personal email address in a forwarding request.", ("pii", "short", "email"), t_short_email_forward),
    Template("short_gps", "short", 1, ("pii",), "unstructured", "low", "deterministic", False, False, False,
             "GPS coordinates used as personal location data.", ("pii", "short", "location"), t_short_gps),
    Template("short_negative_order", "short", 1, (), "unstructured", "low", "deterministic", True, False, False,
             "An ordinary order identifier that should not be treated as sensitive.", ("negative", "false-positive"), t_short_negative_order),
    Template("short_negative_placeholder", "short", 1, (), "unstructured", "low", "deterministic", True, False, False,
             "A placeholder value with no secret behind it.", ("negative", "placeholder"), t_short_negative_placeholder),
    Template("short_negative_public_ip", "short", 1, (), "unstructured", "low", "contextual", True, False, False,
             "A public IP address rather than internal infrastructure.", ("negative", "false-positive", "network"), t_short_negative_public_ip),

    Template("medium_support_ticket", "medium", 2, ("pii",), "email", "medium", "deterministic", False, False, True,
             "Customer support email containing name, phone and national ID.", ("pii", "email", "support"), t_medium_support_ticket),
    Template("medium_payment_verify", "medium", 2, ("payment",), "unstructured", "medium", "deterministic", False, False, False,
             "Payment verification request with card, expiry, CVV and transaction reference.", ("payment", "card", "cvv"), t_medium_payment_verify),
    Template("medium_debug_log", "medium", 3, ("secrets",), "code", "medium", "deterministic", False, False, True,
             "A bearer credential embedded in a log excerpt inside a code block.", ("secrets", "log", "contextual"), t_medium_debug_log),
    Template("medium_sysadmin", "medium", 2, ("infrastructure",), "unstructured", "medium", "deterministic", False, False, False,
             "Internal host, IP and database endpoint in an operations request.", ("infrastructure", "operations"), t_medium_sysadmin),
    Template("medium_summarize_email", "medium", 2, ("pii",), "email", "medium", "deterministic", False, False, True,
             "PII inside a quoted email, including contact details.", ("pii", "email", "quoted-text"), t_medium_summarize_email),
    Template("medium_json_payload", "medium", 3, ("pii", "payment"), "json", "high", "deterministic", False, False, True,
             "PII and payment fields inside a JSON code block.", ("pii", "payment", "json", "multi-domain"), t_medium_json_payload),
    Template("medium_table", "medium", 3, ("pii",), "table", "high", "deterministic", False, False, True,
             "Multiple PII entities inside a markdown table.", ("pii", "table", "dense"), t_medium_table),
    Template("medium_email_signature", "medium", 2, ("pii",), "email", "medium", "deterministic", False, False, True,
             "PII located in an email signature.", ("pii", "email", "signature"), t_medium_email_signature),
    Template("medium_negative_business", "medium", 2, (), "unstructured", "medium", "deterministic", True, False, False,
             "Ordinary order, invoice, amount and product identifiers.", ("negative", "business-data"), t_medium_negative_business),
    Template("medium_negative_ambiguous", "medium", 4, (), "unstructured", "high", "contextual", True, True, True,
             "Values that resemble PII or payment data but fail validation.", ("negative", "ambiguous", "adversarial"), t_medium_negative_ambiguous),
    Template("medium_health", "medium", 3, ("pii",), "unstructured", "medium", "deterministic", False, False, False,
             "Sensitive health data and patient identifier.", ("pii", "health", "sensitive"), t_medium_health),
    Template("medium_env_secrets", "medium", 3, ("secrets",), "code", "high", "deterministic", False, False, True,
             "Credentials inside a dotenv configuration block.", ("secrets", "config", "contextual"), t_medium_env_secrets),
    Template("medium_terraform", "medium", 3, ("infrastructure",), "code", "high", "deterministic", False, False, True,
             "Infrastructure-as-code snippet plus internal host and subnet details.", ("infrastructure", "terraform", "contextual"), t_medium_terraform),

    Template("long_enterprise_report", "long", 4, ("pii", "payment"), "report", "high", "deterministic", False, False, False,
             "Enterprise report combining customer PII and payment records.", ("pii", "payment", "multi-domain", "report"), t_long_enterprise_report),
    Template("long_chat_transcript", "long", 4, ("pii",), "chat", "high", "deterministic", False, False, True,
             "Multi-turn chat transcript with PII in several positions.", ("pii", "chat", "contextual"), t_long_chat_transcript),
    Template("long_meeting_notes", "long", 4, ("secrets", "infrastructure"), "markdown", "high", "deterministic", False, False, False,
             "Meeting notes mixing credentials and internal infrastructure details.", ("secrets", "infrastructure", "multi-domain"), t_long_meeting_notes),
    Template("long_architecture_doc", "long", 4, ("infrastructure", "secrets"), "markdown", "high", "deterministic", False, False, True,
             "Architecture document with internal endpoints, cloud identifiers and secrets.", ("infrastructure", "secrets", "multi-domain", "document"), t_long_architecture_doc),
    Template("long_log_export", "long", 5, ("pii", "secrets", "infrastructure"), "log", "high", "contextual", False, True, True,
             "Mixed-domain secrets, PII and network details hidden inside an exported log.", ("pii", "secrets", "infrastructure", "log", "adversarial"), t_long_log_export),
    Template("long_sql_dump", "long", 4, ("pii", "payment"), "sql", "high", "deterministic", False, False, True,
             "PII and payment data inside SQL statements.", ("pii", "payment", "sql", "structured"), t_long_sql_dump),
    Template("long_k8s_manifest", "long", 4, ("infrastructure", "secrets"), "yaml", "high", "deterministic", False, False, True,
             "Kubernetes manifest containing secrets and internal infrastructure.", ("infrastructure", "secrets", "yaml"), t_long_k8s_manifest),
    Template("long_all_four", "long", 5, ("pii", "payment", "secrets", "infrastructure"), "markdown", "high", "contextual", False, True, True,
             "All four domains in one incident report, requiring action precedence.", ("pii", "payment", "secrets", "infrastructure", "multi-domain", "adversarial"), t_long_all_four),
    Template("long_negative_report", "long", 4, (), "report", "high", "contextual", True, True, False,
             "A long report full of harmless identifiers, placeholders and public addresses.", ("negative", "long", "false-positive"), t_long_negative_report),
]


def build_draft(template: Template, rng, language: str, density: int) -> dict:
    pool = EntityPool(rng, language)
    builder = PromptBuilder()
    template.fn(builder, rng, language, pool, density)
    return {
        "prompt": builder.build(),
        "spans": builder.spans,
        "template": template,
        "org": pool.org,
    }
