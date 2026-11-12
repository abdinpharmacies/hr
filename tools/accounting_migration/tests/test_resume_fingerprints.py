"""Fingerprint reuse must preserve scope and never survive a mutation."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from table_resume import ResumeState


class ResumeFingerprintTests(unittest.TestCase):
    def state(self, checks=None):
        state = ResumeState.__new__(ResumeState)
        state.e = SimpleNamespace(physical={'ab_record': {'id': {}, 'name': {}}},
                                  incoming_scalars={}, dynamic=[])
        state.setup = None
        state.state = {'checks': copy.deepcopy(checks or {})}
        state.digest = Mock(side_effect=lambda *args: 'hash-' + str(state.digest.call_count))
        return state

    def test_identical_descriptors_share_one_scan_only_within_remember(self):
        state = self.state({'ab_record': dict(table='ab_record', columns=['id', 'name'], hash='old')})
        state.remember('ab_record', 'copy')
        self.assertEqual(state.digest.call_count, 1)
        self.assertEqual(state.state['checks']['ab_record']['hash'], 'hash-1')
        state.remember('ab_record', 'copy')
        self.assertEqual(state.digest.call_count, 2)
        self.assertEqual(state.state['checks']['ab_record']['hash'], 'hash-2')

    def test_column_order_and_effective_filters_keep_separate_scans(self):
        checks = {
            'ab_record': dict(table='ab_record', columns=['id', 'name'], hash='old'),
            'ordered': dict(table='ab_record', columns=['name', 'id'], hash='old'),
            'subset': dict(table='ab_record', columns=['id'], hash='old'),
            'attachment': dict(table='ab_record', columns=['id', 'name'], attachment_map=True, hash='old'),
            'capture_a': dict(table='ab_record', columns=['id', 'name'], capture='a', hash='old'),
            'capture_b': dict(table='ab_record', columns=['id', 'name'], capture='b', hash='old'),
            'same_capture': dict(table='ab_record', columns=['id', 'name'], capture='a', hash='old'),
            'other': dict(table='other', columns=['id'], hash='unchanged'),
        }
        state = self.state(checks)
        state.remember('ab_record', 'copy')
        self.assertEqual(state.digest.call_count, 6)
        self.assertEqual(state.state['checks']['capture_a']['hash'], state.state['checks']['same_capture']['hash'])
        self.assertEqual(state.state['checks']['other']['hash'], 'unchanged')

    def test_only_complete_unfiltered_fingerprints_can_be_retained(self):
        full = dict(table='ab_record', columns=['id', 'name'], hash='old')
        for descriptor in ({}, {**full, 'hash': ''}, {**full, 'table': 'other'},
                           {**full, 'columns': ['id']}, {**full, 'capture': 'a'},
                           {**full, 'attachment_map': True}):
            with self.subTest(descriptor=descriptor):
                self.assertFalse(self.state({'ab_record': descriptor}).has_full_fingerprint('ab_record'))
        self.assertTrue(self.state({'ab_record': full}).has_full_fingerprint('ab_record'))
        self.assertFalse(self.state().has_full_fingerprint('missing'))

    def test_resume_verification_reads_again_instead_of_using_a_cached_digest(self):
        state = self.state()
        state.remember('ab_record', 'copy')
        state.e.manifest = {}
        state.original_models = set()
        state.e.relationship_policy = 'raw_references_report_only_v1'
        state.records = {}
        state.digest.side_effect = None
        state.digest.return_value = state.state['checks']['ab_record']['hash']
        state.validate()
        self.assertEqual(state.digest.call_count, 2)
