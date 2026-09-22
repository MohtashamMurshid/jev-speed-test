import unittest
from uncertainty import calculate, eligible


class ScorePopulationTest(unittest.TestCase):
    def test_scored_failure_excluded_from_point_bootstrap_and_random(self):
        rows = [{'status': 'ok', 'correct': True, 's': 1},
                {'status': 'ok', 'correct': False, 's': .2},
                {'status': 'error', 'correct': False, 's': 1}]
        r = calculate(rows, 's', 1, repetitions=40)
        clean = calculate(rows[:2], 's', 1, repetitions=40)
        self.assertEqual(r['error_auroc'], 1)
        self.assertEqual(r['error_auroc_ci95'], clean['error_auroc_ci95'])
        self.assertEqual(r['accepted'], 1)
        self.assertEqual(r['scored_failures_excluded'], 1)
        self.assertEqual(r['matched_random_deferral']['population'], 2)
        self.assertEqual(r['matched_random_deferral']['expected_error_rate'], .5)

    def test_nan_and_no_errors(self):
        rows = [{'status': 'ok', 'correct': True, 's': 1},
                {'status': 'ok', 'correct': False, 's': float('nan')}]
        r = calculate(rows, 's', None, repetitions=20)
        self.assertIsNone(r['error_auroc'])
        self.assertEqual(r['eligible_valid_scored'], 1)
        self.assertEqual(r['accepted'], 0)


if __name__ == '__main__':
    unittest.main()
