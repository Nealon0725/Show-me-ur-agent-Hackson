import unittest

from agents.ui_adapter import evaluate_ui_resumes


class UIAdapterTests(unittest.TestCase):
    def test_accounts_resume_maps_to_clearhire_contract(self):
        text = """Avery Tan
Accounts Assistant
2024-01 to 2025-12
Handled supplier invoices and supplier payments for accounts payable.
Raised customer invoices, allocated receipts and followed up collections for accounts receivable.
Performed monthly bank reconciliations and investigated differences.
Used Excel schedules and Xero accounting software for finance tasks.
"""
        result = evaluate_ui_resumes('JD-003', [{'name': 'avery.docx', 'text': text}])
        candidate = result['candidates'][0]
        self.assertEqual(candidate['name'], 'Avery Tan')
        self.assertEqual(candidate['months'], 24)
        self.assertEqual(candidate['label'], 'evidence_complete')
        self.assertTrue(all(item['status'] == 'demonstrated' for item in candidate['criteria']))

    def test_missing_evidence_is_not_treated_as_rejection(self):
        result = evaluate_ui_resumes('JD-001', [{'name': 'casey.pdf', 'text': 'Casey Lim\nLearning Python.'}])
        candidate = result['candidates'][0]
        self.assertNotEqual(candidate['label'], 'evidence_complete')
        self.assertTrue(any(item['analysis_status'] == 'unknown' for item in candidate['criteria']))

    def test_rejects_unknown_job(self):
        with self.assertRaises(ValueError):
            evaluate_ui_resumes('JD-999', [{'name': 'resume.pdf', 'text': 'Candidate\nExperience'}])


if __name__ == '__main__':
    unittest.main()
