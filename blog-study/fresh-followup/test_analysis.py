"""Offline unit tests. All records here are synthetic test fixtures, not results."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import analyze as a


def record(**kw):
    return dict({'status': 'ok', 'predicted': 'intent', 'nativeConfidence': 1.,
                 'probability': .95, 'latencyMs': 10., 'billedCostUsd': .01,
                 'reservedUsd': .1}, **kw)


def case(id='b1', **kw):
    return dict({'id': id, 'cohort': 'banking', 'expected': 'intent',
                 'jev': record(), 'gemini': record(), 'fallback': None,
                 'cascadeWallMs': 12., 'baselineWallMs': 15.}, **kw)


class Statistics(unittest.TestCase):
    def test_wilson_known_bounds_and_empty(self):
        self.assertEqual(a.wilson(0, 0), [None, None])
        self.assertAlmostEqual(a.wilson(0, 100)[1], .03699349820698568)
        self.assertAlmostEqual(a.wilson(100, 100)[0], .9630065017930143)
        with self.assertRaises(ValueError): a.wilson(2, 1)

    def test_gate_boundaries_failures_missing_nonfinite(self):
        self.assertTrue(a.gate(record(), 'jev'))
        self.assertTrue(a.gate(record(), 'gemini'))
        for score in [None, True, float('nan'), float('inf'), .999]:
            self.assertFalse(a.gate(record(nativeConfidence=score), 'jev'))
        self.assertFalse(a.gate(record(status='error'), 'jev'))
        self.assertFalse(a.gate(record(probability=.94999), 'gemini'))

    def test_paired_resampling_preserves_strata_and_pairing(self):
        result = a.paired_bootstrap([1, 1, 0], [0, 0, 1], ['A', 'A', 'B'], 100)
        self.assertEqual(result['gains'], 2)
        self.assertEqual(result['losses'], 1)
        self.assertAlmostEqual(result['difference_pp'], 100/3)
        self.assertEqual(result['ci95_pp'], [result['difference_pp']]*2)
        self.assertEqual(result, a.paired_bootstrap([1, 1, 0], [0, 0, 1], ['A', 'A', 'B'], 100))
        self.assertEqual(a.paired_bootstrap([1, 0], [1, 0], ['A', 'A'], 100)['ci95_pp'], [0., 0.])

    def test_cost_sources_separate_unknown_not_zero(self):
        c = a.cost_summary([record(estimatedCostUsd=.02), {'estimatedCostUsd': .03, 'reservedUsd': 1}, {'reservedUsd': 2}])
        self.assertAlmostEqual(c['accounted_total_usd'], 2.04)
        self.assertEqual(c['accounted_basis_counts'], dict.fromkeys(a.COST_FIELDS, 1))
        self.assertEqual(c['source_totals_usd_not_additive']['billedCostUsd'], .01)
        self.assertIsNone(a.cost_summary([{}])['accounted_total_usd'])
        self.assertEqual(a.cost_summary([{'billedCostUsd': 0, 'reservedUsd': 2}])['accounted_total_usd'], 0)
        with self.assertRaises(ValueError): a.cost_summary([{'billedCostUsd': -1}])

    def test_failures_stay_in_primary_denominator_and_timing(self):
        c = case('b2', jev=record(status='error'), fallback=record(status='error'), gemini=record(status='error'), cascadeWallMs=100)
        s, _ = a.analyze_cases([case(), c], 100)
        self.assertEqual(s['systems']['cascade']['accuracy_all_attempts']['rate'], .5)
        self.assertEqual(s['systems']['cascade']['timing']['all_outcomes']['n'], 2)
        self.assertEqual(s['systems']['cascade']['timing']['valid_chosen_response_only']['n'], 1)
        self.assertEqual(s['systems']['cascade']['failures'], 1)
        self.assertEqual(s['systems']['cascade']['timing']['all_outcomes']['median_ms'], 56.)

    def test_oos_safety_uses_actual_fallback_not_separate_baseline(self):
        oos = case('o1', cohort='oos', expected=None, jev=record(nativeConfidence=.5),
                   fallback=record(probability=.2), gemini=record(probability=1))
        s, rows = a.analyze_cases([case(), oos], 100)
        self.assertEqual(s['oos']['gemini_baseline_accept_false_acceptance']['count'], 1)
        self.assertEqual(s['oos']['safety_accept_false_acceptance']['count'], 0)
        self.assertTrue(rows[-1]['safety_human_defer'])
        self.assertEqual(s['physical_calls_all_cohorts']['calls'], 5)
        self.assertEqual(s['systems']['cascade']['cost']['calls'], 1)

    def test_gain_against_failed_baseline(self):
        s, _ = a.analyze_cases([case(gemini=record(status='error'))], 100)
        c = s['comparisons']['cascade_minus_gemini']
        self.assertEqual(c['gains_against_failed_baseline'], 1)
        self.assertEqual(c['difference_pp'], 100)

    def test_no_missing_fallback_or_duplicate_case(self):
        with self.assertRaises(ValueError): a.analyze_cases([case(jev=record(nativeConfidence=.2))], 100)
        with self.assertRaises(ValueError): a.analyze_cases([case(), case()], 100)
        with self.assertRaises(ValueError): a.analyze_cases([case(fallback=record())], 100)

    def test_local_results_and_partial_rejection(self):
        s, _ = a.analyze_cases([case(local=record(latencyMs=.2))], 100)
        self.assertEqual(s['systems']['local']['accuracy_all_attempts']['rate'], 1.)
        self.assertIsNone(s['systems']['local']['cost']['compute_cost_usd'])
        with self.assertRaises(ValueError): a.analyze_cases([case(local=record()), case('b2')], 100)

    def test_export_determinism_in_temp_directories(self):
        data = [case(), case('b2', gemini=record(status='error')),
                case('o1', cohort='oos', expected=None)]
        with tempfile.TemporaryDirectory() as tmp:
            p, q = Path(tmp)/'first', Path(tmp)/'second'
            s, rows = a.analyze_cases(data, 100)
            a.render(s, rows, p)
            s2, rows2 = a.analyze_cases(copy.deepcopy(data), 100)
            a.render(s2, rows2, q)
            self.assertEqual(sorted(f.name for f in p.iterdir()), sorted(f.name for f in q.iterdir()))
            for f in p.iterdir(): self.assertEqual(f.read_bytes(), (q/f.name).read_bytes(), f.name)
            self.assertTrue((p/'accuracy.svg').stat().st_size > 1000)
            self.assertTrue((p/'oos.png').stat().st_size > 1000)

    def test_complete_runner_schema_adapter_synthetic_only(self):
        # A full-shape disk fixture tests the adapter, never writes study outputs.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'calls').mkdir(); (root/'paths').mkdir()
            def put(path, value): path.write_text(json.dumps(value))
            bank = [{'id': f'b{i}', 'expected': 'intent'} for i in range(500)]
            oos = [{'id': f'o{i}', 'expected': None} for i in range(100)]
            protocol = {'seed': a.SEED, 'thresholds': {'jevNative': 1., 'geminiProbability': .95},
                        'priorStudyUsd': 1.028709, 'budgetUsd': 8.9, 'totalStudyCapUsd': 10}
            for name, value in [('protocol.json', protocol), ('cases.json', bank), ('oos.json', oos),
                                ('manifest.json', {'contractHash': 'synthetic-unit-test', 'contract': {'protocol': protocol, 'cases': bank, 'oos': oos}})]:
                put(root/name, value)
            sequence = 0
            for cohort, items in [('cases', bank), ('oos', oos)]:
                for c in items:
                    for path, system in [('cascade', 'jev'), ('baseline', 'gemini')]:
                        key = c['id']+'_'+path
                        callkey = key+'__'+system
                        r = record(key=callkey, sequence=sequence, caseId=c['id'], cohort=cohort,
                                   path=path, system=system, expected=c['expected'],
                                   correct=c['expected'] is not None, accountedUsd=.01)
                        sequence += 1
                        put(root/'calls'/(callkey+'.result.json'), r)
                        put(root/'calls'/(callkey+'.reservation.json'), {'key': callkey, 'amount': .1})
                        p = {'key': key, 'caseId': c['id'], 'cohort': cohort, 'path': path,
                             'expected': c['expected'], 'predicted': 'intent', 'status': 'ok',
                             'correct': c['expected'] is not None, 'jevAccepted': path == 'cascade',
                             'safetyAccepted': True, 'latencyMs': 12., 'timing': 'measured-live-sequential',
                             'components': [callkey], 'accountedUsd': .01}
                        put(root/'paths'/(key+'.result.json'), p)
                        put(root/'paths'/(key+'.start.json'), {'key': key})
            data, metadata = a.load_inputs(root)
            self.assertEqual(len(data), 600)
            self.assertEqual(len(metadata['input_sha256']), 4804)
            self.assertAlmostEqual(metadata['budget_accounting']['fresh_runner_conservative_usd'], 12.)
            (root/'local').mkdir()
            protocol_hash = metadata['input_sha256']['protocol.json']
            put(root/'local'/'threshold.json', {'threshold': .5, 'protocol_sha256': protocol_hash})
            provenance = dict.fromkeys(('all_official_test_normalized_overlap', 'development_overlap', 'calibration_overlap', 'fresh_test_overlap'), 0)
            provenance.update(protocol_sha256=protocol_hash, config={}, training_rows_retained=10)
            put(root/'local'/'training-provenance.json', provenance)
            put(root/'local'/'summary.json', {'versions': {}, 'timing': 'synthetic test', 'compute_cost': 'not priced'})
            for name, cases in [('banking', bank), ('oos', oos)]:
                put(root/'local'/(name+'-predictions.json'), [dict(c, status='ok', predicted='intent', correct=c['expected'] is not None,
                    score=.6, accepted=True, cpuMs=.1, wallMs=.2) for c in cases])
            data, metadata = a.load_inputs(root)
            self.assertEqual(data[0]['local']['latencyMs'], .1)
            self.assertEqual(metadata['local_metadata']['metrics_recomputed']['oos']['accepted']['count'], 100)
            (root/'paths'/'b0_cascade.result.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Incomplete run'): a.load_inputs(root)

    def test_unfinished_scope_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in [('protocol.json', {}), ('cases.json', []), ('oos.json', [])]:
                (root/name).write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, '500 banking'): a.load_inputs(root)


if __name__ == '__main__':
    unittest.main()
