import argparse
import copy
import json
import re
from pathlib import Path
import tempfile
import unittest

from common import ACTIONS, ROOT, load_suite
from parity import case_contracts, reference_contract


class PosParityTests(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(ROOT / 'sales_ui_cases.json')
        self.reference = json.loads((ROOT / 'pos_reference.json').read_text())

    def test_every_pos_step_and_expected_value_is_present(self):
        self.assertEqual(case_contracts(self.suite['cases']), self.reference['cases'])
        self.assertEqual(ACTIONS, self.reference['actions'])
        handlers = re.findall(r"case '([^']+)'", (ROOT / 'sales_ui_runner.mjs').read_text())
        self.assertCountEqual(handlers, ACTIONS)

    def test_fixture_terms_prices_and_shortage_policy_match(self):
        self.assertEqual(self.suite['fixtures']['contracts'], self.reference['contracts'])
        self.assertEqual(self.suite['fixtures']['promotion'], self.reference['promotion'])
        self.assertEqual(self.suite['out_of_stock'], self.reference['out_of_stock'])
        self.assertEqual({key: value['unit_price'] for key, value in self.suite['records']['products'].items()},
                         self.reference['unit_prices'])

    def test_missing_intermediate_assertion_is_detected(self):
        changed = copy.deepcopy(self.suite['cases'])
        case = next(case for case in changed if case['id'] == 'CONTRACT_MANUAL_PROMO')
        index = next(index for index, step in enumerate(case['steps']) if isinstance(step.get('expected'), dict))
        del case['steps'][index]
        self.assertNotEqual(case_contracts(changed), self.reference['cases'])

    def test_legacy_report_reuses_records_with_current_cases(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'reports') as directory:
            saved = copy.deepcopy(self.suite)
            saved['records']['store_id'] = 135
            saved['credentials']['login'] = 'saved-login'
            saved['cases'] = saved['cases'][:1]
            saved['cases'][0]['steps'] = []
            path = Path(directory) / 'selected-suite.json'
            path.write_text(json.dumps(saved))
            restored = load_suite(path)
            self.assertEqual(restored['cases'], self.suite['cases'])
            self.assertEqual(restored['records']['store_id'], 135)
            self.assertEqual(restored['credentials']['login'], 'saved-login')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pos-root', type=Path)
    args, remaining = parser.parse_known_args()
    if args.pos_root:
        suite = json.loads((args.pos_root / 'sales_ui_cases.json').read_text())
        actions = json.loads((args.pos_root / 'actions.json').read_text())['actions']
        reference = json.loads((ROOT / 'pos_reference.json').read_text())
        actual = reference_contract(suite, actions)
        if any(actual[key] != reference[key] for key in actual):
            raise SystemExit('POS reference drift detected; review scenario parity')
        print('Current POS checkout matches the captured scenario reference')
    (ROOT / 'reports').mkdir(mode=0o700, exist_ok=True)
    unittest.main(argv=['selftest_parity.py', *remaining])
