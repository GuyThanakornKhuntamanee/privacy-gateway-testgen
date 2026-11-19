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

FORMAL_OPENERS = {
    "th": ("รบกวนช่วย", "ช่วย", "ขอให้ช่วย"),
    "en": ("Could you", "Please", "Would you"),
}
CASUAL_OPENERS = {
    "th": ("ช่วย", "ดู", "เช็ก", "ลองดู"),
    "en": ("can you", "could you", "pls", "quick one"),
}

TH_TEMPLATES = {
    "file": (
        "{file} ช่วย{task}หน่อย",
        "อันนี้ {file} {task}ให้ที",
        "ดู {file} ให้หน่อย {task}",
        "พี่ช่วย{task} {file} นี้หน่อย",
        "{file} ล่าสุดนะ {task}",
        "งงกับ {file} นี้ {task}",
        "{file} อยู่ในแนบ {task} ให้ที",
        "ฝากดู {file} หน่อย {task}",
    ),
    "ref": (
        "อันนี้ {task} หน่อย",
        "ช่วย{task}ให้ที",
        "{task} ให้หน่อย",
        "อันนี้มัน {task}",
        "ฝากดูให้หน่อย {task}",
        "พี่ช่วย{task}ที",
    ),
    "multi": (
        "สองไฟล์นี้ {task} หน่อย",
        "เทียบ {files} ให้ที {task}",
        "เอาสองอันนี้ {task}",
        "{files} ช่วย{task}ให้หน่อย",
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
        "can you {task} for {file}?",
        "I've attached {file}; {task}",
        "could you take a look at {file} and {task}?",
    ),
    "ref": (
        "can you {task}?",
        "could you {task} for me",
        "{task} please",
        "this one is weird, {task}",
        "take a look and {task}",
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
        "ช่วย {task} {file} หน่อย",
        "this {file} {task} ให้ที",
        "{file} นี้ {task} please",
        "ดู {file} แล้ว {task} ให้หน่อย",
        "อันนี้ {file} ล่าสุด {task}",
        "help ดู {file} หน่อย {task}",
    ),
    "ref": (
        "อันนี้ {task} ให้หน่อย",
        "help me {task} หน่อย",
        "this one {task} please",
        "ช่วย {task} ที",
    ),
    "multi": (
        "สองไฟล์นี้ {task} ให้ที",
        "compare {files} แล้ว {task}",
        "เอาสองอันนี้ {task} หน่อย",
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

CONTEXTS_TH = (
    "คือเมื่อคืน deploy แล้วมันพัง",
    "หัวหน้าขอภายในวันนี้",
    "ข้อมูลเมื่อวานนะ",
    "เครื่องผมรันปกตินะ",
    "ลูกค้าเร่งอยู่",
    "ยังไม่ได้แก้เลย",
    "อันเก่ายังใช้ได้ปกติ",
    "พี่เมย์ฝากถาม",
    "เพิ่ง export มาเมื่อเช้า",
    "ไม่แน่ใจว่าใช่ไฟล์เดียวกันไหม",
    "ทีมภายนอกขอมาด่วน",
    "พี่เขาบอกให้ส่งก่อนเที่ยง",
)
CONTEXTS_EN = (
    "it worked yesterday",
    "prod only, staging is fine",
    "boss wants it by 5",
    "the customer is waiting",
    "this is the latest export",
    "not urgent but today please",
    "the old file still works",
    "I exported it this morning",
    "not sure it's the right file",
    "the vendor asked for it",
    "we need it before the meeting",
    "someone changed this last night",
)
CONTEXTS_MIXED = (
    "คือเมื่อคืน deploy แล้วมันพัง",
    "boss wants it by 5",
    "ข้อมูลเมื่อวานนะ",
    "customer is waiting",
    "เพิ่ง export มาเมื่อเช้า",
    "prod only นะ",
    "พี่เมย์ฝากถาม",
    "use this one instead",
)

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


def _pick(rng: random.Random, values: Sequence[str]) -> str:
    return values[rng.randrange(len(values))]


def _typo_word(word: str, rng: random.Random) -> str:
    if len(word) < 4 or not re.search(r"[A-Za-zก-๙]", word):
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
    """Apply a small, configurable amount of human imperfection."""
    if not text or rate <= 0 or rng.random() >= rate:
        return text
    result = text
    words = result.split(" ")
    candidates = [i for i, word in enumerate(words) if len(word) > 3 and not any(ch.isdigit() for ch in word)]
    if candidates:
        index = rng.choice(candidates)
        words[index] = _typo_word(words[index], rng)
        result = " ".join(words)
    if rng.random() < 0.25:
        result = result.rstrip(".!?")
    if rng.random() < 0.18:
        result = result.replace(" ", "  ", 1)
    if rng.random() < 0.12:
        result = result + rng.choice(("🙏", "😅", "ด่วน", ""))
    if language == "en" and rng.random() < 0.18:
        result = result[:1].lower() + result[1:]
    return result


def _template_set(language: str) -> dict:
    if language == "th":
        return TH_TEMPLATES
    if language == "en":
        return EN_TEMPLATES
    return MIXED_TEMPLATES


def _contexts(language: str) -> tuple:
    if language == "th":
        return CONTEXTS_TH
    if language == "en":
        return CONTEXTS_EN
    return CONTEXTS_MIXED


def _task(rng: random.Random, intent: str, language: str) -> str:
    phrases = INTENT_PHRASES[intent]
    if language == "th":
        return _pick(rng, phrases["th"])
    if language == "en":
        return _pick(rng, phrases["en"])
    return _pick(rng, phrases["th"] + phrases["en"])


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

    if formality == "formal":
        opener = _pick(rng, FORMAL_OPENERS[language if language != "mixed" else "en"])
        if rng.random() < 0.35:
            static = f"{opener} {static[:1].lower() + static[1:]}"
    elif formality == "casual" and language != "en" and rng.random() < 0.25:
        static = static.replace("ช่วย", "ช่วย", 1)

    contexts = list(_contexts(language))
    rng.shuffle(contexts)
    text = static.replace("\x00", file_phrase).replace("\x01", files_phrase)
    if length in ("medium", "long"):
        text += ". " + imperfect(rng, contexts[0], typo_rate, language)
    if length == "long":
        text += "; " + imperfect(rng, contexts[1], typo_rate, language)
        if rng.random() < 0.5:
            text += ". " + imperfect(rng, contexts[2], typo_rate, language)

    context_complexity = "low" if length == "short" else ("medium" if length == "medium" else "high")
    if destination:
        text += ". " + imperfect(rng, _pick(rng, DESTINATION_CLAUSES[language]), typo_rate, language)
        context_complexity = "high" if context_complexity == "low" else context_complexity

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
    return {
        "prompt": builder.build(),
        "spans": builder.spans,
        "template_key": key,
        "intent": intent,
        "persona": persona,
        "formality": formality,
        "context_complexity": context_complexity,
        "prompt_style": length,
    }


def prompt_fingerprint(prompt: str) -> str:
    normalized = " ".join(prompt.lower().split())
    return re.sub(r"\s+", " ", normalized)
