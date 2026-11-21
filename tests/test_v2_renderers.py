"""Renderer round-trip tests for every schema-v2 file family."""

from __future__ import annotations

import io
import unittest
import zipfile

from tests.support import ROOT
from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.v2.docmodel import DocBuilder, cell
from privacy_gateway_testgen.v2.extract import verify_attachment
from privacy_gateway_testgen.v2.renderers import SUPPORTED_FORMATS, render
from privacy_gateway_testgen.v2.renderers.base import MIME_TYPES

NAME = Entity("pii", "thai_name", "Anan Jaidee")
EMAIL = Entity("pii", "email_address", "anan.jaidee@example.com")
IP = Entity("infrastructure", "internal_ipv4", "10.20.1.15")
KEY = Entity("secrets", "api_key", "sk_example_fake_0123456789abcdef")
CARD = Entity("payment", "payment_card_number", "4111111111111111")


def sample_doc() -> object:
    builder = DocBuilder("incident_report", "Synthetic incident report", "incident.docx", "en")
    builder.heading("Incident report")
    builder.para("Reported by ", NAME, " (", EMAIL, ").")
    builder.para("The application host ", IP, " could not reach the database.")
    builder.table(["employee", "email"], [["Anan", EMAIL], [NAME, "ops"]], title="People")
    builder.record({
        "database": {"host": IP, "password": KEY},
        "payment": {"card": CARD, "reference": "TXN-2026-0001"},
        "note": "synthetic example",
    })
    return builder.build(header=cell("Synthetic header"), footer=cell("Synthetic footer"),
                         hidden_sheets=["People"], xml_root="incident")


class RendererRoundTripTests(unittest.TestCase):
    def test_every_supported_format_renders_and_verifies(self):
        doc = sample_doc()
        for ext in SUPPORTED_FORMATS:
            with self.subTest(ext=ext):
                rendered = render(doc, ext, f"sample.{ext}")
                self.assertGreater(len(rendered.data), 20)
                self.assertEqual(rendered.mime_type, MIME_TYPES[ext])
                self.assertGreater(len(rendered.entity_locations), 0, f"{ext} lost all entity locations")
                result = verify_attachment(rendered.data, ext, rendered.mime_type,
                                           rendered.entity_locations, rendered.meta)
                self.assertEqual(result["issues"], [], f"{ext}: {result['issues']}")
                self.assertIn(result["status"], ("verified", "verified_layout"))

    def test_ooxml_packages_are_macro_free(self):
        doc = sample_doc()
        for ext in ("docx", "xlsx", "pptx"):
            rendered = render(doc, ext, f"sample.{ext}")
            with zipfile.ZipFile(io.BytesIO(rendered.data)) as archive:
                names = archive.namelist()
                self.assertNotIn("word/vbaProject.bin", names)
                self.assertNotIn("xl/vbaProject.bin", names)
                self.assertNotIn("ppt/vbaProject.bin", names)
                self.assertIsNone(archive.testzip())
                self.assertIn("[Content_Types].xml", names)

    def test_pdf_has_no_active_content(self):
        doc = sample_doc()
        rendered = render(doc, "pdf", "sample.pdf")
        for marker in (b"/JavaScript", b"/JS", b"/OpenAction", b"/Launch"):
            self.assertNotIn(marker, rendered.data)
        self.assertTrue(rendered.data.startswith(b"%PDF-"))

    def test_png_and_jpeg_have_real_headers(self):
        doc = sample_doc()
        png = render(doc, "png", "sample.png")
        jpg = render(doc, "jpg", "sample.jpg")
        self.assertEqual(png.data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(jpg.data[:2], b"\xff\xd8")
        self.assertIn(b"\xff\xc0", jpg.data)
        self.assertNotEqual(png.data, jpg.data)

    def test_scanned_pdf_is_layout_verified(self):
        doc = sample_doc()
        doc.scan = True
        doc.metadata["image_style"] = "scan"
        doc.metadata["ocr_difficulty"] = 2
        rendered = render(doc, "pdf", "scan.pdf")
        self.assertEqual(rendered.renderer, "pdf_scanned")
        self.assertTrue(any(item["location"]["kind"] == "pdf_image" for item in rendered.entity_locations))
        result = verify_attachment(rendered.data, "pdf", rendered.mime_type,
                                   rendered.entity_locations, rendered.meta)
        self.assertEqual(result["status"], "verified_layout")
        self.assertEqual(result["issues"], [])

    def test_verifier_rejects_tampered_spans(self):
        doc = sample_doc()
        rendered = render(doc, "txt", "sample.txt")
        tampered = [dict(item) for item in rendered.entity_locations]
        tampered[0] = dict(tampered[0])
        tampered[0]["location"] = dict(tampered[0]["location"])
        tampered[0]["location"]["character_start"] += 2
        tampered[0]["location"]["character_end"] += 2
        result = verify_attachment(rendered.data, "txt", rendered.mime_type, tampered, rendered.meta)
        self.assertEqual(result["status"], "unverified")
        self.assertTrue(result["issues"])


if __name__ == "__main__":
    unittest.main()
