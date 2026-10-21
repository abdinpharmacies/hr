import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from common import ACTIONS, ROOT, load_suite, local_url


class CallcenterCliTests(unittest.TestCase):
    def test_fifteen_scenarios_and_twenty_one_actions(self):
        suite = load_suite(ROOT / 'sales_ui_cases.json')
        self.assertEqual(len(suite['cases']), 15)
        self.assertEqual(len(ACTIONS), 21)
        for case in suite['cases']:
            total = sum(suite['records']['products'][line['product']]['unit_price'] * line['qty'] for line in case['lines'])
            self.assertAlmostEqual(total, case['expected']['gross_total'])

    def test_cli_discovery_never_requires_credentials_or_database(self):
        for flag in ['--help', '--list-actions', '--list-cases', '--validate']:
            result = subprocess.run([sys.executable, str(ROOT / 'run_sales_ui.py'), flag],
                                    input='', text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_case_fails_before_connection(self):
        result = subprocess.run([sys.executable, str(ROOT / 'run_sales_ui.py'), '--case', 'MISSING', '--validate'],
                                input='', text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unknown cases', result.stderr)

    def test_submit_requires_opt_in_and_strict_sequence(self):
        suite = load_suite(ROOT / 'sales_ui_cases.json', ['CASH'])
        suite['cases'][0]['steps'][-2]['action'] = 'submit'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'suite.json'
            path.write_text(json.dumps(suite))
            with self.assertRaisesRegex(ValueError, 'allow-submit'):
                load_suite(path)
            self.assertEqual(len(load_suite(path, allow_submit=True)['cases']), 1)
            broken = copy.deepcopy(suite)
            broken['cases'][0]['steps'].insert(-1, {'action': 'clear_contract'})
            path.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                load_suite(path, allow_submit=True)

    def test_bad_actions_and_amounts_rejected(self):
        for mutation in ['action', 'amount', 'intermediate']:
            suite = load_suite(ROOT / 'sales_ui_cases.json', ['CASH'])
            if mutation == 'action':
                suite['cases'][0]['steps'][1]['action'] = 'invented_action'
            elif mutation == 'amount':
                suite['cases'][0]['expected']['gross_total'] = float('nan')
            else:
                suite['cases'][0]['steps'][1]['expected'] = {'customer_pay': float('nan')}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'suite.json'
                path.write_text(json.dumps(suite))
                with self.assertRaises(ValueError):
                    load_suite(path)

    def test_password_reset_requires_explicit_apply_without_connecting(self):
        for script in ['prepare_test_data.py', 'prepare_sales_scenarios.py']:
            result = subprocess.run([sys.executable, str(ROOT / script), '--reset-password'],
                                    input='', text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--reset-password requires', result.stderr)

    def test_local_url_policy(self):
        for value in ['http://localhost:4095', 'http://127.0.0.11:5069', 'http://[::1]:5069']:
            self.assertEqual(local_url(value), value)
        for value in ['https://example.com', 'http://user:secret@localhost', 'http://localhost/web',
                      'http://localhost?db=x', 'http://localhost/#fragment', 'http://localhost:0']:
            with self.assertRaises(ValueError):
                local_url(value)

    def test_unconfigured_records_fail_without_database_access(self):
        from qa_orm import configured_records
        with self.assertRaisesRegex(ValueError, 'QA record ID'):
            configured_records(load_suite(ROOT / 'sales_ui_cases.json'))

    def test_report_paths_and_embedded_credentials_are_rejected(self):
        for mutation in ['path', 'password']:
            suite = load_suite(ROOT / 'sales_ui_cases.json', ['CASH'])
            if mutation == 'path':
                suite['cases'][0]['id'] = '../outside'
            else:
                suite['credentials']['password'] = 'not-a-real-secret'
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'suite.json'
                path.write_text(json.dumps(suite))
                with self.assertRaises(ValueError):
                    load_suite(path)


if __name__ == '__main__':
    unittest.main()
