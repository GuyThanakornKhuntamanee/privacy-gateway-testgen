import json
import unittest

from .support import ROOT, SRC  # noqa: F401
from .support import generate_small

from privacy_gateway_testgen.validation import REQUIRED_FIELDS


class SchemaTests(unittest.TestCase):
    def test_schema_required_fields_match_validator(self):
        with open(ROOT / "schemas" / "testcase.schema.json", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(set(schema["required"]), set(REQUIRED_FIELDS))
        self.assertEqual(set(schema["properties"]), set(REQUIRED_FIELDS))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0")

    def test_schema_enums_match_domain_model(self):
        with open(ROOT / "schemas" / "testcase.schema.json", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(schema["properties"]["policy_decision_expected"]["enum"],
                         ["ALLOW", "MASK", "TOKENIZE", "REDACT", "LOCAL_ONLY", "BLOCK"])
        self.assertEqual(schema["properties"]["language"]["enum"], ["th", "en", "mixed"])
        self.assertEqual(schema["properties"]["split"]["enum"],
                         ["train", "validation", "test"])

    def test_generated_case_has_every_required_property(self):
        dataset, _, _ = generate_small(12, seed=5)
        with open(ROOT / "schemas" / "testcase.schema.json", encoding="utf-8") as handle:
            schema = json.load(handle)
        for case in dataset["cases"]:
            self.assertTrue(set(schema["required"]).issubset(case))


if __name__ == "__main__":
    unittest.main()
