"""Non-database checks for security-upgrade acceptance reporting."""
from copy import deepcopy
import unittest

from audit_security_upgrade import compare


class TestSecurityUpgradeAudit(unittest.TestCase):
    def snapshots(self):
        prefix = 'supplier_claim_group_'
        before = {
            'database': 'example', 'business': {'claims': {'rows': 2, 'sha256': 'original'}},
            'groups': {prefix + name: i for i, name in enumerate(('participant', 'user', 'reviewer', 'admin', 'inventory'), 1)},
            'members': {prefix + 'participant': [10], prefix + 'inventory': [20]},
        }
        after = deepcopy(before)
        del after['groups'][prefix + 'inventory']
        del after['members'][prefix + 'inventory']
        after['members'][prefix + 'participant'] = [10, 20]
        return before, after

    def test_preserved_data_and_membership_pass(self):
        before, after = self.snapshots()
        self.assertEqual(compare(before, after), [])

    def test_lost_user_is_detected(self):
        before, after = self.snapshots()
        after['members']['supplier_claim_group_participant'] = [10]
        self.assertIn('Department users lost Participant membership', compare(before, after))

    def test_changed_data_is_detected_even_with_same_count(self):
        before, after = self.snapshots()
        after['business']['claims']['sha256'] = 'changed'
        self.assertIn('Business data changed: claims', compare(before, after))

    def test_recreated_group_id_is_detected(self):
        before, after = self.snapshots()
        after['groups']['supplier_claim_group_admin'] = 99
        self.assertIn('Retained group ID changed: supplier_claim_group_admin', compare(before, after))
