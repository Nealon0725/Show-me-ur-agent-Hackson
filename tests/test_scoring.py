import unittest
from agents.scoring import calculate_scores

class ScoringTests(unittest.TestCase):
    def test_three_scores_and_weights(self):
        details = [{"status":"evidenced","weight":2,"scored":True},{"status":"unknown","weight":2,"scored":True},{"status":"evidenced","weight":1,"scored":True}]
        self.assertEqual(calculate_scores(details), {"documented_score":60,"possible_score":100,"evidence_completeness":60})
    def test_not_met_and_needs_review(self):
        details = [{"status":"not_met","weight":2,"scored":True},{"status":"needs_review","weight":1,"scored":True}]
        self.assertEqual(calculate_scores(details), {"documented_score":0,"possible_score":33,"evidence_completeness":67})
    def test_unscored_excluded(self):
        details = [{"status":"evidenced","weight":2,"scored":True},{"status":"not_met","weight":100,"scored":False}]
        self.assertEqual(calculate_scores(details)["documented_score"], 100)
