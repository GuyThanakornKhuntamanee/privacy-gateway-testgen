import unittest

from .support import SRC  # noqa: F401

from privacy_gateway_testgen.builder import PromptBuilder
from privacy_gateway_testgen.models import Entity


class PromptBuilderTests(unittest.TestCase):
    def test_thai_text_offsets_are_exact(self):
        builder = PromptBuilder()
        prefix = "ลูกค้า "
        builder.text(prefix)
        builder.entity(Entity("pii", "thai_name", "สมชาย ใจดี"))
        builder.text(" โทร ")
        builder.entity(Entity("pii", "thai_phone", "081-234-5678"))
        prompt = builder.build()
        self.assertEqual(prompt, "ลูกค้า สมชาย ใจดี โทร 081-234-5678")
        self.assertEqual(len(builder.spans), 2)
        for span in builder.spans:
            self.assertEqual(prompt[span.start:span.end], span.entity.value)
        self.assertEqual(builder.spans[0].start, len(prefix))

    def test_multiline_and_adjacent_entities(self):
        builder = PromptBuilder()
        builder.line("BEGIN")
        builder.entity(Entity("secrets", "api_key", "sk_example_fake_a"))
        builder.entity(Entity("secrets", "access_token", "at_example_fake_b"))
        builder.line()
        prompt = builder.build()
        for span in builder.spans:
            self.assertEqual(prompt[span.start:span.end], span.entity.value)
        self.assertEqual(builder.spans[0].end, builder.spans[1].start)

    def test_annotations_are_sorted_by_construction(self):
        builder = PromptBuilder()
        builder.text("a ")
        builder.entity(Entity("infrastructure", "internal_ipv4", "10.0.0.1"))
        builder.text(" b ")
        builder.entity(Entity("pii", "email_address", "a.b@example.com"))
        spans = builder.spans
        self.assertEqual([span.start for span in spans], sorted(span.start for span in spans))


if __name__ == "__main__":
    unittest.main()
