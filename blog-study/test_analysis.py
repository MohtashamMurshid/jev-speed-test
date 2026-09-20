import unittest
import numpy as np
from analyze import eligible_scores, discrimination, failure_category


class DelayedAuditRegressions(unittest.TestCase):
    def test_failed_partial_score_is_excluded_from_both_populations(self):
        rows = [
            {'status': 'ok', 'correct': True, 'probability': .9},
            {'status': 'ok', 'correct': False, 'probability': .1},
            {'status': 'provider-mismatch', 'correct': False, 'probability': .99},
        ]
        scores = eligible_scores(rows, 'probability')
        self.assertTrue(np.isnan(scores[2]))
        valid = [r for r in rows if r['status'] == 'ok']
        point = discrimination([r['correct'] for r in valid], [r['probability'] for r in valid])
        mask = np.isfinite(scores)
        bootstrap_population = discrimination(np.array([r['correct'] for r in rows])[mask], scores[mask])
        self.assertEqual(point, bootstrap_population)
        self.assertEqual(point['auroc'], 1.)

    def test_success_does_not_become_failure_from_irrelevant_text(self):
        self.assertIsNone(failure_category({'status': 'ok', 'error': 'could not parse'}))

    def test_preserved_errors_have_specific_categories(self):
        cases = [
            ({'status': 'error', 'response': {'error': {'code': 502}}}, 'upstream_error'),
            ({'status': 'error', 'response': {'error': {'code': 400}}}, 'api_rejection'),
            ({'status': 'error', 'error': 'No object generated: could not parse the response.'}, 'parse_error'),
            ({'status': 'error', 'error': 'No object generated: response did not match schema.'}, 'schema_error'),
            ({'status': 'timeout'}, 'timeout'),
            ({'status': 'truncated'}, 'truncated'),
            ({'status': 'error', 'response': {'choices': [{'message': {'refusal': 'Not allowed'}}]}}, 'refusal'),
        ]
        for row, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(failure_category(row), expected)


if __name__ == '__main__':
    unittest.main()
