"""Prompt realism, archetype coverage and configuration tests."""

from __future__ import annotations

import random
import unittest

from tests.support import ROOT
from privacy_gateway_testgen.v2.archetypes import ARCHETYPES
from privacy_gateway_testgen.v2.config import load_v2_config, load_profiles
from privacy_gateway_testgen.v2.realism import build_prompt, imperfect
from privacy_gateway_testgen.v2.renderers import SUPPORTED_FORMATS

CONFIG = str(ROOT / "configs" / "v2" / "default.json")


class RealismTests(unittest.TestCase):
    def test_imperfection_is_configurable_and_visible(self):
        text = "Please summarize this report for the customer before Friday"
        changed = 0
        for seed in range(20):
            result = imperfect(random.Random(seed), text, 1.0, "en")
            if result != text:
                changed += 1
        self.assertGreaterEqual(changed, 15)
        self.assertEqual(imperfect(random.Random(1), text, 0.0, "en"), text)

    def test_prompts_are_diverse_and_human(self):
        prompts = []
        rng = random.Random(42)
        personas = ["developer", "hr", "finance", "manager", "support", "security_engineer"]
        intents = ["troubleshoot", "summarize", "compare", "extract_fields", "review_document", "calculate"]
        languages = ["th", "en", "mixed"]
        files = [{"filename": "prod.env", "archetype": "application_environment_config"},
                 {"filename": "report.xlsx", "archetype": "employee_list"}]
        for index in range(30):
            info = build_prompt(
                rng,
                persona=personas[index % len(personas)],
                intent=intents[index % len(intents)],
                language=languages[index % len(languages)],
                formality=("formal", "neutral", "casual")[index % 3],
                files=files[: 1 + index % 2],
                length=("short", "medium", "long")[index % 3],
                typo_rate=0.15,
            )
            prompts.append(info["prompt"])
        self.assertGreaterEqual(len(set(prompts)), 24)
        forbidden = ("detect the pii", "personally identifiable information", "sensitive information",
                     "please analyze the following")
        for prompt in prompts:
            self.assertGreater(len(prompt), 4)
            for phrase in forbidden:
                self.assertNotIn(phrase, prompt.lower())

    def test_prompt_without_attachment_can_be_vague(self):
        rng = random.Random(7)
        info = build_prompt(rng, persona="developer", intent="troubleshoot", language="th",
                            formality="casual", files=[], length="short", typo_rate=0.2)
        self.assertTrue(info["prompt"])
        self.assertIn(info["template_key"], ("ref", "vague"))

    def test_attachment_names_are_not_corrupted_by_typos(self):
        files = [{"filename": "management_deck.pptx", "archetype": "management_deck"}]
        seen = 0
        for seed in range(20):
            info = build_prompt(random.Random(seed), persona="developer", intent="inspect_config",
                                language="th", formality="casual", files=files,
                                length="medium", typo_rate=1.0)
            if "management_deck.pptx" in info["prompt"]:
                seen += 1
            self.assertNotIn("managgement", info["prompt"])
        self.assertGreaterEqual(seen, 10)


class LibraryCoverageTests(unittest.TestCase):
    def test_all_required_file_types_are_supported(self):
        required = {
            "txt", "csv", "json", "pdf", "png", "jpg", "jpeg", "docx", "xlsx", "pptx",
            "yaml", "yml", "xml", "log", "md", "env", "ini", "conf", "toml", "sql", "tf",
            "py", "js", "ts", "java", "go",
        }
        self.assertTrue(required.issubset(set(SUPPORTED_FORMATS)), required - set(SUPPORTED_FORMATS))

    def test_archetype_categories_cover_the_brief(self):
        categories = {item.category for item in ARCHETYPES}
        for required in ("HR", "Finance", "Sales", "Management", "Healthcare", "IT", "Operations", "CRM"):
            self.assertIn(required, categories)
        self.assertGreaterEqual(len(ARCHETYPES), 40)
        print_names = {"employee_list", "payroll", "invoice", "incident_report", "kubernetes_manifest",
                       "application_environment_config", "app_log", "source_code", "management_deck",
                       "screenshot_terminal", "scanned_invoice"}
        self.assertTrue(print_names.issubset({item.id for item in ARCHETYPES}))

    def test_profiles_load_and_validate(self):
        profiles = load_profiles(str(ROOT / "configs" / "v2" / "profiles.json"))
        for name in ("benchmark-balanced", "real-world-enterprise", "thai-enterprise",
                     "developer-security", "office-documents", "ocr", "negative-hard"):
            self.assertIn(name, profiles)
            config = load_v2_config(CONFIG, profile=name)
            self.assertEqual(config["profile"], name)
            self.assertIn("file_type", config["distributions"])
            self.assertIn("persona", config["distributions"])


if __name__ == "__main__":
    unittest.main()
