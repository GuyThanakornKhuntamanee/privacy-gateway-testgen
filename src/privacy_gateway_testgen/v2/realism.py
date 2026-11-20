"""Human-like prompt engine for v2.

Real requests are short, incomplete, sometimes misspelled and usually about a
task, not about the sensitive data that happens to be in the file.  This module
keeps that shape: the attachment is the context, the prompt is the human part.
"""

from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Sequence

from ..builder import PromptBuilder
from ..models import Entity, Span

PERSONAS: Dict[str, dict] = {
    "developer": {
        "label": "software developer", "categories": ("IT", "Engineering"),
        "intents": ("troubleshoot", "check_code", "explain_error", "inspect_config", "find_anomalies"),
        "tone": "terse", "files": ("env", "log", "py", "js", "ts", "json", "yaml", "conf"),
    },
    "sysadmin": {
        "label": "system administrator", "categories": ("IT", "Engineering"),
        "intents": ("troubleshoot", "inspect_config", "explain_error", "summarize"),
        "tone": "terse", "files": ("log", "env", "yaml", "conf", "ini", "txt"),
    },
    "devops": {
        "label": "DevOps engineer", "categories": ("IT", "Engineering"),
        "intents": ("troubleshoot", "inspect_config", "find_anomalies", "summarize"),
        "tone": "terse", "files": ("yaml", "yml", "tf", "log", "json", "env"),
    },
    "hr": {
        "label": "HR staff", "categories": ("HR",),
        "intents": ("summarize", "extract_fields", "find_missing", "review_document", "prepare_report"),
        "tone": "polite", "files": ("xlsx", "docx", "pdf", "csv", "txt"),
    },
    "finance": {
        "label": "finance staff", "categories": ("Finance",),
        "intents": ("calculate", "compare", "find_anomalies", "prepare_report", "extract_fields"),
        "tone": "structured", "files": ("xlsx", "csv", "pdf", "docx"),
    },
    "accountant": {
        "label": "accountant", "categories": ("Finance",),
        "intents": ("calculate", "compare", "find_anomalies", "prepare_report", "review_document"),
        "tone": "structured", "files": ("xlsx", "csv", "pdf"),
    },
    "support": {
        "label": "customer support agent", "categories": ("Operations", "Support"),
        "intents": ("summarize", "answer_questions", "draft_email", "classify", "review_document"),
        "tone": "polite", "files": ("txt", "docx", "pdf", "png", "jpg", "json"),
    },
    "sales": {
        "label": "salesperson", "categories": ("Sales", "CRM"),
        "intents": ("summarize", "compare", "extract_fields", "prepare_report", "draft_email"),
        "tone": "casual", "files": ("xlsx", "csv", "pptx", "pdf", "docx"),
    },
    "manager": {
        "label": "manager", "categories": ("Management", "Corporate"),
        "intents": ("summarize", "prepare_report", "review_document", "answer_questions", "compare"),
        "tone": "polite", "files": ("pptx", "pdf", "docx", "xlsx"),
    },
    "executive_assistant": {
        "label": "executive assistant", "categories": ("Management", "Corporate"),
        "intents": ("summarize", "draft_email", "prepare_report", "modify_document", "translate"),
        "tone": "polite", "files": ("docx", "pdf", "pptx", "xlsx"),
    },
    "healthcare_admin": {
        "label": "healthcare administrative staff", "categories": ("Healthcare",),
        "intents": ("extract_fields", "summarize", "find_missing", "prepare_report"),
        "tone": "polite", "files": ("xlsx", "csv", "pdf", "docx"),
    },
    "analyst": {
        "label": "data analyst", "categories": ("Finance", "Sales", "Management"),
        "intents": ("calculate", "find_anomalies", "compare", "summarize", "create_chart"),
        "tone": "structured", "files": ("xlsx", "csv", "json", "pdf"),
    },
    "intern": {
        "label": "intern", "categories": ("HR", "Operations", "Sales"),
        "intents": ("summarize", "extract_fields", "find_missing", "translate", "rewrite"),
        "tone": "casual", "files": ("xlsx", "docx", "pdf", "txt", "png"),
    },
    "compliance": {
        "label": "compliance officer", "categories": ("Management", "HR", "Finance"),
        "intents": ("review_document", "classify", "find_anomalies", "prepare_report"),
        "tone": "polite", "files": ("pdf", "docx", "xlsx", "csv"),
    },
    "security_engineer": {
        "label": "security engineer", "categories": ("IT", "Engineering"),
        "intents": ("troubleshoot", "inspect_config", "check_code", "find_anomalies", "classify"),
        "tone": "terse", "files": ("log", "yaml", "json", "env", "py", "txt", "png"),
    },
    "operations": {
        "label": "operations staff", "categories": ("Operations", "Support"),
        "intents": ("find_anomalies", "find_missing", "extract_fields", "prepare_report", "answer_questions"),
        "tone": "casual", "files": ("xlsx", "csv", "txt", "pdf", "png", "log"),
    },
}

INTENT_PHRASES: Dict[str, dict] = {
    "summarize": {"th": ("สรุป", "สรุปให้หน่อย", "ทำ summary", "สรุปเป็น bullet"),
                  "en": ("summarize this", "give me a summary", "sum this up", "make a short summary")},
    "compare": {"th": ("เทียบให้หน่อย", "เทียบสองอันนี้", "ดูว่าต่างกันตรงไหน", "เทียบยอด"),
                "en": ("compare these", "tell me what changed", "spot the difference", "reconcile these")},
    "translate": {"th": ("แปลให้หน่อย", "แปลเป็นอังกฤษ", "translate ให้ที"),
                  "en": ("translate this", "put this in English", "translate it for me")},
    "rewrite": {"th": ("rewrite ให้หน่อย", "แก้ภาษาให้อ่านง่ายขึ้น", "ปรับถ้อยคำให้ที"),
                "en": ("rewrite this", "make it sound better", "clean up the wording")},
    "analyze": {"th": ("วิเคราะห์ให้หน่อย", "ดูให้หน่อยว่ามีอะไรผิดปกติ", "วิเคราะห์ข้อมูลนี้"),
                "en": ("analyze this", "look through it and tell me what stands out", "analyze the data")},
    "troubleshoot": {"th": ("ดูว่าทำไมต่อไม่ได้", "หาสาเหตุให้หน่อย", "ดู error ตรงไหน", "ช่วย debug"),
                     "en": ("figure out why it is failing", "find the error", "debug this", "why is this broken")},
    "extract_fields": {"th": ("ดึงข้อมูลที่ต้องใช้ให้หน่อย", "แยกฟิลด์ให้ที", "เอาข้อมูลออกมาเป็นตาราง"),
                       "en": ("pull out the fields I need", "extract the data into a table", "parse the fields")},
    "calculate": {"th": ("คำนวณให้หน่อย", "เช็กยอดรวมให้ที", "บวกยอดให้หน่อย"),
                  "en": ("calculate the total", "check the numbers", "work out the amounts")},
    "classify": {"th": ("จัดประเภทให้หน่อย", "บอกว่าเป็นหมวดไหน", "แยกประเภทให้ที"),
                 "en": ("classify these", "tell me which category this is", "sort these into groups")},
    "prepare_report": {"th": ("ทำรายงานให้หน่อย", "เตรียมสรุปสำหรับหัวหน้า", "ทำรายงานส่งลูกค้า"),
                       "en": ("put a report together", "prepare a summary for my manager", "make a client report")},
    "find_anomalies": {"th": ("ดูว่ามีรายการไหนผิดปกติ", "หา anomaly ให้หน่อย", "มีอะไรแปลกๆ ไหม"),
                       "en": ("find anything unusual", "look for anomalies", "flag anything odd")},
    "explain_error": {"th": ("อธิบาย error นี้ให้หน่อย", "error นี้หมายความว่าอะไร", "ทำไมขึ้น error นี้"),
                      "en": ("explain this error", "what does this error mean", "why am I getting this error")},
    "convert_format": {"th": ("แปลงเป็น CSV ให้หน่อย", "convert เป็น json", "เปลี่ยน format ให้ที"),
                       "en": ("convert this to CSV", "turn it into JSON", "change the format")},
    "draft_email": {"th": ("ร่างอีเมลให้หน่อย", "เขียนตอบลูกค้าให้ที", "ร่างข้อความส่งลูกค้า"),
                    "en": ("draft an email", "write a reply to the customer", "draft a message for the client")},
    "review_document": {"th": ("ตรวจเอกสารให้หน่อย", "รีวิวให้ทีว่ามีอะไรต้องแก้", "เช็กสัญญาฉบับนี้"),
                        "en": ("review this document", "check it before I send it", "go through this contract")},
    "modify_document": {"th": ("แก้หน้า 3 ให้หน่อย", "ปรับ wording ให้ที", "แก้เอกสารนี้ให้หน่อย"),
                        "en": ("edit page 3", "change the wording", "fix this document")},
    "find_missing": {"th": ("ดูว่ามีช่องไหนข้อมูลไม่ครบ", "หา missing value ให้หน่อย", "ใครข้อมูลขาดบ้าง"),
                     "en": ("find the missing values", "which rows are incomplete", "check for blanks")},
    "create_chart": {"th": ("ทำกราฟให้หน่อย", "สร้าง chart จากข้อมูลนี้", "plot ให้ที"),
                     "en": ("make a chart", "plot this data", "create a graph")},
    "answer_questions": {"th": ("ตอบคำถามจากไฟล์นี้ให้หน่อย", "ถามตอบจากเอกสารนี้", "สรุปคำตอบให้ที"),
                         "en": ("answer questions from this file", "what does the document say about this", "pull the answer")},
    "inspect_config": {"th": ("ดู config ให้หน่อย", "เช็กค่าพวกนี้ให้ที", "config นี้มีอะไรผิด"),
                       "en": ("check this config", "look at these settings", "is anything wrong in this config")},
    "check_code": {"th": ("ดูโค้ดให้หน่อย", "โค้ดนี้มีปัญหาตรงไหน", "review code ให้ที"),
                   "en": ("check this code", "what is wrong with this code", "review the code")},
    "generate_docs": {"th": ("เขียน doc ให้หน่อย", "ทำ README จากไฟล์นี้", "สรุปเป็นเอกสารให้ที"),
                      "en": ("write the docs", "turn this into a README", "document this")},
}

# Particle-free intent cores used by the slot composer.  Particles such as
# "หน่อย" / "please" live in the templates, so a task can never duplicate them.
INTENT_CORES: Dict[str, Dict[str, tuple]] = {
    "summarize": {"th": ("สรุป", "สรุปใจความ"), "en": ("summarize this", "give me a summary")},
    "compare": {"th": ("เทียบให้ดู", "เทียบสองอันนี้"), "en": ("compare these", "reconcile these")},
    "translate": {"th": ("แปล", "แปลเป็นอังกฤษ"), "en": ("translate this", "put this in English")},
    "rewrite": {"th": ("แก้ถ้อยคำ", "ปรับภาษา"), "en": ("rewrite this", "clean up the wording")},
    "analyze": {"th": ("วิเคราะห์", "ดูว่ามีอะไรผิดปกติ"), "en": ("analyze this", "tell me what stands out")},
    "troubleshoot": {"th": ("หาสาเหตุที่ต่อไม่ได้", "ดูว่า error อยู่ตรงไหน"),
                     "en": ("figure out why it is failing", "find the error")},
    "extract_fields": {"th": ("ดึงข้อมูลออกมาเป็นตาราง", "แยกฟิลด์"),
                       "en": ("pull out the fields I need", "extract the data into a table")},
    "calculate": {"th": ("คำนวณยอดรวม", "เช็กยอด"), "en": ("check the numbers", "work out the amounts")},
    "classify": {"th": ("จัดประเภท", "แยกหมวด"), "en": ("classify these", "sort these into groups")},
    "prepare_report": {"th": ("ทำรายงาน", "เตรียมสรุปสำหรับหัวหน้า"),
                       "en": ("put a report together", "prepare a summary for my manager")},
    "find_anomalies": {"th": ("หารายการที่ผิดปกติ", "หา anomaly"), "en": ("find anything unusual", "look for anomalies")},
    "explain_error": {"th": ("อธิบาย error นี้", "บอกว่า error นี้หมายความว่าอะไร"),
                      "en": ("explain this error", "tell me what this error means")},
    "convert_format": {"th": ("แปลงเป็น CSV", "เปลี่ยน format"), "en": ("convert this to CSV", "turn it into JSON")},
    "draft_email": {"th": ("ร่างอีเมล", "เขียนตอบลูกค้า"), "en": ("draft an email", "write a reply to the customer")},
    "review_document": {"th": ("ตรวจเอกสาร", "รีวิวเอกสารนี้"), "en": ("review this document", "check it before I send it")},
    "modify_document": {"th": ("แก้เอกสารนี้", "ปรับถ้อยคำ"), "en": ("edit this document", "change the wording")},
    "find_missing": {"th": ("หาข้อมูลที่ขาด", "ดูว่าช่องไหนว่าง"), "en": ("find the missing values", "check for blanks")},
    "create_chart": {"th": ("ทำกราฟ", "สร้าง chart"), "en": ("make a chart", "plot this data")},
    "answer_questions": {"th": ("ตอบคำถามจากไฟล์นี้", "ดึงคำตอบจากเอกสาร"),
                         "en": ("answer questions from this file", "pull the answer from the document")},
    "inspect_config": {"th": ("ตรวจ config", "ดูค่าตั้งค่า"), "en": ("check this config", "look at these settings")},
    "check_code": {"th": ("ตรวจโค้ด", "ดูว่าโค้ดมีปัญหาตรงไหน"), "en": ("check this code", "review the code")},
    "generate_docs": {"th": ("เขียนเอกสารประกอบ", "ทำ README"), "en": ("write the docs", "turn this into a README")},
}

FORMAL_OPENERS = {
    "th": ("รบกวนช่วย", "ช่วย", "ขอให้ช่วย"),
    "en": ("Could you", "Please", "Would you"),
}
CASUAL_OPENERS = {
    "th": ("ช่วย", "ดู", "เช็ก", "ลองดู"),
    "en": ("can you", "could you", "pls", "quick one"),
}

# Templates take a particle-free task core, so composing them cannot produce
# "ช่วยสรุปให้หน่อยหน่อย".  File slots are protected from typo mutation.
TH_TEMPLATES = {
    "file": (
        "{file} ช่วย{task}หน่อย",
        "{file} {task}ให้ที",
        "ช่วย{task}จาก {file} หน่อย",
        "ดู {file} แล้ว{task}ให้ที",
        "ฝาก{task} {file} หน่อย",
    ),
    "ref": (
        "อันนี้ช่วย{task}หน่อย",
        "ฝาก{task}ให้ที",
        "ช่วย{task}ที",
        "อยากให้{task}",
    ),
    "multi": (
        "สองไฟล์นี้ช่วย{task}หน่อย",
        "เทียบ {files} ให้ที แล้ว{task}",
        "เอาสองอันนี้{task}ให้หน่อย",
        "{files} ช่วย{task}ให้ที",
    ),
    "vague": (
        "อันนี้มัน error ตรงไหนอะ",
        "help หน่อย อันนี้มันแปลกๆ",
        "อันนี้ของลูกค้าเมื่อวานนะ",
        "ใช้ไฟล์นี้แทนอันเก่า",
        "ดูให้ทีนะ เมื่อคืนแก้แล้ว",
        "อันนี้มันยังไม่ได้เลย",
    ),
}

EN_TEMPLATES = {
    "file": (
        "{file} - can you {task}?",
        "attached {file}, {task} please",
        "quick one: {task} from {file}",
        "not sure what's wrong with {file}, {task}",
        "{file} attached. {task}",
        "could you take a look at {file} and {task}?",
    ),
    "ref": (
        "can you {task}?",
        "could you {task} for me",
        "{task} please",
        "this one is weird, {task}",
        "help me out, {task}",
    ),
    "multi": (
        "these two - {task}",
        "compare {files} and {task}",
        "can you {task} on both files",
        "{files} attached, {task} please",
    ),
    "vague": (
        "this is broken, can you look?",
        "not sure what happened here",
        "this came from the customer yesterday",
        "use this one instead of the old file",
        "it still doesn't work",
        "can you check this",
    ),
}

MIXED_TEMPLATES = {
    "file": (
        "ช่วย{task} {file} หน่อย",
        "{file} {task} ให้ที",
        "{file} {task} please",
        "ดู {file} แล้ว{task}ให้หน่อย",
        "help ดู {file} หน่อย แล้ว{task}",
    ),
    "ref": (
        "อันนี้ช่วย{task}ให้หน่อย",
        "help me {task} หน่อย",
        "this one {task} please",
        "ช่วย{task}ที",
    ),
    "multi": (
        "สองไฟล์นี้ช่วย{task}ให้ที",
        "compare {files} แล้ว{task}",
        "เอาสองอันนี้{task}หน่อย",
        "{files} help {task} ให้ที",
    ),
    "vague": (
        "อันนี้มัน error ตรงไหนอะ",
        "this is broken, help ดูให้ที",
        "อันนี้ของลูกค้า when you have time",
        "use this one แทนอันเก่า",
        "ยังไม่ได้เลย ช่วยดูที",
    ),
}

# (phrase, categories the phrase is plausible for).  A technical deployment
# comment never lands on an HR document.
CONTEXTS_TH = (
    ("คือเมื่อคืน deploy แล้วมันพัง", ("IT", "Engineering")),
    ("หัวหน้าขอภายในวันนี้", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare")),
    ("ข้อมูลเมื่อวานนะ", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare", "IT", "Engineering")),
    ("เครื่องผมรันปกตินะ", ("IT", "Engineering")),
    ("ลูกค้าเร่งอยู่", ("Support", "Sales", "CRM", "Operations")),
    ("ยังไม่ได้แก้เลย", ("IT", "Engineering", "Operations")),
    ("อันเก่ายังใช้ได้ปกติ", ("IT", "Engineering", "Operations")),
    ("พี่เมย์ฝากถาม", ("HR", "Finance", "Management", "Corporate", "Operations")),
    ("เพิ่ง export มาเมื่อเช้า", ("HR", "Finance", "Management", "Corporate", "Operations", "Sales", "CRM", "Healthcare")),
    ("ไม่แน่ใจว่าใช่ไฟล์เดียวกันไหม", ("HR", "Finance", "Management", "Corporate", "Operations")),
    ("ทีมภายนอกขอมาด่วน", ("Support", "Sales", "CRM", "Management", "Corporate")),
    ("พี่เขาบอกให้ส่งก่อนเที่ยง", ("HR", "Finance", "Management", "Corporate", "Operations")),
)
CONTEXTS_EN = (
    ("it worked yesterday", ("IT", "Engineering", "Operations")),
    ("prod only, staging is fine", ("IT", "Engineering")),
    ("boss wants it by 5", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare")),
    ("the customer is waiting", ("Support", "Sales", "CRM", "Operations")),
    ("this is the latest export", ("HR", "Finance", "Management", "Corporate", "Operations", "Sales", "CRM", "Healthcare")),
    ("not urgent but today please", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare")),
    ("the old file still works", ("IT", "Engineering", "Operations")),
    ("I exported it this morning", ("HR", "Finance", "Management", "Corporate", "Operations", "Sales", "CRM", "Healthcare")),
    ("not sure it's the right file", ("HR", "Finance", "Management", "Corporate", "Operations")),
    ("the vendor asked for it", ("Operations", "Sales", "Finance", "Management", "Corporate")),
    ("we need it before the meeting", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM")),
    ("someone changed this last night", ("IT", "Engineering", "Operations")),
)
CONTEXTS_MIXED = (
    ("คือเมื่อคืน deploy แล้วมันพัง", ("IT", "Engineering")),
    ("boss wants it by 5", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare")),
    ("ข้อมูลเมื่อวานนะ", ("HR", "Finance", "Management", "Corporate", "Operations", "Support", "Sales", "CRM", "Healthcare", "IT", "Engineering")),
    ("customer is waiting", ("Support", "Sales", "CRM", "Operations")),
    ("เพิ่ง export มาเมื่อเช้า", ("HR", "Finance", "Management", "Corporate", "Operations", "Sales", "CRM", "Healthcare")),
    ("prod only นะ", ("IT", "Engineering")),
    ("พี่เมย์ฝากถาม", ("HR", "Finance", "Management", "Corporate", "Operations")),
    ("use this one instead", ("HR", "Finance", "Management", "Corporate", "Operations")),
)

DESTINATION_PERSONAS = {"support", "sales", "executive_assistant", "manager", "compliance", "operations"}

DESTINATION_CLAUSES = {
    "th": (
        "อันนี้จะส่งให้ vendor นะ",
        "เดี๋ยวแชร์ในกลุ่มลูกค้า",
        "ต้องส่งต่อทีมภายนอก",
        "ไฟล์นี้ public แล้ว",
    ),
    "en": (
        "this is going to the vendor",
        "I need to share it with the customer",
        "it will go to an external team",
        "this file is already public",
    ),
    "mixed": (
        "อันนี้จะส่งให้ vendor",
        "ต้อง share ให้ customer",
        "this one goes external",
        "ไฟล์นี้ public แล้วนะ",
    ),
}

PERSONA_OPENERS = {
    "developer": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("quick one:", "hey,", "pls")},
    "sysadmin": {"th": ("พี่ครับ", "รบกวนดู", "เครื่องนี้"), "en": ("quick one:", "hey,", "ops question:")},
    "devops": {"th": ("พี่ครับ", "อันนี้", "ช่วยเช็ก"), "en": ("quick one:", "hey,", "deploy question:")},
    "hr": {"th": ("รบกวนช่วย", "พี่คะ", "ขอให้ช่วย"), "en": ("hello,", "could you", "please")},
    "finance": {"th": ("รบกวนช่วย", "พี่คะ", "ขอให้ช่วย"), "en": ("hello,", "please", "could you")},
    "accountant": {"th": ("รบกวนช่วย", "พี่คะ", "ขอให้ช่วย"), "en": ("hello,", "please", "could you")},
    "support": {"th": ("รบกวนช่วย", "พี่คะ", "ลูกค้าแจ้งว่า"), "en": ("hi,", "customer says", "could you")},
    "sales": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("hey,", "quick one:", "can you")},
    "manager": {"th": ("รบกวนช่วย", "ขอให้ช่วย", "ฝากดู"), "en": ("could you", "please", "would you")},
    "executive_assistant": {"th": ("รบกวนช่วย", "ขอให้ช่วย", "ฝากดู"), "en": ("could you", "please", "would you")},
    "healthcare_admin": {"th": ("รบกวนช่วย", "พี่คะ", "ขอให้ช่วย"), "en": ("hello,", "could you", "please")},
    "analyst": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("quick one:", "can you", "hey,")},
    "intern": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("hi,", "can you", "sorry,")},
    "compliance": {"th": ("รบกวนช่วย", "ขอให้ช่วย", "ฝากตรวจ"), "en": ("could you", "please", "would you")},
    "security_engineer": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("quick one:", "hey,", "sec question:")},
    "operations": {"th": ("พี่ครับ", "ช่วยดู", "อันนี้"), "en": ("hey,", "quick one:", "can you")},
}



def _pick(rng: random.Random, values: Sequence[str]) -> str:
    return values[rng.randrange(len(values))]


def _typo_word(word: str, rng: random.Random) -> str:
    """Latin-only character mutation.

    Thai is deliberately excluded: arbitrary insert/delete/swap on Thai
    combining marks produces unreadable text rather than a plausible mistake.
    Thai imperfection is expressed through particles, spacing and punctuation.
    """
    if len(word) < 4 or not re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", word):
        return word
    operation = rng.randrange(4)
    index = rng.randrange(1, len(word) - 1)
    if operation == 0:
        return word[:index] + word[index + 1:]
    if operation == 1:
        return word[:index] + word[index] + word[index:]
    if operation == 2 and index + 1 < len(word):
        return word[:index] + word[index + 1] + word[index] + word[index + 2:]
    return word.lower() if word[:1].isupper() else word


def imperfect(rng: random.Random, text: str, rate: float, language: str) -> str:
    """Apply a small, configurable amount of plausible human imperfection."""
    if not text or rate <= 0 or rng.random() >= rate:
        return text
    result = text
    words = result.split(" ")
    if language == "th":
        # Conservative Thai imperfection: a repeated particle, never a glyph
        # mutation.  "ช่วยสรุปหน่อยนะคะ" stays readable.
        particles = [index for index, word in enumerate(words)
                     if word.endswith(("ครับ", "ค่ะ", "คะ", "นะ"))]
        if particles and rng.random() < 0.5:
            index = rng.choice(particles)
            word = words[index]
            words[index] = word + ("คะ" if word.endswith("นะ") else "ะ")
            result = " ".join(words)
        elif rng.random() < 0.4:
            result = result.rstrip(".") + rng.choice(("นะคะ", "ครับ", "ค่ะ"))
    else:
        candidates = [i for i, word in enumerate(words)
                      if len(word) > 3 and not any(ch.isdigit() for ch in word)]
        if candidates:
            index = rng.choice(candidates)
            words[index] = _typo_word(words[index], rng)
            result = " ".join(words)
    if rng.random() < 0.25:
        result = result.rstrip(".!?")
    if rng.random() < 0.18 and "  " not in result:
        result = result.replace(" ", "  ", 1)
    if rng.random() < 0.08:
        result = result + rng.choice(("🙏", "😅"))
    if language == "en" and rng.random() < 0.18:
        result = result[:1].lower() + result[1:]
    return result


def _template_set(language: str) -> dict:
    if language == "th":
        return TH_TEMPLATES
    if language == "en":
        return EN_TEMPLATES
    return MIXED_TEMPLATES


def _contexts(language: str, persona: str = "") -> tuple:
    if language == "th":
        pool = CONTEXTS_TH
    elif language == "en":
        pool = CONTEXTS_EN
    else:
        pool = CONTEXTS_MIXED
    categories = set(PERSONAS.get(persona, {}).get("categories", ()))
    return tuple(phrase for phrase, allowed in pool if categories & set(allowed))


def _task(rng: random.Random, intent: str, language: str) -> str:
    cores = INTENT_CORES[intent]
    if language == "th":
        return _pick(rng, cores["th"])
    if language == "en":
        return _pick(rng, cores["en"])
    return _pick(rng, cores["th"] + cores["en"])


def _file_phrase(rng: random.Random, files: Sequence[dict], language: str) -> str:
    if not files:
        return ""
    if len(files) >= 2:
        names = ", ".join(item["filename"] for item in files[:2])
        return names if rng.random() < 0.45 else ("สองไฟล์นี้" if language == "th" else "these two")
    name = files[0]["filename"]
    if language == "th":
        return name if rng.random() < 0.55 else _pick(rng, ("ไฟล์นี้", "อันนี้", "ไฟล์แนบ"))
    if language == "mixed":
        return name if rng.random() < 0.55 else _pick(rng, ("ไฟล์นี้", "this file", "อันนี้"))
    return name if rng.random() < 0.55 else _pick(rng, ("this file", "the attached file", "this one"))


def _structure_phrase(rng: random.Random, ref: dict, language: str) -> str:
    kind = ref["kind"]
    value = ref["value"]
    if kind == "sheet":
        thai, english = f"tab {value}", f'tab "{value}"'
    elif kind == "row":
        thai, english = f"row {value}", f"row {value}"
    elif kind == "column":
        thai, english = f"คอลัมน์ {value}", f'column "{value}"'
    elif kind == "page":
        thai, english = f"หน้า {value}", f"page {value}"
    elif kind == "slide":
        thai, english = f"slide {value}", f"slide {value}"
    elif kind == "section":
        thai, english = f"ส่วน {value}", f'section "{value}"'
    elif kind == "line":
        thai, english = f"บรรทัดที่ {value}", f"line {value}"
    elif kind == "key":
        thai, english = f"key {value}", f'key "{value}"'
    else:
        thai = english = str(value)
    if language == "th":
        return _pick(rng, (f"ลองดู {thai} ด้วย", f"ช่วยเช็ก {thai} ให้ที", f"ดู {thai} หน่อย"))
    if language == "mixed":
        return _pick(rng, (f"check {thai} ให้ที", f"ดู {thai} ด้วย", f"ช่วยเช็ก {thai} หน่อย"))
    return _pick(rng, (f"also check {english}", f"look at {english} too", f"{english} looks off"))


def duplicated_phrases(prompt: str) -> List[str]:
    """Repeated multi-word fragments that signal blind concatenation."""
    normalized = " ".join(prompt.lower().split())
    words = normalized.split()
    found: List[str] = []
    for size in (2, 3, 4):
        counts: Dict[str, int] = {}
        for index in range(max(0, len(words) - size + 1)):
            gram = " ".join(words[index:index + size])
            counts[gram] = counts.get(gram, 0) + 1
        for gram, count in sorted(counts.items()):
            if count > 1 and not re.fullmatch(r"[\d\s.,:+\-/]+", gram):
                found.append(gram)
    return sorted(set(found))


def prompt_quality_issues(prompt: str) -> List[str]:
    issues = [f"duplicated phrase: {phrase}" for phrase in duplicated_phrases(prompt)
              if len(phrase) >= 8]
    for particle in ("หน่อยหน่อย", "ให้ทีให้ที", "please please", "ครับครับ", "ค่ะค่ะ"):
        if particle in prompt:
            issues.append(f"duplicated particle: {particle}")
    if re.search(r"(\S{3,})\s+\1", prompt, re.IGNORECASE):
        issues.append("duplicated adjacent word")
    return issues


def _shares_run(first: str, second: str, size: int = 3) -> bool:
    def grams(text: str) -> set:
        words = text.lower().split()
        return {" ".join(words[index:index + size])
                for index in range(max(0, len(words) - size + 1))}
    return bool(grams(first) & grams(second))


def build_prompt(
    rng: random.Random,
    *,
    persona: str,
    intent: str,
    language: str,
    formality: str,
    files: Sequence[dict],
    length: str = "medium",
    typo_rate: float = 0.15,
    destination: bool = False,
    prompt_entity: Optional[Entity] = None,
    structure_refs: Sequence[dict] = (),
) -> dict:
    templates = _template_set(language)
    key = "multi" if len(files) >= 2 else ("file" if files else "ref")
    # Vague prompts are realistic when the attachment carries the context.
    if files and rng.random() < 0.18:
        key = "vague"
    template = _pick(rng, templates[key])
    task = _task(rng, intent, language)
    file_phrase = _file_phrase(rng, files, language)
    files_phrase = file_phrase
    # Protect attachment names: a user may typo the request, not the filename
    # they are referring to.
    static = template.replace("{task}", task).replace("{file}", "\x00").replace("{files}", "\x01")
    static = imperfect(rng, static, typo_rate, language)

    def _opener_fits(opener: str, text: str) -> bool:
        lowered = text.lower()
        if not opener.strip():
            return True
        if lowered.startswith(opener.lower()):
            return False
        first = lowered.split()[0] if lowered.split() else ""
        if first and first in opener.lower().split():
            return False
        # Thai particles are multi-codepoint; compare whole particle words.
        particles = ("ช่วย", "รบกวน", "ขอให้", "ฝาก", "ดู", "อันนี้", "pls",
                     "please", "can you", "could you", "this")
        return not any(lowered.startswith(particle) and particle in opener.lower()
                       for particle in particles)

    if formality == "formal":
        opener = _pick(rng, FORMAL_OPENERS[language if language != "mixed" else "en"])
        if rng.random() < 0.35 and _opener_fits(opener, static):
            static = f"{opener} {static}"

    persona_openers = PERSONA_OPENERS.get(persona, {}).get(
        language if language != "mixed" else "th"
    )
    if persona_openers and rng.random() < 0.35:
        opener = _pick(rng, persona_openers)
        if _opener_fits(opener, static):
            static = opener + " " + static

    contexts = [phrase for phrase in _contexts(language, persona)
                if not _shares_run(static, phrase)]
    rng.shuffle(contexts)
    if not contexts:
        contexts = [phrase for phrase, _allowed in (
            CONTEXTS_TH if language == "th" else CONTEXTS_EN if language == "en"
            else CONTEXTS_MIXED) if not _shares_run(static, phrase)]
    text = static.replace("\x00", file_phrase).replace("\x01", files_phrase)
    if length in ("medium", "long") and contexts:
        text += ". " + imperfect(rng, contexts[0], typo_rate, language)
    if length == "long" and len(contexts) > 1:
        text += "; " + imperfect(rng, contexts[1], typo_rate, language)
        if rng.random() < 0.5 and len(contexts) > 2:
            text += ". " + imperfect(rng, contexts[2], typo_rate, language)

    context_complexity = "low" if length == "short" else ("medium" if length == "medium" else "high")
    if destination and persona in DESTINATION_PERSONAS:
        text += ". " + imperfect(rng, _pick(rng, DESTINATION_CLAUSES[language]), typo_rate, language)
        context_complexity = "high" if context_complexity == "low" else context_complexity
    if structure_refs:
        text += ". " + _structure_phrase(rng, structure_refs[0], language)
        if len(structure_refs) > 1 and rng.random() < 0.4:
            text += " และ" if language != "en" else " and "
            text += _structure_phrase(rng, structure_refs[1], language)
        context_complexity = "high"

    builder = PromptBuilder()
    if prompt_entity is not None:
        prefix = ""
        suffix = ""
        if language == "th":
            prefix = " ส่งไปที่ "
            suffix = " ด้วย"
        elif language == "en":
            prefix = " send it to "
            suffix = " too"
        else:
            prefix = " ส่งไปที่ "
            suffix = " ด้วย"
        if rng.random() < 0.5:
            builder.text(text)
            builder.text(prefix)
            builder.entity(prompt_entity)
            builder.text(suffix)
        else:
            builder.text(prefix.strip().capitalize() + " ")
            builder.entity(prompt_entity)
            builder.text(" - " + text)
    else:
        builder.text(text)
    prompt = builder.build()
    return {
        "prompt": prompt,
        "spans": builder.spans,
        "template_key": key,
        "intent": intent,
        "persona": persona,
        "formality": formality,
        "context_complexity": context_complexity,
        "prompt_style": length,
        "structure_references": list(structure_refs),
        "quality_issues": prompt_quality_issues(prompt),
    }


def prompt_fingerprint(prompt: str) -> str:
    normalized = " ".join(prompt.lower().split())
    return re.sub(r"\s+", " ", normalized)
