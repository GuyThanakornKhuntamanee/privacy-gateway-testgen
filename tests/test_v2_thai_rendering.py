"""Round-trip tests for the v2.2 Thai PDF and raster rendering path.

The generator's ground truth is the canonical text it composed; OCR is never run.
These tests therefore check three things per format: the file opens with a real
parser, the canonical Thai text comes back out (native PDF only), and the
recorded boxes still describe the rendered file.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from pypdf import PdfReader

from tests.support import ROOT
from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.archetypes import BY_ID, BuildContext
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.docmodel import DocBuilder, cell
from privacy_gateway_testgen.v2.extract import verify_attachment
from privacy_gateway_testgen.v2.generate import V2Generator, export_v2_dataset
from privacy_gateway_testgen.v2.localization import language_capability, script_counts
from privacy_gateway_testgen.v2.renderers import render
from privacy_gateway_testgen.v2.renderers.fonts import RendererUnavailable, font_path
from privacy_gateway_testgen.v2.renderers.textlayout import cluster_spans, normalize_extracted

NAME = Entity("pii", "thai_name", "ลลิตา พูลสวัสดิ์")
EMAIL = Entity("pii", "email_address", "lalita.p@example.com")
HOST = Entity("infrastructure", "internal_hostname", "db-primary.internal")
URL = Entity("infrastructure", "internal_url", "https://intranet.example.internal/health")
CARD = Entity("payment", "payment_card_number", "4111111111111111")
KEY = Entity("secrets", "api_key", "sk_example_fake_0123456789abcdef")
CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")


def thai_doc(language: str = "th", title: str = "รายงานเหตุการณ์ระบบ") -> object:
    builder = DocBuilder("incident_report", title, "incident.pdf", language)
    builder.heading("รายงานเหตุการณ์ระบบ")
    builder.para("ผู้แจ้ง: ", NAME, " (", EMAIL, ")")
    builder.para("ระบบที่ได้รับผลกระทบ: ", HOST, " เวลา: 09:12")
    builder.para("ทีม DevOps พบ timeout ระหว่าง API gateway กับ database "
                 "หลังจาก rotate credential และกำลังตรวจสอบ")
    builder.para("Service URL: ", URL, " จำนวนเงิน 1,250.00 บาท")
    builder.table(["พนักงาน", "อีเมล"], [[NAME, EMAIL], ["กาย", "kay@example.com"]],
                  title="ตาราง")
    builder.code(["ERROR connection timeout", "host=db-primary.internal"])
    builder.para("บัตร: ", CARD, " คีย์: ", KEY)
    return builder.build()


def english_doc() -> object:
    builder = DocBuilder("incident_report", "Incident report", "incident.pdf", "en")
    builder.heading("Incident report")
    builder.para("Reported by ", Entity("pii", "person_name", "Anan Jaidee"))
    builder.para("Host ", HOST, " could not reach the database.")
    return builder.build()


def pdf_pages(data: bytes):
    reader = PdfReader(io.BytesIO(data))
    return [normalize_extracted(page.extract_text() or "") for page in reader.pages]


def verified(rendered, extension: str) -> dict:
    return verify_attachment(rendered.data, extension, rendered.mime_type,
                             rendered.entity_locations, rendered.meta)


class NativeThaiPdfTests(unittest.TestCase):
    def test_thai_text_renders_and_extracts(self):
        rendered = render(thai_doc(), "pdf", "thai.pdf")
        result = verified(rendered, "pdf")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["status"], "verified")
        text = "\n".join(pdf_pages(rendered.data))
        self.assertIn("รายงานเหตุการณ์ระบบ", text)
        self.assertIn(NAME.value, text)
        self.assertIn(EMAIL.value, text)
        self.assertIn(HOST.value, text)
        self.assertIn(URL.value, text)
        self.assertNotIn("\ufffd", text)

    def test_english_text_extracts_exactly(self):
        rendered = render(english_doc(), "pdf", "english.pdf")
        text = "\n".join(pdf_pages(rendered.data))
        self.assertIn("Incident report", text)
        self.assertIn("Anan Jaidee", text)
        self.assertEqual(script_counts(text)["thai_characters"], 0)

    def test_mixed_language_pdf_carries_both_scripts(self):
        rendered = render(thai_doc("mixed"), "pdf", "mixed.pdf")
        text = "\n".join(pdf_pages(rendered.data))
        counts = script_counts(text)
        self.assertGreater(counts["thai_characters"], 20)
        self.assertGreater(counts["latin_characters"], 20)
        self.assertTrue(counts["contains_both"])
        self.assertIn("ทีม DevOps พบ timeout", normalize_extracted(text))

    def test_slide_deck_pdf_renders_one_page_per_slide(self):
        builder = DocBuilder("management_deck", "สไลด์ผู้บริหาร", "deck.pdf", "th")
        builder.slide("ภาพรวม", "เนื้อหาภาษาไทย ", NAME)
        builder.slide("ผลลัพธ์", "ระบบ ", HOST, " ทำงานปกติ")
        rendered = render(builder.build(), "pdf", "deck.pdf")
        pages = pdf_pages(rendered.data)
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(rendered.entity_locations), 2)
        self.assertEqual(verified(rendered, "pdf")["issues"], [])
        self.assertIn(NAME.value, pages[0])
        self.assertIn(HOST.value, pages[1])

    def test_multi_page_pdf_keeps_entities_on_their_page(self):
        builder = DocBuilder("incident_report", "รายงานยาว", "long.pdf", "th")
        for index in range(45):
            builder.para(f"ย่อหน้า {index}: ทีมตรวจสอบระบบและบันทึกเหตุการณ์ไว้เรียบร้อยแล้ว "
                         "พร้อมทั้งยืนยันว่าข้อมูลยังคงครบถ้วนทุกครั้ง")
        builder.para("ผู้รับผิดชอบคนสุดท้าย: ", NAME)
        rendered = render(builder.build(), "pdf", "long.pdf")
        pages = pdf_pages(rendered.data)
        self.assertGreater(len(pages), 1)
        result = verified(rendered, "pdf")
        self.assertEqual(result["issues"], [])
        last = rendered.entity_locations[-1]["location"]
        self.assertEqual(last["page"], len(pages))
        self.assertIn(NAME.value, pages[last["page"] - 1])

    def test_thai_table_cells_are_located_and_extractable(self):
        rendered = render(thai_doc(), "pdf", "table.pdf")
        table_cells = [item for item in rendered.entity_locations
                       if item["location"]["kind"] == "pdf_text"]
        self.assertGreaterEqual(len(table_cells), 5)
        for item in table_cells:
            self.assertGreater(item["location"]["width"], 0)
        pages = pdf_pages(rendered.data)
        self.assertIn(NAME.value, pages[0])

    def test_embedded_font_and_unicode_map(self):
        rendered = render(thai_doc(), "pdf", "font.pdf")
        self.assertIn(b"/FontFile2", rendered.data)
        self.assertIn(b"/ToUnicode", rendered.data)
        self.assertIn(b"Sarabun", rendered.data)
        self.assertTrue(rendered.meta["font"]["embedded"])

    def test_pdf_has_no_active_content(self):
        rendered = render(thai_doc(), "pdf", "safe.pdf")
        for marker in (b"/JavaScript", b"/OpenAction", b"/Launch", b"/EmbeddedFile"):
            self.assertNotIn(marker, rendered.data)

    def test_thai_entity_is_never_split_by_wrapping(self):
        long_name = Entity("pii", "thai_name", "พระมหาสมชาย สุขสวัสดิ์ มั่นคงเจริญ")
        builder = DocBuilder("memo", "บันทึก", "memo.pdf", "th")
        builder.para("ผู้ลงนามในเอกสารฉบับนี้คือ ", long_name, " และผู้แทนอีกหลายท่าน "
                     "จึงเรียนมาเพื่อโปรดพิจารณาและอนุมัติในลำดับต่อไป")
        doc = builder.build()
        for extension in ("pdf", "png"):
            rendered = render(doc, extension, f"memo.{extension}")
            self.assertEqual(verified(rendered, extension)["issues"], [], extension)
            for item in rendered.entity_locations:
                if item["entity"].value != long_name.value:
                    continue
                location = item["location"]
                if location["kind"] in ("image_ocr", "pdf_image"):
                    self.assertIn(long_name.value, location["expected_ocr_text"])
                else:
                    self.assertGreaterEqual(location["character_end"] - location["character_start"],
                                            len(long_name.value))

    def test_thai_digits_and_currency_extract(self):
        amount = Entity("payment", "payment_amount", "๑๒,๕๐๐.๐๐ บาท")
        builder = DocBuilder("memo", "ใบเสร็จ", "receipt.pdf", "th")
        builder.para("ยอดชำระทั้งสิ้น ", amount, " ฿1,250.00")
        rendered = render(builder.build(), "pdf", "receipt.pdf")
        text = "\n".join(pdf_pages(rendered.data))
        self.assertIn(amount.value, text)
        self.assertIn("฿1,250.00", text)

    def test_pdf_bytes_are_deterministic(self):
        first = render(thai_doc(), "pdf", "a.pdf").data
        second = render(thai_doc(), "pdf", "a.pdf").data
        self.assertEqual(hashlib.sha256(first).hexdigest(),
                         hashlib.sha256(second).hexdigest())

    def test_pdf_bytes_are_stable_across_hash_seeds(self):
        script = (
            "import hashlib, sys\n"
            "sys.path.insert(0, 'src')\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from tests.test_v2_thai_rendering import thai_doc\n"
            "from privacy_gateway_testgen.v2.renderers import render\n"
            "print(hashlib.sha256(render(thai_doc(), 'pdf', 'a.pdf').data).hexdigest())\n"
        )
        digests = []
        for hash_seed in ("5", "888"):
            environment = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH="src")
            environment["PYTHONIOENCODING"] = "utf-8"
            result = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT),
                                    capture_output=True, text=True, env=environment, check=True)
            digests.append(result.stdout.strip())
        self.assertEqual(digests[0], digests[1])


class ThaiImageTests(unittest.TestCase):
    def test_png_and_jpeg_render_thai_and_verify(self):
        for extension in ("png", "jpg", "jpeg"):
            with self.subTest(extension=extension):
                rendered = render(thai_doc(), extension, f"shot.{extension}")
                result = verified(rendered, extension)
                self.assertEqual(result["issues"], [])
                self.assertEqual(result["status"], "verified_layout")
                with Image.open(io.BytesIO(rendered.data)) as image:
                    width, height = image.size
                self.assertEqual((width, height),
                                 (rendered.meta["width"], rendered.meta["height"]))
                thai = [item for item in rendered.entity_locations
                        if item["entity"].value == NAME.value]
                self.assertTrue(thai)
                box = thai[0]["location"]["bbox"]
                self.assertGreaterEqual(box[0], 0)
                self.assertGreaterEqual(box[1], 0)
                self.assertLessEqual(box[0] + box[2], width + 0.5)
                self.assertLessEqual(box[1] + box[3], height + 0.5)

    def test_mixed_screenshot_contains_both_scripts(self):
        doc = thai_doc("mixed")
        doc.metadata["image_style"] = "terminal"
        rendered = render(doc, "png", "terminal.png")
        lines = {item["location"]["expected_ocr_text"] for item in rendered.entity_locations}
        joined = "\n".join(sorted(lines))
        counts = script_counts(joined)
        self.assertTrue(counts["contains_both"], joined[:200])
        self.assertEqual(verified(rendered, "png")["issues"], [])

    def test_rotated_scan_reports_final_boxes(self):
        doc = thai_doc()
        doc.metadata["ocr_difficulty"] = 4
        doc.metadata["image_seed"] = 11
        rendered = render(doc, "png", "scan.png")
        self.assertTrue(rendered.meta["rotation_applied"])
        result = verified(rendered, "png")
        self.assertEqual(result["issues"], [])
        for item in rendered.entity_locations:
            self.assertEqual(item["location"]["bbox_space"], "final")
            self.assertTrue(item["location"]["rotation_applied"])

    def test_long_thai_entity_widens_the_canvas(self):
        long_name = Entity("pii", "thai_name",
                           "นางสาวสุชาดา ประเสริฐศรีวัฒนกุล มั่นคงถาวร")
        builder = DocBuilder("screenshot_form", "แบบฟอร์ม", "form.png", "th")
        builder.para("ชื่อ-นามสกุล: ", long_name)
        doc = builder.build()
        doc.metadata["image_style"] = "form"
        doc.metadata["image_width"] = 420
        rendered = render(doc, "png", "form.png")
        self.assertGreater(rendered.meta["width"], 420)
        result = verified(rendered, "png")
        self.assertEqual(result["issues"], [])
        location = next(item["location"] for item in rendered.entity_locations
                        if item["entity"].value == long_name.value)
        self.assertEqual(location["fragment_count"], 1)
        self.assertIn(long_name.value, location["expected_ocr_text"])

    def test_image_bytes_are_deterministic(self):
        first = render(thai_doc(), "jpg", "a.jpg").data
        second = render(thai_doc(), "jpg", "a.jpg").data
        self.assertEqual(hashlib.sha256(first).hexdigest(),
                         hashlib.sha256(second).hexdigest())


class ScannedAndHybridPdfTests(unittest.TestCase):
    def test_thai_scanned_pdf_is_layout_verified(self):
        doc = thai_doc()
        doc.scan = True
        doc.metadata["image_style"] = "scan"
        doc.metadata["ocr_difficulty"] = 3
        rendered = render(doc, "pdf", "scan.pdf")
        self.assertEqual(rendered.renderer, "pdf_scanned")
        self.assertEqual(rendered.meta["mode"], "scanned")
        result = verified(rendered, "pdf")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["status"], "verified_layout")
        self.assertNotIn("ocr_verified", result["checks"])
        self.assertEqual(len(PdfReader(io.BytesIO(rendered.data)).pages), 1)
        for item in rendered.entity_locations:
            location = item["location"]
            self.assertEqual(location["kind"], "pdf_image")
            self.assertEqual(location["source_type"], "scanned_page")
            self.assertLessEqual(location["page_bbox"][0] + location["page_bbox"][2], 595.5)
            self.assertLessEqual(location["page_bbox"][1] + location["page_bbox"][3], 842.5)

    def test_hybrid_pdf_mixes_native_text_and_embedded_image(self):
        doc = thai_doc()
        index = next(i for i, block in enumerate(doc.blocks) if block.kind == "table")
        doc.metadata.update({"hybrid_block": index, "hybrid_span": 1,
                             "hybrid_style": "scan", "image_seed": 3})
        rendered = render(doc, "pdf", "hybrid.pdf")
        self.assertEqual(rendered.meta["mode"], "hybrid")
        sources = {item["location"]["kind"]: item["location"]["source_type"]
                   for item in rendered.entity_locations}
        self.assertEqual(sources["pdf_text"], "native_text")
        self.assertEqual(sources["pdf_image"], "embedded_image")
        result = verified(rendered, "pdf")
        self.assertEqual(result["issues"], [])
        text = "\n".join(pdf_pages(rendered.data))
        self.assertIn(NAME.value, text)


class FontCapabilityTests(unittest.TestCase):
    def test_bundled_font_is_present_and_licensed(self):
        path = font_path("regular")
        self.assertTrue(path.is_file())
        self.assertTrue(path.with_name("OFL.txt").is_file())
        self.assertTrue(font_path("bold").is_file())

    def test_missing_font_raises_instead_of_falling_back(self):
        with self.assertRaises(RendererUnavailable):
            font_path("condensed")

    def test_pdf_and_image_declare_thai_capability(self):
        for extension in ("pdf", "png", "jpg", "jpeg"):
            self.assertEqual(language_capability(extension), ("th", "en", "mixed"))
        self.assertEqual(language_capability("log"), ("en",))

    def test_combining_marks_stay_in_one_cluster(self):
        text = "กิ่ ก้ เนื้อ เบื้องต้น น้ำ"
        for start, end in cluster_spans(text):
            for offset in range(start + 1, end):
                code = ord(text[offset])
                self.assertTrue(0x0E31 <= code <= 0x0E4E or code in (0x0E33,),
                                f"{text[offset]!r} should not start a cluster")

    def test_normalizer_does_not_accept_broken_words(self):
        self.assertEqual(normalize_extracted("example.com\n"), "example.com")
        self.assertNotEqual(normalize_extracted("exam ple.com"), "example.com")


class CrossFileThaiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from privacy_gateway_testgen.entities import EntityPool
        from privacy_gateway_testgen.v2.org import make_org
        from privacy_gateway_testgen.v2.scenario import make_scenario
        import random

        rng = random.Random(7)
        org = make_org(rng, "th", "normal")
        pool = EntityPool(rng, "th", org.as_pool_org())
        scenario = make_scenario("pgt2-trn-00001", rng, org, pool, "th", False, False)
        cls.scenario = scenario
        cls.ctx = BuildContext(rng=rng, language="th", org=org, pool=pool,
                               domains=("pii", "infrastructure", "secrets"),
                               negative=False, ambiguous=False, density=2,
                               doc_language="th", image_style="scan", ocr_difficulty=2,
                               scenario=scenario, variant=1, attachment_id="ATT-001")

    def test_thai_docx_and_pdf_share_one_identity(self):
        docx_doc = BY_ID["employee_list"].builder(self.ctx)
        pdf_doc = BY_ID["incident_report"].builder(self.ctx)
        shared_name = self.ctx.org.employees[0].name.value
        docx = render(docx_doc, "docx", "employees.docx")
        pdf = render(pdf_doc, "pdf", "incident.pdf")
        self.assertEqual(verified(docx, "docx")["issues"], [])
        self.assertEqual(verified(pdf, "pdf")["issues"], [])
        self.assertIn(shared_name, pdf_pages(pdf.data)[0])
        values = {item["entity"].value for item in pdf.entity_locations}
        self.assertTrue(values & {item["entity"].value for item in docx.entity_locations},
                        "Thai DOCX and Thai PDF share no canonical entity value")

    def test_thai_xlsx_and_screenshot_share_one_identity(self):
        sheet = BY_ID["employee_list"].builder(self.ctx)
        builder = DocBuilder("screenshot_form", "แบบฟอร์ม", "form.png", "th")
        builder.para("พนักงาน: ", self.ctx.person_name(self.ctx.org.employees[0]))
        image_doc = builder.build()
        image_doc.metadata.update({"image_style": "form", "image_seed": 2})
        xlsx = render(sheet, "xlsx", "employees.xlsx")
        image = render(image_doc, "png", "form.png")
        self.assertEqual(verified(xlsx, "xlsx")["issues"], [])
        self.assertEqual(verified(image, "png")["issues"], [])
        name = self.ctx.org.employees[0].name.value
        self.assertIn(name, "\n".join(item["location"]["expected_ocr_text"]
                                      for item in image.entity_locations))

    def test_english_config_and_thai_pdf_keep_scenario_endpoints(self):
        env = BY_ID["application_environment_config"].builder(self.ctx)
        incident = BY_ID["incident_report"].builder(self.ctx)
        env_file = render(env, "env", "prod.env")
        pdf = render(incident, "pdf", "incident.pdf")
        self.assertEqual(env_file.mime_type, "text/plain")
        text = env_file.data.decode("utf-8")
        endpoint = self.scenario.org.database_endpoint.value
        self.assertIn(endpoint, text)
        self.assertIn(endpoint, "\n".join(pdf_pages(pdf.data)))


class DatasetModalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_v2_config(CONFIG, profile="thai-rendering")
        config["total_samples"] = 8
        policy = load_policy(POLICY)
        cls.dataset = V2Generator(config, policy).generate()
        cls.policy = policy

    def test_thai_pdf_and_image_attachments_are_verified(self):
        seen = 0
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                if attachment["extension"] not in ("pdf", "png", "jpg", "jpeg"):
                    continue
                if attachment["language"] not in ("th", "mixed"):
                    continue
                seen += 1
                self.assertIn(attachment["evaluation_requirement"],
                              ("direct_text_extraction", "ocr_required"))
                self.assertIn(attachment["language"], attachment["language_capability"])
                self.assertIn(attachment["verification"]["status"],
                              ("verified", "verified_layout"))
        self.assertGreater(seen, 0)

    def test_modality_decides_the_benchmark_subset(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_v2_dataset(self.dataset, directory,
                                         load_v2_config(CONFIG, profile="thai-rendering"),
                                         self.policy)
            for name in ("benchmark_safe_text_cases.jsonl", "benchmark_safe_ocr_cases.jsonl"):
                self.assertTrue(os.path.exists(os.path.join(directory, name)), name)
            with open(os.path.join(directory, "benchmark_safe_text_cases.jsonl"), encoding="utf-8") as handle:
                text_cases = [json.loads(line) for line in handle if line.strip()]
            with open(os.path.join(directory, "benchmark_safe_ocr_cases.jsonl"), encoding="utf-8") as handle:
                ocr_cases = [json.loads(line) for line in handle if line.strip()]
            self.assertTrue(text_cases)
            self.assertTrue(ocr_cases)
            for case in text_cases:
                self.assertEqual(case["evaluation_requirement"], "direct_text_extraction")
            for case in ocr_cases:
                self.assertEqual(case["evaluation_requirement"], "ocr_required")
            self.assertEqual(
                manifest["benchmark_safe_text_cases"], len(text_cases))
            self.assertEqual(
                manifest["benchmark_safe_ocr_cases"], len(ocr_cases))
            ids_text = {case["test_id"] for case in text_cases}
            ids_ocr = {case["test_id"] for case in ocr_cases}
            self.assertFalse(ids_text & ids_ocr)


if __name__ == "__main__":
    unittest.main()
