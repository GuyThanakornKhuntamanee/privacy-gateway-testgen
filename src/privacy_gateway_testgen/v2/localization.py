"""Localization and Thai formatting for schema 2.1 documents.

Document builders describe business meaning in English.  This module turns a
finished ``Doc`` into Thai or genuinely mixed Thai-English content while
preserving every entity placement: only the static text between placements is
translated, never the entity values themselves.

``mixed`` means intra-document code-switching, not "a Thai name in an English
file": labels become bilingual, prose is Thai, and technical nouns such as
``config``, ``deploy`` or ``API`` stay in English.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .docmodel import Block, Cell, Doc, Placement

THAI_MONTHS = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)
THAI_MONTHS_SHORT = (
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
)
EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# Canonical English label -> Thai.  Technical keywords stay English by design.
LABELS: Dict[str, str] = {
    # people
    "name": "ชื่อ", "employee": "พนักงาน", "employee_name": "ชื่อพนักงาน",
    "customer": "ลูกค้า", "customer_name": "ชื่อลูกค้า", "customer_id": "รหัสลูกค้า",
    "contact": "ผู้ติดต่อ", "contact_email": "อีเมลผู้ติดต่อ", "owner": "ผู้รับผิดชอบ",
    "owner_email": "อีเมลผู้รับผิดชอบ", "user": "ผู้ใช้", "reporter": "ผู้แจ้ง",
    "email": "อีเมล", "phone": "เบอร์โทร", "address": "ที่อยู่",
    "national_id": "เลขบัตรประชาชน", "dob": "วันเกิด", "department": "แผนก",
    "role": "บทบาท", "position": "ตำแหน่ง", "bank_account": "บัญชีธนาคาร",
    "bank": "ธนาคาร", "tax_reference": "เลขผู้เสียภาษี", "hn": "HN",
    "patient": "ผู้ป่วย", "diagnosis": "การวินิจฉัย", "appointment": "นัดหมาย",
    "medication": "ยา", "dose": "ขนาดยา", "duration": "ระยะเวลา",
    "test": "รายการตรวจ", "result": "ผล", "reference": "อ้างอิง",
    # finance
    "gross": "เงินเดือนรวม", "tax": "ภาษี", "net": "เงินสุทธิ",
    "amount": "จำนวนเงิน", "total": "ยอดรวม", "subtotal": "ยอดรวมก่อนภาษี",
    "vat": "ภาษีมูลค่าเพิ่ม", "unit_price": "ราคาต่อหน่วย",
    "line_total": "ยอดรวมรายการ", "quantity": "จำนวน", "description": "รายการ",
    "date": "วันที่", "due_date": "วันครบกำหนด", "issue_date": "วันที่ออก",
    "status": "สถานะ", "balance": "ยอดคงเหลือ", "debit": "เดบิต",
    "credit": "เครดิต", "type": "ประเภท", "invoice": "ใบแจ้งหนี้",
    "invoice_number": "เลขที่ใบแจ้งหนี้", "customer_export": "ข้อมูลลูกค้า",
    "bill to": "เรียกเก็บเงินจาก", "due": "ครบกำหนด", "vat 7%": "ภาษีมูลค่าเพิ่ม 7%",
    "account holder": "เจ้าของบัญชี", "opening balance": "ยอดยกมา",
    "transaction reference": "อ้างอิงธุรกรรม", "card on file": "บัตรที่บันทึกไว้",
    "expiry": "วันหมดอายุ", "authorization": "รหัสอนุมัติ",
    "currency": "สกุลเงิน",
    "payment gateway key": "คีย์ payment gateway",
    "billing service endpoint": "ปลายทางบริการเรียกเก็บเงิน",
    "order_id": "เลขที่คำสั่งซื้อ", "opportunity": "โอกาสขาย",
    "stage": "ขั้นตอน", "category": "หมวด", "expense": "ค่าใช้จ่าย",
    # operations / IT
    "hostname": "ชื่อโฮสต์", "private_ip": "IP ภายใน", "source_ip": "IP ต้นทาง",
    "resource": "ทรัพยากร", "timestamp": "เวลา", "action": "การกระทำ",
    "environment": "สภาพแวดล้อม", "role_name": "บทบาท",
    "vendor": "ผู้ขาย", "contact_name": "ชื่อผู้ติดต่อ",
    "transaction_ref": "อ้างอิงธุรกรรม", "reference_number": "เลขอ้างอิง",
    "auth_code": "รหัสอนุมัติ", "card": "บัตร", "card_on_file": "บัตรที่บันทึกไว้",
    "card_expiry": "วันหมดอายุบัตร", "authorization": "การอนุมัติ",
    "failure": "ความล้มเหลว", "impact": "ผลกระทบ", "service": "บริการ",
    "request_id": "รหัสคำขอ", "incident_id": "รหัสเหตุการณ์",
    "risk": "ความเสี่ยง", "rating": "ระดับ", "timeline": "ไทม์ไลน์",
    "owner_name": "ชื่อผู้รับผิดชอบ", "summary": "สรุป",
    "action_items": "รายการที่ต้องทำ", "attendees": "ผู้เข้าร่วม",
    "decision": "ข้อสรุป", "evidence": "หลักฐาน", "location": "สถานที่",
    # spreadsheet sheets / slides
    "employees": "พนักงาน", "customers": "ลูกค้า", "transactions": "ธุรกรรม",
    "asset_assignment": "การมอบหมายทรัพย์สิน",
    "servers": "เซิร์ฟเวอร์", "employees_assets": "ทรัพย์สินพนักงาน",
    "payroll": "เงินเดือน", "items": "รายการสินค้า", "orders": "คำสั่งซื้อ",
    "expenses": "ค่าใช้จ่าย", "access_events": "เหตุการณ์การเข้าถึง",
    "vendors": "ผู้ขาย", "appointments": "นัดหมาย", "pipeline": "ไปป์ไลน์",
    "risks": "ความเสี่ยง", "results": "ผลตรวจ", "prescription": "ใบสั่งยา",
    "Asset assignment": "การมอบหมายทรัพย์สิน",
    "Revised version: one field was corrected for this synthetic scenario.":
        "ฉบับแก้ไข: มีการแก้ไขหนึ่งฟิลด์สำหรับสถานการณ์สังเคราะห์นี้",
    "scorecard": "แบบประเมิน",
    # status values
    "settled": "ชำระแล้ว", "pending": "รอดำเนินการ", "refunded": "คืนเงินแล้ว",
    "packed": "แพ็กแล้ว", "shipped": "จัดส่งแล้ว", "delivered": "ส่งถึงแล้ว",
    "qualified": "ผ่านคุณสมบัติ", "proposal": "เสนอราคา",
    "negotiation": "เจรจา", "won": "ปิดการขาย",
    "production": "โปรดักชัน", "staging": "สเตจจิง",
    "high": "สูง", "medium": "กลาง", "low": "ต่ำ",
    "strong": "ดีมาก", "good": "ดี", "developing": "ต้องพัฒนา",
    "read": "อ่าน", "write": "เขียน", "delete": "ลบ", "login": "เข้าสู่ระบบ",
    "annual": "ลาพักร้อน", "travel": "เดินทาง", "software": "ซอฟต์แวร์",
    "office": "สำนักงาน", "training": "อบรม",
    "success": "สำเร็จ", "failed": "ล้มเหลว", "started": "เริ่มแล้ว",
    "card settlement": "ชำระบัตร", "transfer": "โอนเงิน", "refund": "คืนเงิน",
    "service fee": "ค่าบริการ",
    "Credential exposure in deployment logs": "credential รั่วไหลใน log การ deploy",
    "Database failover not tested": "ยังไม่ทดสอบ failover ของฐานข้อมูล",
    "Vendor access review overdue": "การตรวจสอบสิทธิ์ผู้ขายเกินกำหนด",
    "security": "ความปลอดภัย", "platform": "แพลตฟอร์ม", "compliance": "การกำกับดูแล",
    "SQL": "SQL", "Stakeholder communication": "การสื่อสารกับผู้มีส่วนได้ส่วนเสีย",
    "Domain knowledge": "ความรู้ด้านธุรกิจ", "clear explanations": "อธิบายชัดเจน",
    "structured examples": "ยกตัวอย่างเป็นระบบ", "needs support": "ต้องสนับสนุนเพิ่ม",
    "Haemoglobin": "ฮีโมโกลบิน", "Fasting glucose": "น้ำตาลในเลือดขณะอดอาหาร",
    "Creatinine": "ครีอะตินิน",
}

TEXT_TH: Dict[str, str] = {
    # titles
    "Employee list": "รายชื่อพนักงาน",
    "Payroll register": "ทะเบียนเงินเดือน",
    "Customer export": "ข้อมูลลูกค้า",
    "Transaction export": "รายการธุรกรรม",
    "Patient appointment list": "รายการนัดผู้ป่วย",
    "Server inventory": "ทะเบียนเซิร์ฟเวอร์",
    "Sales pipeline": "ไปป์ไลน์การขาย",
    "Access records": "บันทึกการเข้าถึง",
    "Vendor list": "รายชื่อผู้ขาย",
    "Bank statement": "รายการเดินบัญชี",
    "Expense report": "รายงานค่าใช้จ่าย",
    "Order export": "ข้อมูลคำสั่งซื้อ",
    "Invoice": "ใบแจ้งหนี้",
    "Quotation": "ใบเสนอราคา",
    "Purchase order": "ใบสั่งซื้อ",
    "Employment contract": "สัญญาจ้างงาน",
    "Non-disclosure agreement": "ข้อตกลงรักษาความลับ",
    "Supplier agreement": "สัญญาผู้ขาย",
    "Customer contract": "สัญญาลูกค้า",
    "Curriculum vitae": "ประวัติย่อ",
    "Incident report": "รายงานเหตุการณ์",
    "Meeting minutes": "รายงานการประชุม",
    "Internal memo": "บันทึกข้อความภายใน",
    "Strategy report": "รายงานกลยุทธ์",
    "Risk report": "รายงานความเสี่ยง",
    "Support ticket": "ตั๋วสนับสนุน",
    "Customer complaint": "ข้อร้องเรียนลูกค้า",
    "Leave request": "ใบลาพักร้อน",
    "Candidate evaluation": "แบบประเมินผู้สมัคร",
    "Medical report": "รายงานทางการแพทย์",
    "Laboratory result": "ผลตรวจทางห้องปฏิบัติการ",
    "Prescription": "ใบสั่งยา",
    "Architecture notes": "บันทึกสถาปัตยกรรมระบบ",
    "Troubleshooting notes": "บันทึกการแก้ปัญหา",
    "Application environment": "สภาพแวดล้อมแอปพลิเคชัน",
    "Application configuration": "การตั้งค่าแอปพลิเคชัน",
    "Kubernetes deployment": "การติดตั้งบน Kubernetes",
    "Docker Compose": "Docker Compose",
    "Terraform configuration": "การตั้งค่า Terraform",
    "Database configuration": "การตั้งค่าฐานข้อมูล",
    "Service account": "บัญชีบริการ",
    "API payload": "ข้อมูล API",
    "XML export": "ข้อมูล XML",
    "SQL export": "ข้อมูล SQL",
    "Application source": "ซอร์สโค้ดแอปพลิเคชัน",
    "Application log": "บันทึกแอปพลิเคชัน",
    "Synthetic ID sample": "ตัวอย่างบัตรประชาชนสังเคราะห์",
    # headings
    "Employee directory": "รายชื่อพนักงาน",
    "Payroll register - March 2026": "ทะเบียนเงินเดือน - มีนาคม 2026",
    "Transaction export - March 2026": "รายการธุรกรรม - มีนาคม 2026",
    "Clinic appointment list - synthetic": "รายการนัดคลินิก - ข้อมูลสังเคราะห์",
    "Sales pipeline - Q1 2026": "ไปป์ไลน์การขาย - ไตรมาส 1/2026",
    "Access log export": "ส่งออกบันทึกการเข้าถึง",
    "Approved vendor list": "รายชื่อผู้ขายที่อนุมัติแล้ว",
    "Synthetic bank statement": "รายการเดินบัญชีสังเคราะห์",
    "Incident report - API authentication failures": "รายงานเหตุการณ์ - API ยืนยันตัวตนล้มเหลว",
    "Platform weekly - meeting minutes": "ประชุมแพลตฟอร์มรายสัปดาห์",
    "Internal memo - access review": "บันทึกข้อความภายใน - ตรวจสอบสิทธิ์",
    "FY2026 strategy review": "ทบทวนกลยุทธ์ปี 2026",
    "Operational risk register": "ทะเบียนความเสี่ยงด้านปฏิบัติการ",
    "Support ticket": "ตั๋วสนับสนุน",
    "Customer complaint - delayed delivery": "ข้อร้องเรียนลูกค้า - ส่งของล่าช้า",
    "Leave request form": "แบบฟอร์มขอลา",
    "Candidate evaluation": "แบบประเมินผู้สมัคร",
    "Visit summary - synthetic clinic": "สรุปการเข้ารับบริการ - คลินิกสังเคราะห์",
    "Laboratory result - synthetic": "ผลตรวจทางห้องปฏิบัติการ - ข้อมูลสังเคราะห์",
    "Prescription - synthetic": "ใบสั่งยา - ข้อมูลสังเคราะห์",
    "Order platform architecture": "สถาปัตยกรรมระบบคำสั่งซื้อ",
    "Troubleshooting notes - prod database": "บันทึกการแก้ปัญหา - ฐานข้อมูลโปรดักชัน",
    "Production environment": "สภาพแวดล้อมโปรดักชัน",
    "Application configuration": "การตั้งค่าแอปพลิเคชัน",
    "Kubernetes deployment": "การติดตั้งบน Kubernetes",
    "Docker Compose stack": "สแตก Docker Compose",
    "Terraform configuration": "การตั้งค่า Terraform",
    "Database configuration": "การตั้งค่าฐานข้อมูล",
    "Service account configuration": "การตั้งค่าบัญชีบริการ",
    "Webhook payload": "ข้อมูลเว็บฮุก",
    "Customer export": "ข้อมูลลูกค้า",
    "SQL export": "ข้อมูล SQL",
    "Application source": "ซอร์สโค้ดแอปพลิเคชัน",
    "Q1 business review": "ทบทวนธุรกิจไตรมาส 1",
    "Customer growth": "การเติบโตของลูกค้า",
    "Platform investment": "การลงทุนแพลตฟอร์ม",
    "Next quarter": "ไตรมาสถัดไป",
    "Order platform": "ระบบคำสั่งซื้อ",
    "Network layout": "ผังเครือข่าย",
    "Data layer": "ชั้นข้อมูล",
    "Open risks": "ความเสี่ยงที่เปิดอยู่",
    "Incident review": "ทบทวนเหตุการณ์",
    "Timeline": "ไทม์ไลน์",
    "Root cause": "สาเหตุราก",
    "Actions": "การดำเนินการ",
    "Sales performance": "ผลการขาย",
    "Pipeline": "ไปป์ไลน์",
    "Customer examples": "ตัวอย่างลูกค้า",
    "Forecast": "พยากรณ์",
    "Overview": "ภาพรวม",
    "Details": "รายละเอียด",
    "Risks": "ความเสี่ยง",
    "Next steps": "ขั้นตอนถัดไป",
    # section headings
    "Summary": "สรุป", "Timeline": "ไทม์ไลน์", "Follow-up": "การติดตามผล",
    "Attendees": "ผู้เข้าร่วม", "Notes": "บันทึก", "Action items": "รายการที่ต้องทำ",
    "Market view": "มุมมองตลาด", "Experience": "ประสบการณ์", "Skills": "ทักษะ",
    "Scope": "ขอบเขต", "Confidentiality": "การรักษาความลับ", "Signatures": "ลายเซ็น",
    "Impact": "ผลกระทบ", "Risks": "ความเสี่ยง",
    "1. Scope": "1. ขอบเขต", "2. Confidentiality": "2. การรักษาความลับ",
    "3. Signatures": "3. ลายเซ็น",
    # notes / footers
    "Generated test document. Values are synthetic and non-functional.":
        "เอกสารทดสอบที่สร้างขึ้น ค่าเป็นข้อมูลสังเคราะห์และใช้งานจริงไม่ได้",
    "Synthetic payroll - not real employee data": "เงินเดือนสังเคราะห์ - ไม่ใช่ข้อมูลพนักงานจริง",
    "Synthetic example - not real personal data": "ตัวอย่างสังเคราะห์ - ไม่ใช่ข้อมูลส่วนบุคคลจริง",
    "Exported for a synthetic customer-success review.":
        "ส่งออกเพื่อการทบทวนลูกค้าสัมพันธ์แบบสังเคราะห์",
    "Fictional clinic data for privacy-filter testing. No real patient records.":
        "ข้อมูลคลินิกสมมติสำหรับทดสอบตัวกรองความเป็นส่วนตัว ไม่มีเวชระเบียนจริง",
    "Statement generated for synthetic testing. Not a real bank document.":
        "รายการเดินบัญชีนี้สร้างเพื่อการทดสอบสังเคราะห์ ไม่ใช่เอกสารธนาคารจริง",
    "Synthetic example document. Not a real invoice or payment instruction.":
        "เอกสารตัวอย่างสังเคราะห์ ไม่ใช่ใบแจ้งหนี้หรือคำสั่งชำระเงินจริง",
    "Synthetic memo for policy testing.": "บันทึกสังเคราะห์สำหรับทดสอบนโยบาย",
    "Synthetic result for filter testing. Not a real diagnosis.":
        "ผลตรวจสังเคราะห์สำหรับทดสอบตัวกรอง ไม่ใช่การวินิจฉัยจริง",
    "Fictional medication names for testing only.":
        "ชื่อยาสมมติสำหรับการทดสอบเท่านั้น",
    "Synthetic management presentation. All data is fictional.":
        "งานนำเสนอผู้บริหารแบบสังเคราะห์ ข้อมูลทั้งหมดเป็นข้อมูลสมมติ",
    "Synthetic example - all values are fictional": "ตัวอย่างสังเคราะห์ - ค่าทั้งหมดเป็นข้อมูลสมมติ",
    "Confidential - synthetic example": "เป็นความลับ - ตัวอย่างสังเคราะห์",
    "Candidate CV - synthetic": "ประวัติย่อผู้สมัคร - ข้อมูลสังเคราะห์",
    "Internal - synthetic incident": "ภายใน - เหตุการณ์สังเคราะห์",
    "Internal meeting notes - synthetic": "บันทึกการประชุมภายใน - ข้อมูลสังเคราะห์",
    "Internal memo": "บันทึกข้อความภายใน",
    "Confidential strategy - synthetic": "กลยุทธ์ที่เป็นความลับ - ข้อมูลสังเคราะห์",
    "Risk committee - synthetic": "คณะกรรมการความเสี่ยง - ข้อมูลสังเคราะห์",
    "Synthetic support queue": "คิวสนับสนุนสังเคราะห์",
    "HR - synthetic form": "HR - แบบฟอร์มสังเคราะห์",
    "Hiring - confidential synthetic": "การสรรหา - ข้อมูลสังเคราะห์ที่เป็นความลับ",
    "Synthetic medical record - not a real patient": "เวชระเบียนสังเคราะห์ - ไม่ใช่ผู้ป่วยจริง",
    "Synthetic laboratory": "ห้องปฏิบัติการสังเคราะห์",
    "Synthetic prescription": "ใบสั่งยาสังเคราะห์",
    "Engineering notes - synthetic": "บันทึกวิศวกรรม - ข้อมูลสังเคราะห์",
    "Synthetic Bank - Example Only": "ธนาคารสมมติ - ตัวอย่างเท่านั้น",
    "Platform weekly - meeting minutes": "ประชุมแพลตฟอร์มรายสัปดาห์",
    # prose
    "Synthetic export from the people system. Internal use only.":
        "ข้อมูลส่งออกสังเคราะห์จากระบบบุคคล ใช้ภายในเท่านั้น",
    "Never commit real environment files. This example is non-functional.":
        "ห้าม commit ไฟล์ environment จริง ตัวอย่างนี้ใช้งานจริงไม่ได้",
    "The application could not connect to the database after the previous deployment.":
        "แอปพลิเคชันเชื่อมต่อฐานข้อมูลไม่ได้หลังการ deploy ครั้งก่อน",
    "At 09:12 the API gateway returned 502 responses for requests to the order service. ":
        "เวลา 09:12 API gateway ตอบกลับ 502 สำหรับคำขอไปยังบริการคำสั่งซื้อ ",
    "Rotate the exposed credential, review deployment logging, and add a config check.":
        "เปลี่ยน credential ที่รั่วไหล ตรวจสอบ logging ของ deployment และเพิ่มการตรวจ config",
    "The team reviewed the deployment checklist and the customer migration plan. ":
        "ทีมทบทวน checklist การ deploy และแผนย้ายข้อมูลลูกค้า ",
    "One action remains open for the database owner.":
        "ยังมีงานค้างหนึ่งรายการสำหรับเจ้าของฐานข้อมูล",
    "The quarterly access review found two accounts with elevated permissions. ":
        "การตรวจสอบสิทธิ์รายไตรมาสพบบัญชีสองบัญชีที่มีสิทธิ์สูง ",
    "Please confirm the owners before Friday.": "กรุณายืนยันเจ้าของบัญชีก่อนวันศุกร์",
    "Customer demand grew in the mid-market segment. The team will prioritise retention ":
        "ความต้องการของลูกค้าเติบโตในกลุ่ม mid-market ทีมจะให้ความสำคัญกับการรักษาลูกค้า ",
    "and shorten onboarding.": "และลดระยะเวลาการเริ่มใช้งาน",
    "Dependency on a single vendor and limited local support capacity remain the top risks.":
        "การพึ่งพาผู้ขายรายเดียวและกำลังสนับสนุนในพื้นที่จำกัดยังเป็นความเสี่ยงหลัก",
    "The parcel arrived three days late and the packaging was damaged. ":
        "พัสดุมาถึงช้ากว่ากำหนดสามวันและบรรจุภัณฑ์เสียหาย ",
    "Please confirm the replacement process.": "กรุณายืนยันขั้นตอนการเปลี่ยนสินค้า",
    "Reason: family trip. Coverage arranged with the platform team.":
        "เหตุผล: ทริปครอบครัว มีทีมแพลตฟอร์มดูแลงานแทน",
    "Plan: routine follow-up in four weeks. No real medical advice is provided.":
        "แผน: ติดตามผลตามปกติในสี่สัปดาห์ ไม่มีคำแนะนำทางการแพทย์จริง",
    "Traffic enters through a public load balancer and reaches the API service. ":
        "ทราฟฟิกเข้าผ่าน load balancer สาธารณะและไปถึงบริการ API ",
    "Workers consume the queue and store results in PostgreSQL.":
        "Worker ดึงงานจากคิวและเก็บผลลัพธ์ใน PostgreSQL",
    "Symptom: the API starts but readiness checks fail. Local environment works.":
        "อาการ: API เริ่มทำงานแต่ readiness check ล้มเหลว สภาพแวดล้อม local ใช้งานได้",
    "Next step: verify DNS resolution and the database security group.":
        "ขั้นตอนถัดไป: ตรวจสอบ DNS และ security group ของฐานข้อมูล",
    "The deployment log printed the following credential while retrying: ":
        "log ของ deployment พิมพ์ credential ต่อไปนี้ขณะลองใหม่: ",
    "Connection string in the failed job: ": "connection string ในงานที่ล้มเหลว: ",
    "Payment retry queue reference: ": "อ้างอิงคิวลองชำระเงินใหม่: ",
    "Affected host: ": "โฮสต์ที่ได้รับผลกระทบ: ",
    "Database endpoint: ": "ปลายทางฐานข้อมูล: ",
    "Service URL: ": "URL บริการ: ",
    "Network: ": "เครือข่าย: ",
    "Card on file: ": "บัตรที่บันทึกไว้: ",
    "Expiry: ": "วันหมดอายุ: ",
    "Authorization: ": "รหัสอนุมัติ: ",
    "Payment gateway key: ": "คีย์ payment gateway: ",
    "Billing service endpoint: ": "ปลายทางบริการเรียกเก็บเงิน: ",
    "Reference: ": "อ้างอิง: ",
    "Transaction reference: ": "อ้างอิงธุรกรรม: ",
    "Opening balance: ": "ยอดยกมา: ",
    "Request ID: ": "รหัสคำขอ: ",
    "Date: ": "วันที่: ", "Due: ": "ครบกำหนด: ",
    "Date:": "วันที่:", "Due:": "ครบกำหนด:",
    "  |  Date: ": "  |  วันที่: ", "  |  Due: ": "  |  ครบกำหนด: ",
    "  |  Date:": "  |  วันที่:", "  |  Due:": "  |  ครบกำหนด:",
    "|  Date:": "|  วันที่:", "|  Due:": "|  ครบกำหนด:",
    "Bill to: ": "เรียกเก็บเงินจาก: ", "Address: ": "ที่อยู่: ",
    "Account holder: ": "เจ้าของบัญชี: ", "Account: ": "บัญชี: ",
    "Subtotal: ": "ยอดรวมก่อนภาษี: ", "VAT 7%: ": "ภาษีมูลค่าเพิ่ม 7%: ",
    "Total: ": "ยอดรวม: ",
    "Incident ID: ": "รหัสเหตุการณ์: ", "Reported by: ": "ผู้รายงาน: ",
    "Requester: ": "ผู้แจ้ง: ", "Phone: ": "เบอร์โทร: ",
    "Issue: ": "ปัญหา: ", "Suggested next step: ": "ขั้นตอนถัดไปที่แนะนำ: ",
    "From: ": "จาก: ", "To: ": "ถึง: ", "Employee: ": "พนักงาน: ",
    "Email: ": "อีเมล: ", "National ID: ": "เลขบัตรประชาชน: ",
    "Leave type: ": "ประเภทการลา: ", "Dates: ": "วันที่: ", "Days: ": "จำนวนวัน: ",
    "Approved by: ": "อนุมัติโดย: ", "Candidate: ": "ผู้สมัคร: ",
    "Role: ": "ตำแหน่ง: ", "Patient: ": "ผู้ป่วย: ", "DOB: ": "วันเกิด: ",
    "Diagnosis: ": "การวินิจฉัย: ", "Plan: ": "แผน: ", "Clinician: ": "แพทย์ผู้ดูแล: ",
    "Owner: ": "ผู้รับผิดชอบ: ", "Reference: ": "อ้างอิง: ",
    "Bank transfer integration credential: ": "credential สำหรับโอนเงินผ่านธนาคาร: ",
    "The worker uses this integration credential: ": "worker ใช้ credential สำหรับเชื่อมต่อนี้: ",
    "The current environment file contains: ": "ไฟล์ environment ปัจจุบันมี: ",
    "The shared integration key was pasted in chat during the demo: ":
        "integration key ที่ใช้ร่วมกันถูกแปะในแชทระหว่างเดโม: ",
    "Legacy integration key still present in the deployment job: ":
        "integration key รุ่นเก่ายังอยู่ใน deployment job: ",
    "Temporary review credential: ": "credential ชั่วคราวสำหรับตรวจสอบ: ",
    "Example exposed value: ": "ตัวอย่างค่าที่รั่วไหล: ",
    "Database endpoint in scope: ": "ฐานข้อมูลในขอบเขต: ",
    "Review scope: ": "ขอบเขตการตรวจสอบ: ",
    "Migration target: ": "เป้าหมายการย้ายระบบ: ",
    "Resolution database endpoint: ": "ฐานข้อมูลที่ใช้แก้ปัญหา: ",
    "Application host: ": "โฮสต์แอปพลิเคชัน: ",
    "Internal service: ": "บริการภายใน: ",
    "Named customer sponsor: ": "ผู้สนับสนุนฝ่ายลูกค้า: ",
    "Customer address for the pilot: ": "ที่อยู่ลูกค้าสำหรับโครงการนำร่อง: ",
    "Expected booking: ": "ยอดจองที่คาดการณ์: ",
    "Platform capacity: ": "ความจุแพลตฟอร์ม: ",
    "Platform owner: ": "เจ้าของแพลตฟอร์ม: ",
    "Risk owner: ": "เจ้าของความเสี่ยง: ",
    "Failed order reference: ": "อ้างอิงคำสั่งซื้อที่ล้มเหลว: ",
    "Browser console showed request header: ": "console ของเบราว์เซอร์แสดง header คำขอ: ",
    "Order reference: ": "อ้างอิงคำสั่งซื้อ: ",
    "Delivery address: ": "ที่อยู่จัดส่ง: ",
    "Scorecard": "แบบประเมิน",
    # mixed-only footer; also used as a guaranteed Thai sentence
}
MIXED_FOOTER = "Synthetic example / เอกสารตัวอย่างสังเคราะห์ - ห้ามใช้กับข้อมูลจริง"
THAI_NOTE = "เอกสารตัวอย่างสังเคราะห์สำหรับทดสอบ privacy gateway เท่านั้น"
EN_NOTE = "Synthetic example for privacy-gateway testing only."

STATUS_VALUES = {
    "settled", "pending", "refunded", "packed", "shipped", "delivered",
    "qualified", "proposal", "negotiation", "won", "production", "staging",
    "high", "medium", "low", "strong", "good", "developing",
    "read", "write", "delete", "login", "annual", "travel", "software",
    "office", "training", "success", "failed", "started",
}

THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LATIN_RE = re.compile(r"[A-Za-z]")

# English static labels that may appear inside a longer line (``a: 1  b: 2``).
# Only these are reported as untranslated; technical vocabulary is not.
INLINE_LABELS: Dict[str, str] = {
    "bill to": "เรียกเก็บเงินจาก", "date": "วันที่", "due": "ครบกำหนด",
    "reference": "อ้างอิง", "subtotal": "ยอดรวมก่อนภาษี",
    "vat 7%": "ภาษีมูลค่าเพิ่ม 7%", "total": "ยอดรวม",
    "account holder": "เจ้าของบัญชี", "account": "บัญชี",
    "opening balance": "ยอดยกมา", "transaction reference": "อ้างอิงธุรกรรม",
    "card on file": "บัตรที่บันทึกไว้", "expiry": "วันหมดอายุ",
    "authorization": "รหัสอนุมัติ", "payment gateway key": "คีย์ payment gateway",
    "billing service endpoint": "ปลายทางบริการเรียกเก็บเงิน",
    "description": "รายการ", "quantity": "จำนวน", "unit price": "ราคาต่อหน่วย",
    "line total": "ยอดรวมรายการ", "amount": "จำนวนเงิน", "balance": "ยอดคงเหลือ",
    "type": "ประเภท", "address": "ที่อยู่", "national id": "เลขบัตรประชาชน",
    "email": "อีเมล", "phone": "เบอร์โทร", "role": "ตำแหน่ง", "plan": "แผน",
    "owner": "ผู้รับผิดชอบ", "approved by": "อนุมัติโดย", "requester": "ผู้แจ้ง",
    "from": "จาก", "to": "ถึง", "employee": "พนักงาน", "leave type": "ประเภทการลา",
    "dates": "วันที่", "days": "จำนวนวัน", "candidate": "ผู้สมัคร",
    "patient": "ผู้ป่วย", "dob": "วันเกิด", "diagnosis": "การวินิจฉัย",
    "clinician": "แพทย์ผู้ดูแล", "incident id": "รหัสเหตุการณ์",
    "reported by": "ผู้รายงาน", "issue": "ปัญหา",
    "suggested next step": "ขั้นตอนถัดไปที่แนะนำ", "scorecard": "แบบประเมิน",
    "service url": "URL บริการ", "database endpoint": "ปลายทางฐานข้อมูล",
    "network": "เครือข่าย", "request id": "รหัสคำขอ", "status": "สถานะ",
}
_THAI_LABELS = "|".join(
    sorted({re.escape(value) for value in INLINE_LABELS.values()}, key=len, reverse=True))
_INLINE_LABEL_RE = re.compile(
    r"(?:(?P<thai>" + _THAI_LABELS + r")\s*/\s*)?"
    r"(?<![A-Za-z])(?P<label>(" + "|".join(
        sorted((re.escape(key) for key in INLINE_LABELS), key=len, reverse=True)
    ) + r")):",
    re.IGNORECASE,
)
_LABEL_CANONICAL = {key.lower(): key for key in INLINE_LABELS}


def localize_labels_inline(text: str, language: str) -> str:
    """Localize ``Label:`` tokens embedded in a longer static line.

    Idempotent: a bilingual ``ไทย / English:`` pair produced by an earlier pass
    is collapsed or kept as one pair, never prefixed again.  Re-localizing the
    same document previously stacked ``ไทย / ไทย / ...`` in front of a label.
    """
    if language == "en" or not text:
        return text

    def replace(match: "re.Match") -> str:
        label = match.group("label")
        key = _LABEL_CANONICAL.get(label.lower(), label.lower())
        thai = INLINE_LABELS[key]
        if language == "th":
            return f"{thai}:"
        return f"{thai} / {label}:"

    return _INLINE_LABEL_RE.sub(replace, text)


def residual_english_labels(text: str) -> List[str]:
    """Known English labels still untranslated in a Thai document.

    Bilingual ``ไทย / English`` labels produced for mixed documents are not
    residual English, so they are ignored.
    """
    found = set()
    for line in text.splitlines():
        for match in _INLINE_LABEL_RE.finditer(line):
            label = match.group("label")
            if match.group("thai"):
                continue
            found.add(label)
    return sorted(found)


def label(value: str, language: str) -> str:
    """Localize a table header or short label."""
    thai = LABELS.get(value.lower(), TEXT_TH.get(value))
    if language == "en" or thai is None:
        return value
    if language == "mixed":
        return f"{thai} / {value}"
    return thai


def localize_text(text: str, language: str) -> str:
    """Translate static text.  Unknown technical text is left unchanged."""
    if language == "en" or not text:
        return text
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()
    translated = TEXT_TH.get(core)
    if translated is None:
        translated = _prefix_translation(core)
    if translated is None:
        translated = _phrase_translation(core)
    if translated is None:
        translated = _status_translation(core, language)
    if translated is None:
        return localize_labels_inline(text, language)
    return localize_labels_inline(lead + translated + trail, language)


def _phrase_translation(core: str) -> str:
    result = core
    for key in _LONG_PHRASES:
        if key in result:
            result = result.replace(key, TEXT_TH[key])
    return result if result != core else None


def _prefix_translation(core: str) -> str:
    for key in _PREFIX_KEYS:
        if core.startswith(key):
            tail = core[len(key):]
            mapped = TEXT_TH[key]
            return mapped + localize_text(tail, "th")
    return None


def _status_translation(core: str, language: str) -> str:
    lowered = core.lower()
    if lowered in STATUS_VALUES:
        thai = LABELS.get(lowered)
        if thai:
            return f"{thai} / {core}" if language == "mixed" else thai
    return None


_PREFIX_KEYS = sorted(
    (key for key in TEXT_TH if key.endswith(": ")),
    key=len,
    reverse=True,
)
_LONG_PHRASES = sorted(
    (key for key in TEXT_TH if len(key) >= 24 and not key.endswith(": ")),
    key=len,
    reverse=True,
)


def localize_parts(text: str, placements: Sequence[Placement], language: str) -> Tuple[str, List[Placement]]:
    """Translate static segments while keeping entity placements exact."""
    if language == "en" or not placements:
        return localize_text(text, language), list(placements)
    ordered = sorted(placements, key=lambda item: item.start)
    pieces: List[str] = []
    result: List[Placement] = []
    cursor = 0
    length = 0
    for item in ordered:
        if item.start < cursor:
            continue
        static = localize_text(text[cursor:item.start], language)
        pieces.append(static)
        length += len(static)
        value = text[item.start:item.end]
        start = length
        pieces.append(value)
        length += len(value)
        result.append(Placement(item.entity, start, length, item.role))
        cursor = item.end
    pieces.append(localize_text(text[cursor:], language))
    return "".join(pieces), result


def _localize_cell(value: Cell, language: str) -> Cell:
    text, placements = localize_parts(value.text, value.placements, language)
    return Cell(text, placements)


def _localize_block(block: Block, language: str, localize_headers: bool = True) -> None:
    if block.kind == "heading":
        block.text = localize_text(block.text, language)
    elif block.kind in ("paragraph", "note", "bullet"):
        block.text, block.placements = localize_parts(block.text, block.placements, language)
    elif block.kind == "table":
        block.title = localize_text(block.title, language)
        if localize_headers:
            block.headers = [label(header, language) for header in block.headers]
        block.rows = [[_localize_cell(value, language) for value in row] for row in block.rows]
    # code and log blocks keep technical English; a Thai heading/note carries
    # the document language and the renderer adds a localized comment.


def localize_doc(doc: Doc, language: str, localize_headers: bool = True) -> Doc:
    """Localize a document in place.  Entity values are never modified.

    ``localize_headers=False`` keeps machine keys (JSON/XML/YAML/config) in
    English so path provenance stays resolvable; titles, prose and notes are
    still localized.
    """
    if language == "en":
        return doc
    doc.language = language
    doc.title = localize_text(doc.title, language)
    for block in doc.blocks:
        _localize_block(block, language, localize_headers)
    for slide in doc.slides:
        slide.title = localize_text(slide.title, language)
        for block in slide.blocks:
            _localize_block(block, language, localize_headers)
    header = doc.metadata.get("header")
    if isinstance(header, Cell):
        doc.metadata["header"] = _localize_cell(header, language)
    footer = doc.metadata.get("footer")
    if isinstance(footer, Cell):
        doc.metadata["footer"] = _localize_cell(footer, language)
    hidden = doc.metadata.get("hidden_sheets")
    if isinstance(hidden, list):
        doc.metadata["hidden_sheets"] = [localize_text(item, language) for item in hidden]
    if doc.record is not None:
        if isinstance(doc.record, dict) and language in ("th", "mixed"):
            doc.record.setdefault("_language_note", THAI_NOTE)
    ensure_language_content(doc, language)
    return doc


def _add_note(doc: Doc, text: str) -> None:
    doc.blocks.append(Block("note", text=text))


def ensure_language_content(doc: Doc, language: str) -> None:
    """Guarantee the declared language is actually present in the document."""
    text = document_text(doc)
    thai = len(THAI_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if language == "th" and thai == 0:
        _add_note(doc, THAI_NOTE)
    elif language == "mixed":
        if thai == 0:
            _add_note(doc, THAI_NOTE)
        if latin == 0:
            _add_note(doc, EN_NOTE)


def document_text(doc: Doc) -> str:
    parts: List[str] = [doc.title]
    for block in doc.all_blocks():
        parts.append(block.text)
        parts.append(block.title)
        parts.extend(block.headers)
        for row in block.rows:
            parts.extend(cell.text for cell in row)
    if isinstance(doc.record, dict):
        parts.extend(_walk_strings(doc.record))
    return "\n".join(part for part in parts if part)


def _strip_placements(text: str, placements: Sequence[Placement]) -> str:
    result = text
    for placement in sorted(placements, key=lambda item: item.start, reverse=True):
        result = result[:placement.start] + result[placement.end:]
    return result


def document_static_text(doc: Doc) -> str:
    """Authored text only: entity values are removed before measuring scripts.

    A Thai name inside an otherwise English template must not make the file look
    Thai; the language label describes the document, not its identifiers.
    """
    parts: List[str] = [doc.title]
    for block in doc.all_blocks():
        parts.append(_strip_placements(block.text, block.placements))
        parts.append(block.title)
        parts.extend(block.headers)
        for row in block.rows:
            parts.extend(_strip_placements(cell.text, cell.placements) for cell in row)
    if isinstance(doc.record, dict):
        parts.extend(_walk_strings(doc.record))
    return "\n".join(part for part in parts if part)


def _walk_strings(value) -> List[str]:
    found: List[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_walk_strings(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_walk_strings(child))
    return found


def script_stats(text: str) -> dict:
    """Measured script shares; digits, punctuation and spaces are neutral.

    ``thai_share`` / ``latin_share`` use script letters as the denominator so a
    log full of digits and punctuation is still an English log.  The neutral
    share is reported separately over all counted characters.
    """
    thai = len(THAI_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    neutral = sum(1 for char in text
                  if not char.isspace() and not THAI_RE.match(char) and not LATIN_RE.match(char))
    letters = thai + latin
    total = letters + neutral
    return {
        "thai_chars": thai,
        "latin_chars": latin,
        "neutral_chars": neutral,
        "counted_chars": total,
        "thai_share": round(thai / letters, 4) if letters else 0.0,
        "latin_share": round(latin / letters, 4) if letters else 0.0,
        "neutral_share": round(neutral / total, 4) if total else 0.0,
    }


def language_matches(stats: dict, language: str, thresholds: dict) -> bool:
    """Whether measured script shares satisfy the declared language."""
    thai = float(stats.get("thai_share", 0.0))
    latin = float(stats.get("latin_share", 0.0))
    thai_min = float(thresholds.get("th", {}).get("min_thai_share", 0.0))
    latin_min = float(thresholds.get("en", {}).get("min_latin_share", 0.0))
    mixed_thai = float(thresholds.get("mixed", {}).get("min_thai_share", 0.0))
    mixed_latin = float(thresholds.get("mixed", {}).get("min_latin_share", 0.0))
    if language == "th":
        return thai >= thai_min
    if language == "en":
        return latin >= latin_min
    if language == "mixed":
        return thai >= mixed_thai and latin >= mixed_latin
    return False


def classify_language(stats: dict, thresholds: dict) -> Optional[str]:
    """Best matching label, or ``None`` when no declared label fits.

    Thai is checked first so a Thai-dominant document full of English
    identifiers is still ``th``.  ``mixed`` is the fallback for documents whose
    scripts are both present but neither dominates.
    """
    for language in ("th", "en", "mixed"):
        if language_matches(stats, language, thresholds):
            return language
    return None


def script_counts(text: str) -> dict:
    stats = script_stats(text)
    stats.update({
        "thai_characters": stats["thai_chars"],
        "latin_characters": stats["latin_chars"],
        "contains_thai": stats["thai_chars"] > 0,
        "contains_latin": stats["latin_chars"] > 0,
        "contains_both": stats["thai_chars"] > 0 and stats["latin_chars"] > 0,
    })
    return stats


def format_date(value, language: str, mode: str = "be") -> str:
    """Format an ISO date (or date object) for Thai/English documents."""
    if isinstance(value, str):
        day = _dt.date.fromisoformat(value[:10])
    elif isinstance(value, _dt.date):
        day = value
    else:
        raise TypeError(f"unsupported date value: {value!r}")
    if language == "en":
        return f"{day.day} {EN_MONTHS[day.month - 1]} {day.year}"
    year = day.year + 543 if mode == "be" else day.year
    if language == "mixed":
        return f"{day.day} {THAI_MONTHS_SHORT[day.month - 1]} {year}"
    return f"{day.day} {THAI_MONTHS[day.month - 1]} {year}"


def format_currency(amount: float, language: str, mode: str = "thb") -> str:
    if language == "en":
        return f"THB {amount:,.2f}"
    if language == "mixed":
        return f"฿{amount:,.2f}"
    return f"{amount:,.2f} บาท"


def language_capability(extension: str) -> Tuple[str, ...]:
    """Content languages a renderer can carry without glyph loss."""
    if extension in ("pdf", "png", "jpg", "jpeg"):
        # v2.2: the bundled Sarabun font + ReportLab/Pillow carry Thai, English
        # and mixed content.  A thinner renderer can shrink this tuple again
        # without touching the routing call sites.
        return ("th", "en", "mixed")
    if extension == "log":
        # Log bodies are technical English by convention; a Thai log would be
        # an English frame with Thai prose around machine text.
        return ("en",)
    return ("th", "en", "mixed")


def language_mix_description(language: str) -> str:
    return {
        "th": "Thai business prose with English technical terms",
        "en": "English business prose",
        "mixed": "Thai prose with English field names and technical terms",
    }.get(language, "unknown")
