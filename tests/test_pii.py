import json
import unittest

from agents.model_provider import OpenAIResumeParser
from agents.parsers import parse_jd
from agents.pii import redact_contact_pii
from agents.screening import evaluate


class PIIRedactionTests(unittest.TestCase):
    def test_redacts_email_and_singapore_phone_numbers(self):
        text = "Email: vinson@example.com\nPhone: +65 9123 4567\nOffice: 6123-4567"

        redacted = redact_contact_pii(text)

        self.assertEqual(
            redacted,
            "Email: [EMAIL]\nPhone: [PHONE]\nOffice: [PHONE]",
        )

    def test_model_receives_redacted_text_and_evidence_keeps_original(self):
        captured = {}

        def fake_request(payload):
            captured.update(payload)
            return {
                "output_text": json.dumps({
                    "evaluations": [{
                        "criterion_id": "xero",
                        "status": "evidenced",
                        "reason": "The resume describes using Xero.",
                        "evidence_lines": [1],
                    }]
                })
            }

        resume = "Used Xero for invoicing. Contact vinson@example.com or +65 9123 4567."
        criteria = parse_jd("Required: Xero")["criteria"]
        parser = OpenAIResumeParser("test-key", request_json=fake_request)

        result = evaluate(resume, criteria, resume_parser=parser)
        model_input = json.loads(captured["input"])
        sent_text = model_input["resume_lines"][0]["text"]

        self.assertNotIn("vinson@example.com", sent_text)
        self.assertNotIn("9123 4567", sent_text)
        self.assertIn("[EMAIL]", sent_text)
        self.assertIn("[PHONE]", sent_text)
        self.assertEqual(
            result["details"][0]["evidence_refs"][0]["text"],
            resume,
        )


if __name__ == "__main__":
    unittest.main()
