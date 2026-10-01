import json
import unittest
from pathlib import Path

from agents.parsers import parse_jd
from agents.screening import evaluate


ROOT = Path(__file__).resolve().parents[1]


class CandidateEvidenceFixtureTests(unittest.TestCase):
    def test_ground_truth_matches_demo_evaluation(self):
        demo = json.loads(
            (ROOT / "data" / "demo.json").read_text(encoding="utf-8")
        )
        fixture = json.loads(
            (ROOT / "data" / "ground_truth" / "candidate_evidence.json")
            .read_text(encoding="utf-8")
        )

        expected_by_id = {
            candidate["candidate_id"]: candidate["evidence"]
            for candidate in fixture["candidates"]
        }

        for number, resume in enumerate(demo["resumes"], start=1):
            candidate_id = f"C{number:03d}"
            result = evaluate(resume, parse_jd(demo["jd"])["criteria"])

            actual = {
                detail["id"]: {
                    "status": detail["status"],
                    "weight": detail["weight"],
                }
                for detail in result["details"]
            }
            expected = {
                evidence["criterion_id"]: {
                    "status": evidence["status"],
                    "weight": evidence["weight"],
                }
                for evidence in expected_by_id[candidate_id]
            }

            self.assertEqual(actual, expected)

    def test_fixture_has_unique_ids_and_allowed_statuses(self):
        fixture = json.loads(
            (ROOT / "data" / "ground_truth" / "candidate_evidence.json")
            .read_text(encoding="utf-8")
        )
        allowed_statuses = {
            "evidenced",
            "not_met",
            "unknown",
            "needs_review",
        }

        candidate_ids = [
            candidate["candidate_id"]
            for candidate in fixture["candidates"]
        ]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))

        for candidate in fixture["candidates"]:
            criterion_ids = [
                evidence["criterion_id"]
                for evidence in candidate["evidence"]
            ]
            self.assertEqual(len(criterion_ids), len(set(criterion_ids)))

            for evidence in candidate["evidence"]:
                self.assertIn(evidence["status"], allowed_statuses)
