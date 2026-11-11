from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAbSalesContractStoreRestriction(TransactionCase):
    def setUp(self):
        super().setUp()
        self.allowed_store = self.env["ab_store"].sudo().create({
            "name": "Allowed Contract Store",
            "code": "ALW-CNTR",
        })
        self.blocked_store = self.env["ab_store"].sudo().create({
            "name": "Blocked Contract Store",
            "code": "BLK-CNTR",
        })
        self.contract = self.env["ab_contract"].sudo().create({
            "name": "Restricted Contract",
            "allowed_store_ids": [(6, 0, [self.allowed_store.id])],
        })

    def test_restricted_contract_can_be_selected_on_prepending_bill(self):
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.blocked_store.id,
            "contract_id": self.contract.id,
        })

        self.assertEqual(header.status, "prepending")
        self.assertEqual(header.contract_id, self.contract)

    def test_restricted_contract_blocks_pending_bill(self):
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.blocked_store.id,
            "contract_id": self.contract.id,
        })

        with self.assertRaises(ValidationError):
            header.write({"status": "pending"})

        self.assertEqual(header.status, "prepending")

    def test_unrestricted_contract_allows_pending_bill(self):
        contract = self.env["ab_contract"].sudo().create({
            "name": "Unrestricted Contract",
        })
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.blocked_store.id,
            "contract_id": contract.id,
        })

        header.write({"status": "pending"})

        self.assertEqual(header.status, "pending")
