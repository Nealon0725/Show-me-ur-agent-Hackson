import unittest
from agents.ranking import rank_candidates

class RankingTests(unittest.TestCase):
    def test_action_then_score_then_completeness_then_id(self):
        cs=[{"id":"C003","action":"LOW_MATCH","evaluation":{"documented_score":100,"evidence_completeness":100}}, {"id":"C002","action":"REQUEST_INFO","evaluation":{"documented_score":80,"evidence_completeness":80}}, {"id":"C001","action":"SHORTLIST","evaluation":{"documented_score":60,"evidence_completeness":100}}]
        self.assertEqual([c["id"] for c in rank_candidates(cs)], ["C001","C002","C003"])
        self.assertTrue(all(c["evaluation"]["rank_status"] == "provisional" for c in cs))
    def test_stable_id_tiebreak(self):
        cs=[{"id":"C002","action":"SHORTLIST","evaluation":{"documented_score":100,"evidence_completeness":100}}, {"id":"C001","action":"SHORTLIST","evaluation":{"documented_score":100,"evidence_completeness":100}}]
        self.assertEqual([c["id"] for c in rank_candidates(cs)], ["C001","C002"])
