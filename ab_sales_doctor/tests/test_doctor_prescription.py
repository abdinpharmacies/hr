from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDoctorPrescription(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doctor = cls.env["ab_doctor"].create({"name": "Dr. Test"})
        cls.product_card = cls.env["ab_product_card"].create({"name": "Doctor Product"})
        cls.product = cls.env["ab_product"].create({
            "product_card_id": cls.product_card.id,
            "code": "DR-PROD",
            "default_price": 10.0,
        })
        cls.extra_card = cls.env["ab_product_card"].create({"name": "Extra Product"})
        cls.extra_product = cls.env["ab_product"].create({
            "product_card_id": cls.extra_card.id,
            "code": "EXTRA-PROD",
            "default_price": 20.0,
        })
        cls.store = cls.env["ab_store"].create({
            "name": "Doctor Test Store",
            "code": "DRSTORE",
            "allow_sale": True,
        })

    def test_sync_creates_only_marked_prescription_products(self):
        header = self.env["ab_sales_header"].create({
            "store_id": self.store.id,
            "is_doctor_prescription": True,
            "doctor_id": self.doctor.id,
        })
        self.env["ab_sales_line"].create({
            "header_id": header.id,
            "product_id": self.product.id,
            "qty_str": "2",
            "sell_price": 10.0,
            "is_doctor_prescription_product": True,
        })
        self.env["ab_sales_line"].create({
            "header_id": header.id,
            "product_id": self.extra_product.id,
            "qty_str": "1",
            "sell_price": 20.0,
            "is_doctor_prescription_product": False,
        })

        header._sync_doctor_prescription_products()

        prescriptions = self.env["ab_product_doctor_prescription"].search([
            ("doctor_id", "=", self.doctor.id),
        ])
        self.assertEqual(prescriptions.product_id, self.product)
        self.assertEqual(prescriptions.qty, 2.0)

    def test_group_user_can_manage_doctor_prescription_products(self):
        user = self.env["res.users"].create({
            "name": "Doctor Prescription User",
            "login": "doctor_prescription_user",
            "email": "doctor-prescription@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        Doctor = self.env["ab_doctor"].with_user(user)
        Prescription = self.env["ab_product_doctor_prescription"].with_user(user)

        Doctor.check_access_rights("create")
        Prescription.check_access_rights("create")
        created = Doctor.create({"name": "User Doctor"})
        self.assertTrue(created)

    def test_pos_payload_defaults_registered_doctor_product_to_rx(self):
        self.env["ab_product_doctor_prescription"].create({
            "doctor_id": self.doctor.id,
            "product_id": self.product.id,
        })
        payload = {
            "header": {
                "is_doctor_prescription": True,
                "doctor_id": self.doctor.id,
            },
            "lines": [
                {"product_id": self.product.id},
                {"product_id": self.extra_product.id},
            ],
        }

        self.env["ab_sales_pos_api"]._default_doctor_prescription_line_flags(payload)

        self.assertTrue(payload["lines"][0]["is_doctor_prescription_product"])
        self.assertFalse(payload["lines"][1]["is_doctor_prescription_product"])

    def test_doctor_prescription_products_use_summed_store_total_balance(self):
        self.product.eplus_serial = 902001
        other_store = self.env["ab_store"].create({
            "name": "Doctor Test Other Store",
            "code": "DRSTORE2",
            "allow_sale": True,
        })
        self.env["ab_product_doctor_prescription"].create({
            "doctor_id": self.doctor.id,
            "product_id": self.product.id,
        })
        self.env["ab_sales_inventory"].create([
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": False,
                "balance": 999.0,
            },
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": self.store.id,
                "balance": 4.0,
            },
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": other_store.id,
                "balance": 6.0,
            },
        ])

        rows = self.env["ab_sales_ui_api"].doctor_prescription_products(
            doctor_id=self.doctor.id,
            store_id=self.store.id,
        )

        row = next(item for item in rows if item["id"] == self.product.id)
        self.assertEqual(row["balance"], 10.0)
        self.assertEqual(row["pos_balance"], 4.0)
