# -*- coding: utf-8 -*-
from unittest.mock import patch

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

    def test_submit_store_trans_h_notes_appends_reference_on_new_line(self):
        header = self.env["ab_transfer_header"].new({
            "notes": "4 Existing warehouse notes",
        })

        with patch.object(
                type(header),
                "_get_submit_idempotency_key",
                return_value="ODOO_TRANSFER:119:123",
        ):
            notes = header._build_submit_store_trans_h_notes()

        self.assertEqual(
            notes,
            "4 Existing warehouse notes\nOdoo Transfer: %s\n[ODOO_TRANSFER:119:123]"
            % header.display_name,
        )

    def test_submit_store_trans_h_notes_keeps_option_prefix_with_space(self):
        header = self.env["ab_transfer_header"].new({
            "notes": "4",
        })

        with patch.object(
                type(header),
                "_get_submit_idempotency_key",
                return_value="ODOO_TRANSFER:119:123",
        ):
            notes = header._build_submit_store_trans_h_notes()

        self.assertEqual(
            notes,
            "4 Odoo Transfer: %s [ODOO_TRANSFER:119:123]" % header.display_name,
        )
