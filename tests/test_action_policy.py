import unittest
from agents.action_policy import decide_action

class ActionPolicyTests(unittest.TestCase):
    def item(self,status,required=True): return {'status':status,'required':required}
    def test_priority(self):
        self.assertEqual(decide_action([self.item('needs_review'),self.item('not_met')]),'HUMAN_REVIEW')
        self.assertEqual(decide_action([self.item('not_met'),self.item('unknown')]),'LOW_MATCH')
        self.assertEqual(decide_action([self.item('unknown')],0),'REQUEST_INFO')
        self.assertEqual(decide_action([self.item('unknown')],2),'HUMAN_REVIEW')
        self.assertEqual(decide_action([self.item('evidenced'),self.item('unknown',False)]),'SHORTLIST')
