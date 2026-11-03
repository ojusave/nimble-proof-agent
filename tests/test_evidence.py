import json
import unittest

from adapters.demo import SAMPLE_RESUME
from workflows.evidence import MAX_SCAN, select_passages, evidence_summary
from workflows.prompts import assessment_task


class EvidenceTests(unittest.TestCase):
    def test_late_requirements_and_application_survive_navigation(self):
        text = 'Python Developer — Example employer\n' + '[Navigation](https://example.org/) ' * 1100
        tail = '\nQualifications: Python integrations. Remote within the United States. Salary: USD 120,000 per year. Apply using this application form.'
        text += tail
        selected = select_passages(text, 'Python developer remote US salary', 4800)
        joined = '\n'.join(p['text'] for p in selected)
        self.assertIn('Remote within the United States.', joined)
        self.assertIn('Apply using this application form.', joined)
        self.assertLessEqual(sum(len(p['text']) for p in selected), 4800)
        for p in selected:
            self.assertEqual(text[p['start']:p['end']], p['text'])

    def test_adjacent_chunks_merge_without_bridging_unselected_text(self):
        text = 'An ordinary sentence. ' * 80
        selected = select_passages(text, 'ordinary', 2000)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['text'], text.strip())
        text = 'Identity. ' * 65 + 'Boring navigation. ' * 700 + 'Python required. Apply now.'
        selected = select_passages(text, 'Python', 1000)
        self.assertGreater(len(selected), 1)
        self.assertLess(selected[0]['end'], selected[-1]['start'])

    def test_scan_limit_is_reported(self):
        text = 'x' * (MAX_SCAN + 100)
        summary = evidence_summary(text, select_passages(text, '', 1000))
        self.assertTrue(summary['scan_limited'])
        self.assertEqual(summary['source_characters'], MAX_SCAN + 100)
        self.assertEqual(summary['scanned_characters'], MAX_SCAN)

    def test_serialized_budget_preserves_unicode_preferences_and_requirements(self):
        preferences = 'Remote; compensation €120,000; ' + 'é' * 1400
        requirements = [{'id': 'R1', 'text': preferences}]
        listing = {'id': 'a', 'title': 'Python engineer', 'url': 'https://example.org/job',
                   'text': 'Python required. Apply now. ' * 3000}
        task, evidence, resume = assessment_task(SAMPLE_RESUME * 30, preferences, requirements, listing)
        self.assertLessEqual(len(task), 9800)
        payload = json.loads(task.split('\n', 1)[1])
        self.assertEqual(payload['requirements'], requirements)
        self.assertEqual(payload['preferences'], preferences)
        self.assertTrue(evidence['passages'])
        self.assertTrue(resume)
