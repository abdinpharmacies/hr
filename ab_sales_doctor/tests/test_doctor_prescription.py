from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


class _FakeDoctorConnection:
    existing_ids = []
    created_id = 0
    create_values = None
    search_domain = None
    write_called = False

    def __init__(self, env):
        self.env = env

    def execute_kw(self, model, method, args, kwargs=None):
        kwargs = kwargs or {}
        if model == "ab_doctor" and method == "fields_get":
            return {
                "name": {"type": "char"},
                "code": {"type": "char"},
                "phone": {"type": "char"},
                "specialty": {"type": "char"},
                "active": {"type": "boolean"},
            }
        if model == "ab_doctor" and method == "search":
            type(self).search_domain = args[0]
            return type(self).existing_ids
        if model == "ab_doctor" and method == "create":
            type(self).create_values = args[0]
            return type(self).created_id
        if model == "ab_doctor" and method == "write":
            type(self).write_called = True
            return True
        raise AssertionError(f"Unexpected remote call: {model}.{method}")

    @classmethod
    def reset(cls, created_id=0, existing_ids=None):
        cls.existing_ids = existing_ids or []
        cls.created_id = created_id
        cls.create_values = None
        cls.search_domain = None
        cls.write_called = False


@tagged("post_install", "-at_install")
class TestDoctorPrescription(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doctor = cls.env["ab_doctor"].create({
            "name": "Dr. Test",
            "code": "DRTEST",
            "specialty": "General",
        })
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

    def _create_legacy_doctor(self, name, code=None, specialty=None, active=True):
        self.env.cr.execute(
            """
            INSERT INTO ab_doctor
                (name, code, specialty, active, create_uid, create_date, write_uid, write_date)
            VALUES
                (%s, %s, %s, %s, %s, now(), %s, now())
            RETURNING id
            """,
            [name, code, specialty, active, self.env.uid, self.env.uid],
        )
        doctor_id = self.env.cr.fetchone()[0]
        return self.env["ab_doctor"].browse(doctor_id)

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

    def test_doctor_display_name_includes_code_name_and_specialty(self):
        doctor = self.env["ab_doctor"].create({
            "name": "Dr. Test",
            "code": "D001",
            "specialty": "Cardiology",
        })

        self.assertEqual(doctor.display_name, "D001 - Dr. Test - Cardiology")

    def test_doctor_display_name_omits_empty_parts(self):
        no_code = self._create_legacy_doctor(
            "Dr. No Code",
            specialty="Pediatrics",
        )
        no_specialty = self._create_legacy_doctor(
            "Dr. No Specialty",
            code="D002",
        )
        name_only = self._create_legacy_doctor("Dr. Name Only")

        self.assertEqual(no_code.display_name, "Dr. No Code - Pediatrics")
        self.assertEqual(no_specialty.display_name, "D002 - Dr. No Specialty")
        self.assertEqual(name_only.display_name, "Dr. Name Only")

    def test_doctor_display_name_search_by_code(self):
        doctor = self.env["ab_doctor"].create({
            "name": "Dr. Code Search",
            "code": "D003",
            "specialty": "Neurology",
        })

        found = self.env["ab_doctor"].search([("display_name", "ilike", "D003")])

        self.assertIn(doctor, found)

    def test_doctor_display_name_search_by_specialty(self):
        doctor = self.env["ab_doctor"].create({
            "name": "Dr. Specialty Search",
            "code": "D004",
            "specialty": "Dermatology",
        })

        found = self.env["ab_doctor"].search([("display_name", "ilike", "Dermatology")])

        self.assertIn(doctor, found)

    def test_doctor_create_accepts_valid_codes_and_preserves_case(self):
        doctors = self.env["ab_doctor"].create([
            {"name": "Dr. Letters", "code": "ABC", "specialty": "General"},
            {"name": "Dr. Digits", "code": "123", "specialty": "General"},
            {"name": "Dr. Mixed", "code": "AbC123", "specialty": "General"},
        ])

        self.assertEqual(doctors.mapped("code"), ["ABC", "123", "AbC123"])

    def test_doctor_create_rejects_missing_code_and_specialty(self):
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({"name": "Dr. Missing Code", "specialty": "General"})
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({"name": "Dr. Blank Code", "code": "   ", "specialty": "General"})
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({"name": "Dr. Missing Specialty", "code": "MISSPEC"})
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({"name": "Dr. Blank Specialty", "code": "BLANKSPEC", "specialty": "   "})

    def test_doctor_create_rejects_invalid_code_formats(self):
        invalid_codes = ["ASK 300", "ASK-300", "ASK_300", "ASK@300", "دكتور"]
        for index, code in enumerate(invalid_codes):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                self.env["ab_doctor"].create({
                    "name": f"Dr. Invalid Code {index}",
                    "code": code,
                    "specialty": "General",
                })

    def test_doctor_create_rejects_case_insensitive_existing_duplicates(self):
        self.env["ab_doctor"].create({
            "name": "Dr. Duplicate Active",
            "code": "dupactive",
            "specialty": "General",
        })
        self._create_legacy_doctor("Dr. Duplicate Archived", code="duparchived", specialty="General", active=False)

        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({
                "name": "Dr. Duplicate Active New",
                "code": "DUPACTIVE",
                "specialty": "General",
            })
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create({
                "name": "Dr. Duplicate Archived New",
                "code": "DUPARCHIVED",
                "specialty": "General",
            })

    def test_doctor_create_rejects_multi_create_duplicate_codes(self):
        with self.assertRaises(ValidationError):
            self.env["ab_doctor"].create([
                {"name": "Dr. Multi A", "code": "MULTIDUP", "specialty": "General"},
                {"name": "Dr. Multi B", "code": "multidup", "specialty": "General"},
            ])

    def test_existing_incomplete_doctor_allows_unrelated_edits(self):
        doctor = self._create_legacy_doctor("Dr. Legacy Incomplete")

        doctor.write({"phone": "01000000000"})

        self.assertEqual(doctor.phone, "01000000000")

    def test_existing_doctor_validates_changed_code_and_specialty(self):
        doctor = self._create_legacy_doctor("Dr. Legacy Change")

        with self.assertRaises(ValidationError):
            doctor.write({"code": "BAD-CODE"})
        with self.assertRaises(ValidationError):
            doctor.write({"specialty": "   "})

        doctor.write({"code": "LEGACY1", "specialty": "General"})
        self.assertEqual(doctor.code, "LEGACY1")
        self.assertEqual(doctor.specialty, "General")

    def test_pos_create_main_doctor_validates_before_connection(self):
        api = self.env["ab_sales_pos_api"]

        with patch(
            "odoo.addons.ab_sales_doctor.models.ab_sales_pos_api.OdooConnectionSingleton",
            side_effect=AssertionError("Connection should not be opened for invalid doctor values."),
        ):
            with self.assertRaises(ValidationError):
                api.pos_create_main_doctor({
                    "name": "Dr. POS Invalid",
                    "code": "BAD-CODE",
                    "specialty": "General",
                })

    def test_pos_create_main_doctor_rejects_duplicate_main_code_without_update(self):
        api = self.env["ab_sales_pos_api"]
        _FakeDoctorConnection.reset(existing_ids=[999])

        with patch(
            "odoo.addons.ab_sales_doctor.models.ab_sales_pos_api.OdooConnectionSingleton",
            _FakeDoctorConnection,
        ), patch.object(
            type(self.env["ab_odoo_replication"]),
            "replicate_model",
            side_effect=AssertionError("Duplicate doctor must not be replicated locally."),
        ):
            with self.assertRaises(UserError):
                api.pos_create_main_doctor({
                    "name": "Dr. POS Duplicate",
                    "code": "POSDUP",
                    "specialty": "General",
                })

        self.assertEqual(_FakeDoctorConnection.search_domain, [("code", "=ilike", "POSDUP")])
        self.assertFalse(_FakeDoctorConnection.write_called)
        self.assertIsNone(_FakeDoctorConnection.create_values)

    def test_pos_create_main_doctor_create_only_selects_replicated_doctor(self):
        local_doctor = self.env["ab_doctor"].create({
            "name": "Dr. POS Created",
            "code": "POSCREATED",
            "specialty": "General",
        })
        api = self.env["ab_sales_pos_api"]
        _FakeDoctorConnection.reset(created_id=local_doctor.id)

        with patch(
            "odoo.addons.ab_sales_doctor.models.ab_sales_pos_api.OdooConnectionSingleton",
            _FakeDoctorConnection,
        ), patch.object(
            type(self.env["ab_odoo_replication"]),
            "replicate_model",
            return_value=True,
        ) as replicate_model:
            result = api.pos_create_main_doctor({
                "name": "Dr. POS Created",
                "code": "POSCREATED",
                "specialty": "General",
            })

        self.assertEqual(_FakeDoctorConnection.search_domain, [("code", "=ilike", "POSCREATED")])
        self.assertEqual(_FakeDoctorConnection.create_values, {
            "name": "Dr. POS Created",
            "code": "POSCREATED",
            "specialty": "General",
            "active": True,
        })
        self.assertFalse(_FakeDoctorConnection.write_called)
        replicate_model.assert_called_once_with("ab_doctor")
        self.assertEqual(result["id"], local_doctor.id)
        self.assertEqual(result["display_name"], local_doctor.display_name)

    def test_group_user_can_manage_doctor_prescription_products(self):
        user = self.env["res.users"].create({
            "name": "Doctor Prescription User",
            "login": "doctor_prescription_user",
            "email": "doctor-prescription@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        Doctor = self.env["ab_doctor"].with_user(user)
        Prescription = self.env["ab_product_doctor_prescription"].with_user(user)

        Doctor.check_access_rights("create")
        Prescription.check_access_rights("create")
        created = Doctor.create({
            "name": "User Doctor",
            "code": "USERDOC",
            "specialty": "General",
        })
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
