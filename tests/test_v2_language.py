"""Schema 2.1 language realism tests: localization, mixed script, routing."""

from __future__ import annotations

import random
import unittest

from tests.support import ROOT
from privacy_gateway_testgen.entities import EntityPool
from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.archetypes import BY_ID, BuildContext
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.docmodel import DocBuilder, cell
from privacy_gateway_testgen.v2.extract import verify_attachment
from privacy_gateway_testgen.v2.generate import V2Generator
from privacy_gateway_testgen.v2.localization import (
    document_text, format_currency, format_date, label, localize_doc, script_counts,
)
from privacy_gateway_testgen.v2.org import make_org
from privacy_gateway_testgen.v2.renderers import render
from privacy_gateway_testgen.v2.scenario import make_scenario
from privacy_gateway_testgen.v2.validation import validate_dataset_v2

CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")


def build(archetype_id: str, language: str, domains=("pii", "payment", "secrets", "infrastructure"),
          negative: bool = False) -> object:
    rng = random.Random(11)
    org_language = "th" if language in ("th", "mixed") else "en"
    org = make_org(rng, org_language, "normal")
    pool = EntityPool(rng, org_language, org.as_pool_org())
    scenario = make_scenario("pgt2-trn-00001", rng, org, pool, org_language, negative, False)
    ctx = BuildContext(rng=rng, language=org_language, org=org, pool=pool, domains=domains,
                       negative=negative, doc_language=language, scenario=scenario,
                       attachment_id="ATT-001")
    doc = BY_ID[archetype_id].builder(ctx)
    localize_doc(doc, language)
    return doc, scenario


class LocalizationTests(unittest.TestCase):
    def test_thai_labels_and_formatting(self):
        self.assertEqual(label("email", "th"), "อีเมล")
        self.assertEqual(label("email", "mixed"), "อีเมล / email")
        self.assertEqual(label("email", "en"), "email")
        self.assertEqual(format_date("2026-03-18", "th", "be"), "18 มีนาคม 2569")
        self.assertEqual(format_date("2026-03-18", "th", "ce"), "18 มีนาคม 2026")
        self.assertEqual(format_date("2026-03-18", "en"), "18 March 2026")
        self.assertIn("บาท", format_currency(12400, "th"))
        self.assertIn("THB", format_currency(12400, "en"))

    def test_thai_document_has_thai_headers_and_intact_entities(self):
        doc, _scenario = build("payroll", "th")
        text = document_text(doc)
        counts = script_counts(text)
        self.assertTrue(counts["contains_thai"])
        self.assertIn("พนักงาน", text)
        rendered = render(doc, "xlsx", "payroll.xlsx")
        verification = verify_attachment(rendered.data, "xlsx", rendered.mime_type,
                                         rendered.entity_locations, rendered.meta)
        self.assertEqual(verification["issues"], [])
        self.assertEqual(verification["status"], "verified")

    def test_mixed_document_really_code_switches(self):
        doc, _scenario = build("employee_list", "mixed")
        text = document_text(doc)
        counts = script_counts(text)
        self.assertTrue(counts["contains_thai"], text[:200])
        self.assertTrue(counts["contains_latin"], text[:200])
        self.assertIn("ชื่อ / name", text)
        rendered = render(doc, "docx", "employee_list.docx")
        verification = verify_attachment(rendered.data, "docx", rendered.mime_type,
                                         rendered.entity_locations, rendered.meta)
        self.assertEqual(verification["issues"], [])

    def test_english_document_stays_english(self):
        doc, _scenario = build("incident_report", "en")
        text = document_text(doc)
        self.assertEqual(script_counts(text)["thai_characters"], 0)

    def test_pdf_and_image_refuse_thai_instead_of_replacing_glyphs(self):
        builder = DocBuilder("memo", "รายงานภาษาไทย", "memo.pdf", "th")
        builder.para("ทดสอบ ", Entity("pii", "thai_name", "สมชาย ใจดี"))
        doc = builder.build()
        with self.assertRaises(ValueError):
            render(doc, "pdf", "memo.pdf")
        with self.assertRaises(ValueError):
            render(doc, "png", "memo.png")


class PerAttachmentLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_v2_config(CONFIG, profile="benchmark-balanced")
        config["total_samples"] = 18
        config["seed"] = 55
        cls.dataset = V2Generator(config, load_policy(POLICY)).generate()

    def test_attachments_have_independent_language_metadata(self):
        attachments = [item for case in self.dataset["cases"] for item in case["attachments"]]
        languages = {item["language"] for item in attachments}
        self.assertGreaterEqual(len(languages), 2)
        for item in attachments:
            self.assertIn(item["language"], ("th", "en", "mixed"))
            self.assertIn(item["language"], item["language_capability"])
            self.assertIn("language_check", item)
            if item["language"] == "mixed":
                self.assertTrue(item["language_check"]["contains_both"])
            if item["language"] == "th":
                self.assertTrue(item["language_check"]["contains_thai"])

    def test_pdf_and_image_are_routed_to_english(self):
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                if attachment["extension"] in ("pdf", "png", "jpg", "jpeg"):
                    self.assertEqual(attachment["language"], "en")
                    self.assertTrue(attachment["language_routing"])
                    self.assertEqual(attachment["language_capability"], ["en"])

    def test_language_matrix_is_measured(self):
        matrix = self.dataset["stats"]["language_matrix"]
        self.assertGreaterEqual(len(matrix), 4)
        self.assertTrue(any("->th" in key for key in matrix))

    def test_validation_accepts_generated_21_cases(self):
        self.assertEqual(validate_dataset_v2(self.dataset["cases"], load_policy(POLICY)), [])


if __name__ == "__main__":
    unittest.main()
