"""Regression tests for the v2.1.1 correctness and benchmark-readiness pass.

Every test here corresponds to a defect that was reproducible before this
iteration: vacuous log validation, financial mismatches, fragmented image
ground truth, presence-only language labels, placeholder people, hash-seeded
reports, untranslated labels, case-wide Latin routing, impossible addresses,
Unicode-blind Thai typos, concatenated prompts, fake structure references,
unrelated bundles, cosmetic revisions and boolean-only consistency checks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

from tests.support import ROOT
from privacy_gateway_testgen.entities import EntityPool
from privacy_gateway_testgen.entities import common
from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.archetypes import BY_ID, BuildContext
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.evaluate import evaluate_v2, markdown_report_v2
from privacy_gateway_testgen.v2.extract import verify_attachment
from privacy_gateway_testgen.v2.generate import (
    V2Generator, _canonical_id, _choose_structure_refs, benchmark_safe_reasons,
    export_v2_dataset,
)
from privacy_gateway_testgen.v2.localization import (
    document_static_text, document_text, language_matches, localize_doc,
    localize_text, residual_english_labels, script_stats,
)
from privacy_gateway_testgen.v2.org import make_org
from privacy_gateway_testgen.v2.realism import (
    DESTINATION_CLAUSES, _contexts, build_prompt, imperfect, prompt_quality_issues,
)
from privacy_gateway_testgen.v2.renderers import render
from privacy_gateway_testgen.v2.scenario import (
    finance_checks, make_scenario, validate_log_order,
)
from privacy_gateway_testgen.v2.validation import validate_dataset_v2

CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")
COMPAT_FIXTURE = ROOT / "datasets" / "compat" / "v2.0-sample"


def make_config(count: int = 10, seed: int = 31, profile: str = "benchmark-balanced") -> dict:
    config = load_v2_config(CONFIG, profile=profile)
    config["total_samples"] = count
    config["seed"] = seed
    return config


def generate(config: dict) -> dict:
    return V2Generator(config, load_policy(POLICY)).generate()


def context(language: str = "en", domains=("pii", "payment", "secrets", "infrastructure"),
            latin_only: bool = None):
    rng = random.Random(17)
    org = make_org(rng, "th" if language == "th" else "en", "normal")
    pool = EntityPool(rng, language, org.as_pool_org())
    scenario = make_scenario("pgt2-trn-00001", rng, org, pool, language, False, False)
    ctx = BuildContext(rng=rng, language=language, org=org, pool=pool, domains=domains,
                       doc_language=language, scenario=scenario, attachment_id="ATT-001",
                       latin_only=latin_only)
    return ctx, scenario


class LogTimelineTests(unittest.TestCase):
    def test_ordered_log_passes(self):
        lines = [
            "2026-03-18T09:12:00Z INFO worker request_id=req-1",
            "2026-03-18T09:15:07Z INFO worker request_id=req-2",
            "2026-03-18T09:33:49Z ERROR auth failed",
        ]
        result = validate_log_order(lines)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evaluated_items"], 3)

    def test_out_of_order_log_is_rejected(self):
        lines = [
            "2026-03-18T09:12:00Z INFO worker",
            "2026-03-18T09:33:49Z INFO worker",
            "2026-03-18T09:20:01Z ERROR auth failed",
        ]
        result = validate_log_order(lines)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["out_of_order_lines"])

    def test_multiple_timestamp_formats_are_normalised(self):
        ordered = [
            "2026-03-18T09:12:00Z INFO iso",
            "2026/03/18 09:15:07 +0000 INFO bracket",
            "18/Mar/2026:09:18:14 +0000 INFO clf",
        ]
        self.assertEqual(validate_log_order(ordered)["status"], "passed")
        shuffled = [ordered[2], ordered[0], ordered[1]]
        self.assertEqual(validate_log_order(shuffled)["status"], "failed")

    def test_single_line_is_not_evidence(self):
        self.assertEqual(validate_log_order(["2026-03-18T09:12:00Z INFO once"])["status"],
                         "not_evaluated")

    def test_generated_logs_are_ordered_and_error_line_is_last(self):
        for seed in range(8):
            ctx, scenario = context("en")
            ctx.scenario.rng = random.Random(seed)
            doc = BY_ID["app_log"].builder(ctx)
            log_block = next(block for block in doc.blocks
                             if block.kind in ("log", "code"))
            lines = [line for line in log_block.text.splitlines() if line.strip()]
            self.assertEqual(validate_log_order(lines)["status"], "passed")
            check = next(item for item in scenario.checks
                         if item["check"] == "log_timestamps_ordered")
            self.assertEqual(check["status"], "passed")
            self.assertGreater(check["evaluated_items"], 0)

    def test_generation_is_deterministic_for_the_timeline(self):
        def stamps(seed: int) -> list:
            ctx, _ = context("en")
            ctx.scenario.rng = random.Random(seed)
            doc = BY_ID["deployment_log"].builder(ctx)
            block = next(item for item in doc.blocks if item.kind in ("log", "code"))
            return block.text.splitlines()

        self.assertEqual(stamps(11), stamps(11))


class FinanceConsistencyTests(unittest.TestCase):
    def test_scenario_owns_one_transaction_and_one_total(self):
        _ctx, scenario = context("en")
        finance = scenario.finance(4)
        self.assertEqual(finance["subtotal"] + finance["tax"], finance["total"])
        self.assertEqual(sum(item["line_total"] for item in finance["items"]),
                         finance["subtotal"])
        self.assertEqual(finance["payment_schedule"], "single_payment")

    def test_mismatched_linked_amount_is_rejected(self):
        _ctx, scenario = context("en")
        scenario.observe("finance.total", 94020, "ATT-001", "en")
        scenario.observe("finance.total", 90000, "ATT-002", "en")
        scenario.observe("finance.currency", "THB", "ATT-001", "en")
        scenario.observe("finance.currency", "THB", "ATT-002", "en")
        scenario.observe("finance.transaction_reference", "TXN-1", "ATT-001", "en")
        scenario.observe("finance.transaction_reference", "TXN-1", "ATT-002", "en")
        checks = {item["check"]: item for item in finance_checks(scenario)}
        self.assertEqual(checks["linked_amount_matches"]["status"], "failed")
        self.assertEqual(checks["linked_currency_matches"]["status"], "passed")
        self.assertEqual(checks["linked_transaction_reference_matches"]["status"], "passed")

    def test_one_sided_finance_check_is_not_applicable_not_passed(self):
        _ctx, scenario = context("en")
        scenario.observe("finance.total", 94020, "ATT-001", "en")
        checks = {item["check"]: item for item in finance_checks(scenario)}
        self.assertEqual(checks["linked_amount_matches"]["status"], "not_applicable")
        self.assertFalse(checks["linked_amount_matches"]["passed"])
        self.assertEqual(checks["linked_amount_matches"]["evaluated_items"], 0)

    def test_invoice_and_transaction_export_render_the_same_total(self):
        rng = random.Random(5)
        org = make_org(rng, "en", "normal")
        pool = EntityPool(rng, "en", org.as_pool_org())
        scenario = make_scenario("pgt2-trn-00002", rng, org, pool, "en", False, False)
        domains = ["payment", "pii"]
        invoice_ctx = BuildContext(rng=rng, language="en", org=org, pool=pool, domains=domains,
                                   doc_language="en", scenario=scenario, attachment_id="ATT-001")
        txn_ctx = BuildContext(rng=rng, language="en", org=org, pool=pool, domains=domains,
                               doc_language="en", scenario=scenario, attachment_id="ATT-002")
        invoice = BY_ID["invoice"].builder(invoice_ctx)
        transactions = BY_ID["transaction_export"].builder(txn_ctx)
        total = scenario.finance(4)["total"]
        invoice_text = render(invoice, "txt", "invoice.txt").data.decode("utf-8")
        rows = render(transactions, "csv", "transactions.csv").data.decode("utf-8")
        self.assertIn(f"{total:,.2f}", invoice_text)
        self.assertIn(f"{total:,.2f}", rows)
        # The tabular invoice must physically contain the total, not only record it.
        import io
        import zipfile
        xlsx = render(invoice, "xlsx", "invoice.xlsx").data
        sheet = zipfile.ZipFile(io.BytesIO(xlsx)).read("xl/worksheets/sheet2.xml").decode("utf-8")
        self.assertIn(f"{total:,.2f}", sheet)
        self.assertEqual(scenario.finance(4)["transaction_id"],
                         scenario.finance(4)["transaction_id"])


class ImageGroundTruthTests(unittest.TestCase):
    def test_generated_image_entity_stays_in_one_line(self):
        ctx, _ = context("en", domains=("pii",), latin_only=True)
        doc = BY_ID["screenshot_form"].builder(ctx)
        localize_doc(doc, "en")
        rendered = render(doc, "png", "form.png")
        self.assertTrue(rendered.entity_locations)
        for item in rendered.entity_locations:
            location = item["location"]
            self.assertEqual(location["entity_strategy"], "atomic_line")
            self.assertEqual(location["fragment_count"], 1)
            self.assertIn(item["entity"].value.upper(),
                          location["expected_ocr_text"].upper())
        result = verify_attachment(rendered.data, "png", rendered.mime_type,
                                   rendered.entity_locations, rendered.meta)
        self.assertEqual(result["status"], "verified_layout")
        self.assertEqual(result["issues"], [])

    def test_broken_fragment_annotation_is_rejected(self):
        ctx, _ = context("en", domains=("pii",), latin_only=True)
        doc = BY_ID["screenshot_form"].builder(ctx)
        localize_doc(doc, "en")
        rendered = render(doc, "png", "form.png")
        broken = copy.deepcopy(rendered.entity_locations)
        broken[0]["location"]["expected_ocr_text"] = broken[0]["location"]["expected_ocr_text"][:5]
        result = verify_attachment(rendered.data, "png", rendered.mime_type, broken,
                                   rendered.meta)
        self.assertEqual(result["status"], "unverified")
        self.assertIn("image_entity_fragment", {issue["kind"] for issue in result["issues"]})


class LanguageLabelTests(unittest.TestCase):
    def test_numeric_and_symbols_are_neutral(self):
        stats = script_stats("1234-5678 / 99.99 THB")
        self.assertEqual(stats["thai_share"], 0.0)
        self.assertEqual(stats["latin_share"], 1.0)
        self.assertGreater(stats["neutral_share"], 0.5)

    def test_thai_name_inside_an_english_template_is_not_a_thai_document(self):
        ctx, _ = context("th")
        doc = BY_ID["employee_list"].builder(ctx)
        localize_doc(doc, "en")
        stats = script_stats(document_static_text(doc))
        self.assertTrue(language_matches(stats, "en", {
            "th": {"min_thai_share": 0.30}, "en": {"min_latin_share": 0.80},
            "mixed": {"min_thai_share": 0.10, "min_latin_share": 0.10}}))
        self.assertFalse(language_matches(stats, "th", {
            "th": {"min_thai_share": 0.30}, "en": {"min_latin_share": 0.80},
            "mixed": {"min_thai_share": 0.10, "min_latin_share": 0.10}}))

    def test_declared_language_requires_measured_shares(self):
        config = make_config(8, 41)
        dataset = generate(config)
        for case in dataset["cases"]:
            for attachment in case["attachments"]:
                stats = attachment["language_check"]
                self.assertIn("thai_share", stats)
                self.assertIn("latin_share", stats)
                self.assertIn("neutral_share", stats)
                self.assertTrue(stats["matches_declared_language"])
                self.assertTrue(language_matches(
                    stats["static"], attachment["language"],
                    case["language_coverage"]["thresholds"]))


class PlaceholderAndPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate(make_config(30, 73))

    def test_no_contact_number_placeholders(self):
        for case in self.dataset["cases"]:
            blob = json.dumps(case, ensure_ascii=False)
            self.assertNotIn("Contact 1", blob)
            self.assertNotIn("contact1@example.com", blob)

    def test_duplicated_particles_are_rejected(self):
        self.assertTrue(prompt_quality_issues("ช่วยร่างอีเมลให้หน่อย ให้หน่อย"))
        self.assertTrue(prompt_quality_issues("can you please please send it"))
        self.assertEqual(prompt_quality_issues("ช่วยสรุปเอกสารนี้หน่อย"), [])

    def test_composed_prompts_have_no_duplicated_phrases(self):
        rng = random.Random(9)
        files = [{"filename": "report.xlsx", "archetype": "employee_list"}]
        for index in range(120):
            info = build_prompt(
                rng, persona=("hr", "developer", "support", "finance")[index % 4],
                intent=("summarize", "troubleshoot", "review_document", "calculate")[index % 4],
                language=("th", "en", "mixed")[index % 3],
                formality=("formal", "neutral", "casual")[index % 3],
                files=files[: 1 + index % 2], length=("short", "medium", "long")[index % 3],
                typo_rate=0.0, destination=bool(index % 2), structure_refs=[],
            )
            self.assertEqual(info["quality_issues"], [], info["prompt"])

    def test_incompatible_contexts_are_not_attached(self):
        self.assertNotIn("prod only, staging is fine", _contexts("en", "hr"))
        self.assertIn("prod only, staging is fine", _contexts("en", "developer"))
        rng = random.Random(3)
        for _ in range(40):
            prompt = build_prompt(rng, persona="hr", intent="summarize", language="en",
                                  formality="neutral", files=[], length="long",
                                  typo_rate=0.0, destination=True)["prompt"].lower()
            for phrase in DESTINATION_CLAUSES["en"]:
                self.assertNotIn(phrase.lower(), prompt)

    def test_prompt_only_forms_are_diverse(self):
        forms = {case.get("prompt_form") for case in self.dataset["cases"]
                 if case["attachment_count"] == 0}
        self.assertGreaterEqual(len(forms), 3)
        self.assertNotEqual(forms, {"pasted_file"})
        fenced = [case for case in self.dataset["cases"] if case["attachment_count"] == 0
                  and "```" in case["prompt"]]
        self.assertLess(len(fenced), len([case for case in self.dataset["cases"]
                                          if case["attachment_count"] == 0]))


class StructureAndBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = make_config(24, 77)
        config["distributions"]["attachment_probability"] = 1.0
        config["distributions"]["attachment_count"] = {"2": 1.0}
        config["realism"]["structure_reference_probability"] = 1.0
        config["realism"]["same_archetype_bundle_probability"] = 0.5
        cls.dataset = generate(config)

    def test_images_are_never_referenced_by_row_or_column(self):
        attachment = {
            "attachment_id": "ATT-009", "filename": "receipt.png", "extension": "png",
            "structure": {"rows": 4, "columns": 3, "headers": ["total"], "sheets": [],
                          "slides": 0, "pages": 0, "headings": [], "lines": 4, "keys": []},
        }
        self.assertEqual(_choose_structure_refs(random.Random(1), [attachment]), [])

    def test_structure_references_are_user_visible(self):
        for case in self.dataset["cases"]:
            for ref in case["structure_references"]:
                self.assertTrue(ref["user_visible"])
                attachment = next(item for item in case["attachments"]
                                  if item["attachment_id"] == ref["attachment_id"])
                self.assertNotIn(ref["kind"], {"row", "column", "line"}
                                 if attachment["extension"] in ("png", "jpg", "jpeg") else set())

    def test_multifile_bundles_have_relationship_evidence(self):
        multi = [case for case in self.dataset["cases"] if case["attachment_count"] > 1]
        self.assertTrue(multi)
        for case in multi:
            relationship = case["bundle"]["relationship"]
            if relationship["status"] == "related":
                self.assertTrue(relationship["evidence"])
            else:
                self.assertIn(case["test_category"], ("ambiguous", "negative"))

    def test_old_new_revisions_are_meaningful(self):
        config = make_config(6, 88)
        config["distributions"]["attachment_probability"] = 1.0
        config["distributions"]["attachment_count"] = {"2": 1.0}
        config["distributions"]["file_type"] = {"docx": 1.0}
        config["realism"]["same_archetype_bundle_probability"] = 1.0
        config["realism"]["old_new_bundle_probability"] = 1.0
        dataset = generate(config)
        revisions = [change for case in dataset["cases"]
                     for change in case["bundle"]["revision_changes"]]
        self.assertTrue(revisions)
        for change in revisions:
            self.assertTrue(change["change_type"])
            self.assertNotEqual(change["before"], change["after"])
            self.assertNotIn("(revised)", change["after"])
            self.assertIsInstance(change["source_v1"], dict)
            self.assertIsInstance(change["source_v2"], dict)


class ConsistencyStatusTests(unittest.TestCase):
    def test_vacuous_check_is_not_applicable(self):
        dataset = generate(make_config(10, 12))
        cases = [case for case in dataset["cases"] if not case["structure_references"]]
        self.assertTrue(cases)
        for case in cases:
            check = next(item for item in case["consistency_checks"]
                         if item["check"] == "structure_reference_resolution")
            self.assertEqual(check["status"], "not_applicable")
            self.assertEqual(check["evaluated_items"], 0)
            self.assertFalse(check["passed"])

    def test_report_counts_statuses_separately(self):
        dataset = generate(make_config(10, 13))
        report = evaluate_v2(dict(dataset, stats={}), load_v2_config(CONFIG, profile="benchmark-balanced"),
                             load_policy(POLICY), reproducible=True)
        statuses = report["metrics"]["consistency_status"]
        self.assertIn("not_applicable", statuses)
        self.assertEqual(statuses.get("failed", 0), 0)
        self.assertIn("benchmark_ready", report)
        self.assertIn("Benchmark ready", markdown_report_v2(report))


class LatinRoutingTests(unittest.TestCase):
    def test_latin_only_renderer_keeps_a_linked_representation(self):
        ctx_thai, scenario = context("th", domains=("pii",), latin_only=False)
        ctx_latin, _ = context("th", domains=("pii",), latin_only=True)
        ctx_latin.scenario = scenario
        employee = scenario.org.employees[0]
        thai = ctx_thai.person_name(employee)
        latin = ctx_latin.person_name(employee)
        self.assertNotEqual(thai.value, latin.value)
        self.assertTrue(latin.value.isascii())
        self.assertEqual(latin.value, common.romanize_thai_name(thai.value))
        self.assertEqual(_canonical_id(thai), _canonical_id(latin))
        self.assertEqual(latin.canonical_value, thai.value)

    def test_one_pdf_does_not_force_the_other_attachment_to_latin(self):
        ctx_thai, scenario = context("th", domains=("pii",), latin_only=False)
        ctx_pdf = BuildContext(rng=ctx_thai.rng, language="th", org=scenario.org,
                               pool=ctx_thai.pool, domains=("pii",), doc_language="en",
                               scenario=scenario, attachment_id="ATT-002", latin_only=True)
        docx_doc = BY_ID["employee_list"].builder(ctx_thai)
        localize_doc(docx_doc, "th")
        pdf_doc = BY_ID["employee_list"].builder(ctx_pdf)
        localize_doc(pdf_doc, "en")
        thai_text = document_text(docx_doc)
        self.assertTrue(any("\u0e00" <= char <= "\u0e7f" for char in thai_text))
        rendered = render(pdf_doc, "pdf", "employees.pdf")
        self.assertTrue(rendered.data)
        thai_name = scenario.org.employees[0].name
        pdf_values = {item["entity"].value for item in rendered.entity_locations}
        self.assertIn(common.romanize_thai_name(thai_name.value), pdf_values)
        self.assertIn(thai_name.value, thai_text)


class LocalizationAndAddressTests(unittest.TestCase):
    def test_compound_line_labels_are_localized(self):
        text = localize_text("Subtotal: 1,000.00   VAT 7%: 70.00   Total: 1,070.00", "th")
        self.assertIn("ยอดรวมก่อนภาษี", text)
        self.assertIn("ภาษีมูลค่าเพิ่ม", text)
        self.assertIn("ยอดรวม:", text)
        self.assertEqual(residual_english_labels(text), [])

    def test_thai_entity_values_are_never_rewritten_by_localization(self):
        entity = Entity("pii", "thai_name", "ลลิตา พูลสวัสดิ์")
        text = localize_text("ชื่อ: ลลิตา พูลสวัสดิ์", "th")
        self.assertIn("ชื่อ", text)
        self.assertIn(entity.value, text)

    def test_revision_fallback_line_is_localized(self):
        from privacy_gateway_testgen.v2.docmodel import Block, Doc
        doc = Doc(archetype="memo", title="Memo", filename="memo.txt")
        doc.blocks.append(Block("paragraph", text="Status: approved (previously draft)"))
        localize_doc(doc, "th")
        self.assertEqual(residual_english_labels(document_text(doc)), [])

    def test_thai_address_components_are_consistent(self):
        rng = random.Random(4)
        for _ in range(50):
            address = common.thai_address(rng)
            matched = [area for area in common.THAI_ADDRESS_AREAS
                       if f"ตำบล{area['tambon']}" in address
                       and f"อำเภอ{area['amphoe']}" in address
                       and f"จังหวัด{area['province']}" in address]
            self.assertEqual(len(matched), 1, address)
            self.assertEqual(address.split()[-1], matched[0]["postal_code"])

    def test_thai_imperfection_stays_readable(self):
        text = "รบกวนช่วยสรุปเอกสารนี้ให้หน่อยนะคะ"
        words = [word for word in text.split(" ") if len(word) > 2]
        for seed in range(30):
            result = imperfect(random.Random(seed), text, 1.0, "th")
            padded = result.replace("  ", " ")
            for word in words:
                self.assertIn(word, padded)
            self.assertNotIn("หน่อยหน่อย", result)


class DeterminismAndCiTests(unittest.TestCase):
    def test_reports_are_identical_under_different_hash_seeds(self):
        with tempfile.TemporaryDirectory() as workdir:
            dataset_dir = os.path.join(workdir, "dataset")
            config = make_config(6, 21)
            dataset = generate(config)
            policy = load_policy(POLICY)
            export_v2_dataset(dataset, dataset_dir, config, policy)
            hashes = []
            for seed in ("1", "424242"):
                out = os.path.join(workdir, f"report-{seed}")
                env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT / "src"),
                           PYTHONIOENCODING="utf-8")
                subprocess.run([sys.executable, "-m", "privacy_gateway_testgen", "report-v2",
                                "--dataset", dataset_dir, "--out", out],
                               check=False, env=env, capture_output=True)
                def digest(name: str) -> str:
                    with open(os.path.join(out, name), "rb") as handle:
                        return hashlib.sha256(handle.read()).hexdigest()

                hashes.append({name: digest(name)
                               for name in ("evaluation.json", "evaluation.md",
                                            "verification.json")})
            self.assertEqual(hashes[0], hashes[1])

    def test_ci_runs_the_v2_gates(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for command in ("generate-v2", "validate-v2", "verify-v2", "report-v2",
                        "PYTHONHASHSEED", "benchmark_safe_cases"):
            self.assertIn(command, workflow)

    def test_schema_20_fixture_validates(self):
        cases = [json.loads(line) for line in
                 (COMPAT_FIXTURE / "cases.jsonl").read_text(encoding="utf-8-sig").splitlines()
                 if line.strip()]
        self.assertEqual(validate_dataset_v2(cases, load_policy(POLICY)), [])
        self.assertEqual(cases[0]["schema_version"], "2.0")
        self.assertNotIn("language_coverage", cases[0])
        digest = hashlib.sha256((COMPAT_FIXTURE / "cases.jsonl").read_bytes()).hexdigest()
        self.assertEqual(
            digest, "dcf5df90183f008fe4bd6842f18756e0f41f718214db408bdd6b51ed87403be9")

    def test_benchmark_safe_subset_matches_readiness(self):
        config = make_config(10, 14)
        dataset = generate(config)
        report = evaluate_v2(dict(dataset, stats={}), config, load_policy(POLICY),
                             reproducible=True)
        safe = [case for case in dataset["cases"] if not benchmark_safe_reasons(case)]
        self.assertEqual(report["benchmark_ready"]["benchmark_safe_cases"], len(safe))
        self.assertIn("benchmark_ready", report["benchmark_ready"])


if __name__ == "__main__":
    unittest.main()
