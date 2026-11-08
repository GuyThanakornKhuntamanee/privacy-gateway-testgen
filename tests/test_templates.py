import random
import unittest

from .support import SRC  # noqa: F401

from privacy_gateway_testgen.models import DOMAINS
from privacy_gateway_testgen.templates import TEMPLATES, build_draft
from privacy_gateway_testgen.validation import length_bucket


class TemplateTests(unittest.TestCase):
    def test_template_ids_are_unique(self):
        ids = [template.id for template in TEMPLATES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_template_produces_exact_spans_and_matching_domains(self):
        for language in ("th", "en", "mixed"):
            for template in TEMPLATES:
                for seed in range(3):
                    with self.subTest(template=template.id, language=language, seed=seed):
                        draft = build_draft(template, random.Random(seed), language, 2)
                        prompt = draft["prompt"]
                        spans = draft["spans"]
                        self.assertTrue(prompt)
                        expected_domains = {
                            span.entity.domain for span in spans if span.entity.detection_expected
                        }
                        self.assertEqual(expected_domains, set(template.domains))
                        self.assertEqual(bool(expected_domains), not template.negative)
                        previous_end = -1
                        for span in spans:
                            self.assertGreaterEqual(span.start, previous_end)
                            previous_end = span.end
                            self.assertEqual(prompt[span.start:span.end], span.entity.value)

    def test_length_classes_match_measured_prompt_length(self):
        for language in ("th", "en", "mixed"):
            for template in TEMPLATES:
                draft = build_draft(template, random.Random(99), language, 2)
                self.assertEqual(length_bucket(draft["prompt"]), template.length_class,
                                 f"{template.id}/{language}: {len(draft['prompt'])} chars")

    def test_style_and_domain_coverage_in_template_library(self):
        domains = set()
        styles = set()
        for template in TEMPLATES:
            domains.update(template.domains)
            if template.negative:
                styles.add("negative")
            if template.contextual:
                styles.add("contextual")
            if len(template.domains) >= 2:
                styles.add("mixed_domain")
            styles.add(template.length_class)
        self.assertEqual(domains, set(DOMAINS))
        self.assertTrue({"short", "medium", "long", "contextual", "mixed_domain", "negative"}.issubset(styles))

    def test_all_four_domains_appear_in_one_template(self):
        template = next(template for template in TEMPLATES if template.id == "long_all_four")
        draft = build_draft(template, random.Random(7), "mixed", 3)
        domains = {span.entity.domain for span in draft["spans"]}
        self.assertEqual(domains, set(DOMAINS))

    def test_templates_use_at_least_five_entity_types_per_positive_domain(self):
        used = {domain: set() for domain in DOMAINS}
        for template in TEMPLATES:
            if template.negative:
                continue
            for seed in range(2):
                draft = build_draft(template, random.Random(seed), "en", 3)
                for span in draft["spans"]:
                    if span.entity.detection_expected:
                        used[span.entity.domain].add(span.entity.entity_type)
        for domain, types in used.items():
            self.assertGreaterEqual(len(types), 5, f"{domain}: {sorted(types)}")


if __name__ == "__main__":
    unittest.main()
