"""Disclosure tests: synthetic marking must be out-of-band by default.

The generator's ground truth is synthetic, but a detector under test must never
read a hint in the payload that could suppress a detection.  These tests pin both
halves of that rule: no in-band notice in the default mode, and a complete
out-of-band trail (`synthetic: true`, `NOTICE.md`, manifest fields).
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
import unittest
import zipfile

from pypdf import PdfReader

from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.docmodel import DocBuilder
from privacy_gateway_testgen.v2.generate import V2Generator, export_v2_dataset
from privacy_gateway_testgen.v2.renderers import SUPPORTED_FORMATS, render

MARKER = re.compile(r"synthetic|fictional|not a real|not real", re.IGNORECASE)
CONFIG = "configs/v2/default.json"
POLICY = "configs/policy.default.json"


def neutral_doc():
    builder = DocBuilder("incident_report", "Incident report", "incident", "en")
    builder.heading("Incident report")
    builder.para("Reported by ", Entity("pii", "person_name", "Anan Jaidee"),
                 " on host ", Entity("infrastructure", "internal_hostname", "db-primary.internal"))
    builder.table(["employee", "email"],
                  [["Anan", Entity("pii", "email_address", "anan.jaidee@example.com")]])
    builder.code(["ERROR connection timeout"])
    builder.record({"database": {"host": "db-primary.internal"}})
    return builder.build()


def file_text(rendered) -> str:
    extension = rendered.filename.rsplit(".", 1)[-1].lower()
    if extension in ("pdf",):
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(rendered.data)).pages)
    if extension in ("docx", "xlsx", "pptx"):
        with zipfile.ZipFile(io.BytesIO(rendered.data)) as archive:
            parts = []
            for name in archive.namelist():
                if name.endswith(".xml") or name.endswith(".rels"):
                    parts.append(archive.read(name).decode("utf-8", "ignore"))
            return "\n".join(parts)
    if extension in ("png", "jpg", "jpeg"):
        return ""
    return rendered.data.decode("utf-8", "ignore")


class MetadataDisclosureTests(unittest.TestCase):
    def test_no_in_band_notice_in_every_supported_format(self):
        for mode, expected in (("metadata", False), ("banner", True)):
            with self.subTest(mode=mode):
                doc = neutral_doc()
                doc.metadata["disclosure"] = mode
                seen = set()
                hits = []
                for extension in SUPPORTED_FORMATS:
                    rendered = render(doc, extension, f"sample.{extension}")
                    text = file_text(rendered)
                    if not text:
                        continue  # raster text needs OCR; covered by the banner byte test
                    if MARKER.search(text):
                        seen.add(extension)
                        hits.append((extension, MARKER.search(text).group(0)))
                if expected:
                    self.assertTrue(seen, "banner mode must emit a visible notice somewhere")
                else:
                    self.assertEqual(hits, [], f"in-band notice leaked in {sorted(seen)}")

    def test_banner_mode_changes_raster_bytes(self):
        doc = neutral_doc()
        doc.metadata["image_style"] = "terminal"
        doc.metadata["disclosure"] = "metadata"
        hidden = render(doc, "png", "shot.png").data
        doc.metadata["disclosure"] = "banner"
        visible = render(doc, "png", "shot.png").data
        self.assertNotEqual(hidden, visible)

    def test_pdf_metadata_does_not_claim_synthetic(self):
        doc = neutral_doc()
        doc.metadata["disclosure"] = "metadata"
        data = render(doc, "pdf", "sample.pdf").data
        self.assertNotIn(b"synthetic", data.lower())


class OutOfBandDisclosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_v2_config(CONFIG, profile="benchmark-balanced")
        cls.config["total_samples"] = 4
        cls.config["seed"] = 12
        cls.policy = load_policy(POLICY)
        cls.dataset = V2Generator(cls.config, cls.policy).generate()

    def test_every_attachment_and_manifest_is_marked(self):
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                self.assertIs(attachment["synthetic"], True)
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_v2_dataset(self.dataset, directory, self.config, self.policy)
            self.assertIs(manifest["synthetic"], True)
            self.assertEqual(manifest["disclosure"], "metadata")
            self.assertEqual(manifest["synthetic_notice"], "NOTICE.md")
            notice_path = os.path.join(directory, "NOTICE.md")
            self.assertTrue(os.path.exists(notice_path))
            with open(notice_path, encoding="utf-8") as handle:
                notice = handle.read()
            self.assertIn("synthetic", notice.lower())
            self.assertIn("out-of-band", notice.lower())
            self.assertIn("NOTICE.md", manifest["files"])

    def test_default_config_uses_metadata_disclosure(self):
        self.assertEqual(self.config.get("disclosure"), "metadata")
        with self.assertRaises(ValueError):
            bad = load_v2_config(CONFIG, profile="benchmark-balanced")
            bad["disclosure"] = "always"
            from privacy_gateway_testgen.v2.config import validate_v2_config
            validate_v2_config(bad)


if __name__ == "__main__":
    unittest.main()
