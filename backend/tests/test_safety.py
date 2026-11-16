from __future__ import annotations

import unittest

from backend.agents.validator import ValidatorAgent, find_ungrounded_numbers, sanitize_html
from backend.core.rate_limit import SlidingWindowLimiter
from backend.langchain.llm import extract_json_object
from backend.langchain.tools.calculator import calculate
from backend.langchain.tools.password_reset import reset_password


class SanitizerTests(unittest.TestCase):
    def test_strips_scripts_and_attributes(self) -> None:
        html = '<p onclick="x()">Hi <script>alert(1)</script><strong style="color:red">there</strong></p>'
        self.assertEqual(sanitize_html(html), "<p>Hi <strong>there</strong></p>")

    def test_rejects_javascript_links(self) -> None:
        self.assertEqual(sanitize_html('<a href="javascript:alert(1)">x</a>'), "<a>x</a>")
        self.assertIn('href="https://tau-edu.kz"', sanitize_html('<a href="https://tau-edu.kz">x</a>'))

    def test_plain_text_is_untouched(self) -> None:
        self.assertEqual(sanitize_html("Просто текст"), "Просто текст")


class GroundingTests(unittest.TestCase):
    def test_detects_invented_price(self) -> None:
        evidence = ["Стоимость обучения 1 500 000 тенге в год"]
        self.assertEqual(find_ungrounded_numbers("Стоимость 1 500 000 тенге", evidence), [])
        self.assertEqual(find_ungrounded_numbers("Стоимость 2 100 000 тенге", evidence), ["2 100 000"])

    def test_validator_adds_caution_only_for_synthesized_answers(self) -> None:
        validator = ValidatorAgent(name="validator")
        result = validator.validate(answer="<p>Балл 120</p>", evidence=["проходной балл 75"], has_context=True, synthesized=True)
        self.assertFalse(result["is_valid"])
        self.assertIn("ungrounded_numbers", result["issues"])
        self.assertIn("уточните", result["final_answer"])

        tool_result = validator.validate(answer="<p>Балл 120</p>", evidence=["проходной балл 75"], has_context=True, synthesized=False)
        self.assertTrue(tool_result["is_valid"])


class ToolSafetyTests(unittest.TestCase):
    def test_calculator_rejects_code(self) -> None:
        self.assertEqual(calculate("2 + 3 * 4"), 14.0)
        for payload in ("__import__('os').system('id')", "().__class__", "9**9999999"):
            with self.assertRaises(ValueError):
                calculate(payload)

    def test_password_reset_never_returns_a_password(self) -> None:
        data = reset_password("user")
        self.assertNotIn("temporary_password", data)
        self.assertEqual(data["status"], "manual_required")


class InfraTests(unittest.TestCase):
    def test_rate_limiter_blocks_after_limit(self) -> None:
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.hit("ip")[0])
        self.assertTrue(limiter.hit("ip")[0])
        allowed, retry_after = limiter.hit("ip")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)
        self.assertTrue(limiter.hit("other-ip")[0])

    def test_extract_json_object_handles_fences(self) -> None:
        self.assertEqual(extract_json_object('```json\n{"intents": ["gpa"]}\n```'), {"intents": ["gpa"]})
        self.assertIsNone(extract_json_object("no json"))


if __name__ == "__main__":
    unittest.main()
