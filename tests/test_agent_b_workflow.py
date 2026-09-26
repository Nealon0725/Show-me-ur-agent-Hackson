import json
import tempfile
import unittest
from pathlib import Path
from agents.workflow import Workflow

class AgentBWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'test.sqlite3'; self.workflow=Workflow(self.path)
    def tearDown(self): self.temp.cleanup()

    def test_demo_end_to_end_actions_and_followup_rerank(self):
        demo=json.loads((Path(__file__).resolve().parents[1]/'data/demo.json').read_text(encoding='utf-8'))
        run=self.workflow.create(demo['jd'], demo['resumes']); run=self.workflow.update(run['id'],'confirm',{})
        self.assertEqual([c['action'] for c in run['candidates']], ['SHORTLIST','REQUEST_INFO','LOW_MATCH'])
        c2=run['candidates'][1]; old_score=c2['evaluation']['documented_score']; self.assertEqual(c2['evaluation']['rank_status'],'provisional')
        run=self.workflow.update(run['id'],'followup',{'candidate_id':'C002','answers':{'xero':{'status':'evidenced','evidence':'Used Xero for invoice reconciliation for one year.'}}})
        c2=run['candidates'][1]; self.assertEqual(c2['action'],'SHORTLIST'); self.assertGreater(c2['evaluation']['documented_score'],old_score); self.assertEqual(c2['evaluation']['rank_status'],'final')

    def test_round_limit_unknown_goes_human_review(self):
        run=self.workflow.create('Required: Xero',['Xero experience not specified.']); run=self.workflow.update(run['id'],'confirm',{})
        for _ in range(2): run=self.workflow.update(run['id'],'followup',{'candidate_id':'C001','answers':{'xero':{'status':'unknown','evidence':'Awaiting more details.'}}})
        self.assertEqual(run['candidates'][0]['action'],'HUMAN_REVIEW'); self.assertEqual(run['candidates'][0]['evaluation']['questions'],[])

    def test_low_match_requires_human_decision(self):
        run=self.workflow.create('Required: Xero',['No Xero experience.']); run=self.workflow.update(run['id'],'confirm',{})
        c=run['candidates'][0]; self.assertEqual(c['action'],'LOW_MATCH'); self.assertEqual(c['state'],'LOW_MATCH_REVIEW'); self.assertIsNone(c['decision'])
        run=self.workflow.update(run['id'],'review',{'candidate_id':'C001','decision':'decline','reason':'Recruiter reviewed the required evidence.'}); self.assertEqual(run['candidates'][0]['state'],'COMPLETE')

    def test_confirmation_validation_and_persistence(self):
        run=self.workflow.create('Required: Excel',['Used Excel for reporting.'])
        with self.assertRaises(ValueError): self.workflow.update(run['id'],'review',{'candidate_id':'C001'})
        run=self.workflow.update(run['id'],'confirm',{}); self.assertEqual(Workflow(self.path).store.get(run['id']),run)
