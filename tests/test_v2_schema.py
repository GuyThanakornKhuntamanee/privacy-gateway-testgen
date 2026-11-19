"""Schema 2.0 contract checks."""

from __future__ import annotations

import json
import unittest

from tests.support import ROOT
from tests.test_v2_generation import generate, make_config
from privacy_gateway_testgen.v2.validation import (
    CATEGORIES, LOCATION_KINDS, OBJECTIVES, REQUIRED_CASE_FIELDS, REQUIRED_ENTITY_FIELDS,
)

SCHEMA_PATH = ROOT / "schemas" / "testcase.v2.schema.json"


class V2SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.case = generate(make_config(4, 1))["cases"][0]

    def test_schema_version_and_required_fields(self):
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "2.0")
        self.assertEqual(set(self.schema["required"]), set(REQUIRED_CASE_FIELDS))
        equipment = set(self.schema["properties"]["entities"]["items"]["required"])
        self.assertEqual(equipment, set(REQUIRED_ENTITY_FIELDS))

    def test_location_kinds_match_validator(self):
        schema_kinds = set(self.schema["properties"]["entities"]["items"]["properties"]["location"]["properties"]["kind"]["enum"])
        self.assertEqual(schema_kinds, LOCATION_KINDS)

    def test_categories_and_objectives_match(self):
        self.assertEqual(set(self.schema["properties"]["test_category"]["enum"]), set(CATEGORIES))
        self.assertEqual(set(self.schema["properties"]["test_objective"]["enum"]), set(OBJECTIVES))

    def test_generated_case_has_every_required_property(self):
        for field in REQUIRED_CASE_FIELDS:
            self.assertIn(field, self.case)
        for attachment in self.case["attachments"]:
            for field in ("attachment_id", "filename", "extension", "mime_type", "size_bytes",
                          "sha256", "archetype", "renderer", "synthetic", "expected_extraction_method",
                          "verification", "path"):
                self.assertIn(field, attachment)
        for annotation in self.case["entities"]:
            for field in REQUIRED_ENTITY_FIELDS:
                self.assertIn(field, annotation)


if __name__ == "__main__":
    unittest.main()
