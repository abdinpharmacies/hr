# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestTransferTypeNotes(TransactionCase):
    def test_format_transfer_notes_prefixes_number_and_space(self):
        api = self.env["ab_transfer_pos_api"]

        self.assertEqual(
            api._format_transfer_notes("4", "Damaged items"),
            "4 Damaged items",
        )

    def test_format_transfer_notes_requires_transfer_type(self):
        api = self.env["ab_transfer_pos_api"]

        with self.assertRaises(UserError):
            api._format_transfer_notes("", "Damaged items")
