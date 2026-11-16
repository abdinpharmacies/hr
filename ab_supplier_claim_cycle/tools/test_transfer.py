"""Run with: python -m unittest discover -s ab_supplier_claim_cycle/tools."""
import json
from pathlib import Path
import tempfile
import unittest

from claim_transfer import BANK, CASH, Bundle, amount, digest, legacy_runtime, save_json


class TestAmount(unittest.TestCase):
    def test_supported_legacy_formats(self):
        for text, expected in [('7,156.', 7156), ('5,400.00', 5400), ('30,836.25', 30836.25), ('1', 1)]:
            self.assertEqual(amount(text), expected)

    def test_never_guess_invalid_amounts(self):
        for text in ('', 'NaN', '-1', '0', '1,23', '1.234', '7.156,00', 'one hundred'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                amount(text)

    def test_rounding_requires_explicit_policy_and_uses_decimal_half_up(self):
        with self.assertRaises(ValueError):
            amount('68588.855')
        self.assertEqual(amount('68588.855', round_to_cents=True), 68588.86)
        self.assertEqual(amount('17,812.59006', round_to_cents=True), 17812.59)


class TestLegacyRuntime(unittest.TestCase):
    def row(self, **kw):
        return {'id': 1, 'state': 'inventory', 'payment_nature': 'check',
                **{name + '_decision': 'pending' for name in BANK}, **kw}

    def test_future_pending_is_waiting_and_prior_approval_survives(self):
        route, state, current, statuses = legacy_runtime(self.row(purchasing_decision='approved'))
        self.assertEqual(route, BANK)
        self.assertEqual(state, 'in_progress')
        self.assertEqual(current, 'inventory')
        self.assertEqual(statuses['inventory'], 'pending')
        self.assertEqual(statuses['purchasing'], 'approved')
        self.assertEqual(statuses['supplier_accounts'], 'waiting')

    def test_return_resumes_rejecting_stage(self):
        _, state, current, statuses = legacy_runtime(self.row(state='returned_secretarial',
            rejection_department='purchasing', resume_stage='purchasing', purchasing_decision='rejected'))
        self.assertEqual((state, current), ('returned', 'purchasing'))
        self.assertEqual(statuses['inventory'], 'approved')
        self.assertEqual(statuses['purchasing'], 'rejected')
        self.assertEqual(statuses['bank_accounts'], 'waiting')

    def test_cash_closure_and_closed(self):
        route, state, _, statuses = legacy_runtime(self.row(state='ready_to_close', payment_nature='cash'))
        self.assertEqual(route, CASH)
        self.assertEqual(statuses, {'supplier_accounts': 'approved', 'secretarial': 'pending'})
        self.assertEqual(state, 'in_progress')
        self.assertTrue(all(s == 'approved' for s in legacy_runtime(self.row(state='closed'))[3].values()))

    def test_archived_draft_without_payment_has_no_runtime(self):
        self.assertEqual(legacy_runtime(self.row(state='draft', payment_nature=None, active=False))[1:], ('draft', None, {}))

    def test_imported_overdue_deferral_is_preserved(self):
        self.assertEqual(legacy_runtime(self.row(inventory_decision='deferred', inventory_followup_date='2020-01-01'))[3]['inventory'], 'deferred')

    def test_incompatible_current_stage_is_blocked(self):
        with self.assertRaises(ValueError):
            legacy_runtime(self.row(payment_nature='cash', state='inventory'))


class TestBundleIntegrity(unittest.TestCase):
    def test_tampered_binary_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'blobs').mkdir()
            content = b'original evidence'
            sha = digest(content)
            (path / 'blobs' / sha).write_bytes(content)
            save_json(path / 'data.json', {'meta': {'uuid': 'test', 'database': 'test'}, 'tables': {'test': [{'file': {'blob': sha, 'size': len(content)}}]}})
            save_json(path / 'manifest.json', {'format': 1, 'data_sha256': digest((path / 'data.json').read_bytes()), 'counts': {'test': 1}})
            Bundle(path)
            (path / 'blobs' / sha).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                Bundle(path)

    def test_path_traversal_is_blocked(self):
        bundle = Bundle.__new__(Bundle)
        with self.assertRaises(ValueError):
            bundle.blob({'blob': '../outside', 'size': 0})


if __name__ == '__main__':
    unittest.main()
