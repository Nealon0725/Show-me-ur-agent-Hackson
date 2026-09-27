import json
import unittest
from typing import get_args

from agents.schemas import (
    CandidateEvidenceProfile,
    EvidenceStatus,
    JobRequirement,
    RecommendationAction,
    ScreeningResult,
    WorkflowStatus,
    WorkflowState,
)


class SharedSchemaTests(unittest.TestCase):
    def test_evidence_statuses_match_the_agent_contract(self):
        self.assertEqual(
            set(get_args(EvidenceStatus)),
            {"evidenced", "not_met", "unknown", "needs_review"},
        )

    def test_recommendations_are_separate_from_workflow_states(self):
        self.assertEqual(
            set(get_args(RecommendationAction)),
            {"SHORTLIST", "REQUEST_INFO", "HUMAN_REVIEW", "LOW_MATCH"},
        )
        self.assertIn("REQUEST_INFORMATION", get_args(WorkflowStatus))
        self.assertIn("SHORTLIST_REVIEW", get_args(WorkflowStatus))

    def test_required_interface_fields_are_explicit(self):
        self.assertTrue(
            {"id", "label", "description", "type", "required", "scored", "weight", "source"}
            <= JobRequirement.__required_keys__
        )
        self.assertEqual(
            CandidateEvidenceProfile.__required_keys__,
            {"candidate_id", "evidence"},
        )
        self.assertTrue(
            {"documented_score", "possible_score", "evidence_completeness", "action", "details"}
            <= ScreeningResult.__required_keys__
        )
        self.assertEqual(
            WorkflowState.__required_keys__,
            {"job", "criteria_confirmed", "events", "candidates"},
        )

    def test_candidate_evidence_profile_keeps_a_json_shaped_boundary(self):
        profile: CandidateEvidenceProfile = {
            "candidate_id": "C002",
            "evidence": [{
                "criterion_id": "xero",
                "status": "unknown",
                "weight": 2,
                "reason": "No concrete Xero task is stated.",
                "evidence_refs": [],
            }],
            "parser": "fixture",
            "model_usage": {},
            "model_request_id": None,
        }

        self.assertEqual(json.loads(json.dumps(profile)), profile)


if __name__ == "__main__":
    unittest.main()
