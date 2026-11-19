"""Schema 2.1 cross-file, arithmetic and structure-reference tests."""

from __future__ import annotations

import copy
import random
import unittest

from tests.support import ROOT
from privacy_gateway_testgen.entities import EntityPool
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.archetypes import BY_ID, BuildContext
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.generate import V2Generator
from privacy_gateway_testgen.v2.localization import localize_doc
from privacy_gateway_testgen.v2.org import make_org
from privacy_gateway_testgen.v2.renderers import render
from privacy_gateway_testgen.v2.scenario import make_scenario
from privacy_gateway_testgen.v2.validation import validate_dataset_v2, validate_case_v2

CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")


def context(domains=("pii", "payment", "secrets", "infrastructure"), latin_only: bool = False):
    rng = random.Random(21)
    org = make_org(rng, "en", "normal")
    pool = EntityPool(rng, "en", org.as_pool_org())
    scenario = make_scenario("pgt2-trn-00001", rng, org, pool, "en", False, False,
                             latin_only=latin_only)
    ctx = BuildContext(rng=rng, language="en", org=org, pool=pool, domains=domains,
                       doc_language="en", scenario=scenario, attachment_id="ATT-001")
    return ctx, scenario


def build(archetype_id: str, ctx) -> object:
    doc = BY_ID[archetype_id].builder(ctx)
    localize_doc(doc, "en")
    return doc


class ScenarioConsistencyTests(unittest.TestCase):
    def test_shared_values_are_stable(self):
        _ctx, scenario = context()
        first = scenario.shared("infrastructure", "database_endpoint", "db_endpoint")
        second = scenario.shared("infrastructure", "database_endpoint", "db_endpoint")
        self.assertEqual(first.value, second.value)
        self.assertEqual(first.value, scenario.org.database_endpoint.value)

    def test_invoice_and_arithmetic_checks(self):
        ctx, scenario = context(latin_only=True)
        doc = build("invoice", ctx)
        names = {check["check"] for check in scenario.checks}
        self.assertIn("invoice_arithmetic", names)
        self.assertIn("invoice_due_date", names)
        for check in scenario.checks:
            self.assertTrue(check["passed"], check)
        rendered = render(doc, "pdf", "invoice.pdf")
        self.assertIn(scenario.shared("infrastructure", "internal_url", "url").value,
                      rendered.data.decode("latin-1"))

    def test_payroll_and_statement_arithmetic(self):
        ctx, scenario = context()
        build("payroll", ctx)
        build("bank_statement", ctx)
        checks = {check["check"]: check for check in scenario.checks}
        self.assertTrue(checks["payroll_arithmetic"]["passed"])
        self.assertTrue(checks["statement_running_balance"]["passed"])
        self.assertGreater(checks["statement_running_balance"]["details"]["closing_balance"], 0)

    def test_cross_file_database_endpoint_matches(self):
        ctx, scenario = context(("infrastructure", "secrets"))
        invoice = build("invoice", ctx)
        env = build("application_environment_config", ctx)
        url = scenario.shared("infrastructure", "internal_url", "url").value
        api_key = scenario.shared("secrets", "api_key", "api_key").value
        self.assertIn(url, str(invoice.blocks))
        self.assertIn(api_key, str(invoice.blocks))
        self.assertIn(api_key, str(env.record))
        rendered_invoice = render(invoice, "pdf", "invoice.pdf")
        rendered_env = render(env, "env", "prod.env")
        self.assertIn(api_key.encode(), rendered_invoice.data)
        self.assertIn(api_key.encode(), rendered_env.data)


class BundleAndStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(POLICY)
        cls.config = load_v2_config(CONFIG, profile="benchmark-balanced")
        cls.config["total_samples"] = 24
        cls.config["seed"] = 77
        cls.config["distributions"]["attachment_probability"] = 1.0
        cls.config["distributions"]["attachment_count"] = {"2": 1.0}
        cls.config["distributions"]["file_type"] = {
            "docx": 0.3, "xlsx": 0.3, "txt": 0.2, "log": 0.1, "yaml": 0.1,
        }
        cls.config["realism"]["structure_reference_probability"] = 1.0
        cls.dataset = V2Generator(cls.config, cls.policy).generate()

    def test_structure_references_resolve(self):
        cases = [case for case in self.dataset["cases"] if case["structure_references"]]
        self.assertTrue(cases)
        for case in cases:
            for ref in case["structure_references"]:
                self.assertTrue(ref["resolved"], ref)
                self.assertIn(ref["attachment_id"], {item["attachment_id"] for item in case["attachments"]})

    def test_validation_rejects_broken_structure_reference(self):
        case = next(case for case in self.dataset["cases"] if case["structure_references"])
        broken = copy.deepcopy(case)
        broken["structure_references"][0]["value"] = 99999
        broken["structure_references"][0]["resolved"] = True
        self.assertTrue(validate_case_v2(broken, self.policy))

    def test_old_new_bundle_has_traceable_changes(self):
        config = load_v2_config(CONFIG, profile="benchmark-balanced")
        config["total_samples"] = 4
        config["seed"] = 88
        config["distributions"]["attachment_probability"] = 1.0
        config["distributions"]["attachment_count"] = {"2": 1.0}
        config["distributions"]["file_type"] = {"docx": 1.0}
        config["realism"]["same_archetype_bundle_probability"] = 1.0
        config["realism"]["old_new_bundle_probability"] = 1.0
        dataset = V2Generator(config, self.policy).generate()
        old_new = [case for case in dataset["cases"] if case["bundle"]["kind"] == "old_new"]
        self.assertTrue(old_new)
        for case in old_new:
            self.assertEqual(len(case["bundle"]["revision_changes"]), 1)
            self.assertEqual(len(case["attachments"]), 2)
            self.assertEqual(case["attachments"][0]["archetype"], case["attachments"][1]["archetype"])
            self.assertNotEqual(case["attachments"][0]["sha256"], case["attachments"][1]["sha256"])

    def test_cross_file_links_are_consistent(self):
        cases = [case for case in self.dataset["cases"] if case["cross_file_links"]]
        self.assertTrue(cases)
        for case in cases:
            for link in case["cross_file_links"]:
                self.assertTrue(link["consistent"])
                self.assertGreaterEqual(len(link["attachments"]), 2)


if __name__ == "__main__":
    unittest.main()
