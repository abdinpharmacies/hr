import uuid
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _
from odoo.addons.ab_odoo_replication.models_inherit.models_inherit import AbOdooReplicationOnlyAllowed

from .fake_eplus import FakeEplusConnection, UnsupportedFakeEplusSQL
from .json_loader import SalesTestJSONLoader


class BlockedScenario(Exception):
    def __init__(self, missing):
        self.missing = missing
        super().__init__("\n".join(missing))


class SalesTestRunner:
    FLOAT_TOLERANCE = 0.0001
    PRODUCT_ORIGINS = {"local", "imported", "special_imported", "chemical", "other"}
    CONTRACT_ORIGIN_FIELDS = {
        "local": "local_product_discount",
        "imported": "imported_product_discount",
        "special_imported": "special_import_product_discount",
        "chemical": "local_made_product_discount",
        "other": "other_product_discount",
    }
    PROMO_PERCENT_MODES = {"on_order", "cheapest_product", "specific_products"}

    def __init__(self, env, case):
        self.env = env
        self.case = case
        self.created_records = []
        self.header = None
        self.fake_connection = None
        self.keep_generated_records = False

    def run(self):
        try:
            scenario = self._load_scenario()
            self._validate_scenario(scenario)
            actual = self._execute_scenario(scenario)
            failures = self._compare(scenario, actual)
            if failures:
                return self._finish("fail", "\n".join(failures))
            return self._finish("pass", _("Scenario passed."))
        except BlockedScenario as blocked:
            return self._finish("blocked", "\n".join(blocked.missing))
        except (UserError, ValidationError, UnsupportedFakeEplusSQL) as error:
            return self._finish("blocked", str(error))
        except Exception as error:
            return self._finish("fail", repr(error))
        finally:
            self._cleanup_generated_records()

    def _finish(self, status, details):
        summary = details.splitlines()[0] if details else ""
        self.case.sudo().write({
            "configuration_state": "blocked" if status == "blocked" else "ready",
            "last_status": status,
            "last_run_date": fields.Datetime.now(),
            "last_result_summary": summary,
            "last_result_details": details,
        })
        return status

    def _load_scenario(self):
        scenario = SalesTestJSONLoader.get_scenario(self.case.scenario_code)
        if not scenario:
            raise BlockedScenario([_("Scenario %s is not present in test_cases.json.") % self.case.scenario_code])
        return scenario

    def _validate_scenario(self, scenario):
        missing = []
        source = scenario["source"]
        lines = scenario["lines"]
        if not self._source_int(scenario, "sto_id"):
            missing.append(_("Missing source.sto_id."))
        if not self._source_int(scenario, "sth_id"):
            missing.append(_("Missing source.sth_id."))
        if not lines:
            missing.append(_("Scenario has no lines."))

        for line in lines:
            prefix = _("JSON scenario %(scenario)s line %(line)s") % {
                "scenario": scenario["code"],
                "line": line.get("sequence"),
            }
            for field_name in ("itm_id", "c_id"):
                if SalesTestJSONLoader.is_blank(line["source"].get(field_name)):
                    missing.append(_("%(prefix)s is missing source.%(field)s.") % {
                        "prefix": prefix,
                        "field": field_name,
                    })
            for field_name in ("qnty", "itm_sell", "itm_cost"):
                if SalesTestJSONLoader.is_blank(line["inputs"].get(field_name)):
                    missing.append(_("%(prefix)s is missing inputs.%(field)s.") % {
                        "prefix": prefix,
                        "field": field_name,
                    })
            if SalesTestJSONLoader.is_blank(line["expected"].get("expected_itm_dis_per")):
                missing.append(_("%s is missing expected.expected_itm_dis_per.") % prefix)

        contract_inputs = self._contract_inputs(scenario)
        if self._has_contract_input(scenario):
            if SalesTestJSONLoader.is_blank(contract_inputs.get("paid_percentage")):
                missing.append(_("Missing inputs.contract.paid_percentage."))
            missing.extend(self._validate_contract_discount_inputs(scenario))

        if self._needs_promo_config(scenario):
            missing.extend(self._validate_promo_inputs(scenario))

        doctor_inputs = self._doctor_inputs(scenario)
        if SalesTestJSONLoader.to_bool(doctor_inputs.get("is_prescription")):
            if SalesTestJSONLoader.is_blank(doctor_inputs.get("name")):
                missing.append(_("Missing inputs.doctor.name for doctor prescription scenario."))

        if missing:
            raise BlockedScenario(missing)

    @staticmethod
    def _contract_inputs(scenario):
        return dict((scenario.get("inputs") or {}).get("contract") or {})

    @staticmethod
    def _promo_inputs(scenario):
        return dict((scenario.get("inputs") or {}).get("promo") or {})

    @staticmethod
    def _doctor_inputs(scenario):
        return dict((scenario.get("inputs") or {}).get("doctor") or {})

    @staticmethod
    def _pos_session_inputs(scenario):
        return dict((scenario.get("inputs") or {}).get("pos_session") or {})

    @staticmethod
    def _line_contract_inputs(line):
        return dict((line.get("inputs") or {}).get("contract") or {})

    @staticmethod
    def _line_product_inputs(line):
        return dict((line.get("inputs") or {}).get("product") or {})

    @staticmethod
    def _line_promo_inputs(line):
        return dict((line.get("inputs") or {}).get("promo") or {})

    @staticmethod
    def _has_contract_input(scenario):
        return bool(SalesTestRunner._contract_inputs(scenario))

    @staticmethod
    def _needs_promo_config(scenario):
        return (scenario.get("workflow_type") or "").strip().lower() == "promo"

    @classmethod
    def _contract_origin_discount_value(cls, contract_inputs, origin):
        origin_discounts = contract_inputs.get("origin_discounts") or {}
        if not SalesTestJSONLoader.is_blank(origin_discounts.get(origin)):
            return origin_discounts.get(origin)
        field_name = cls.CONTRACT_ORIGIN_FIELDS.get(origin)
        if field_name and not SalesTestJSONLoader.is_blank(contract_inputs.get(field_name)):
            return contract_inputs.get(field_name)
        return None

    @classmethod
    def _validate_contract_discount_inputs(cls, scenario):
        missing = []
        contract_inputs = cls._contract_inputs(scenario)
        product_rule_values = {}
        product_origin_values = {}
        for line in scenario["lines"]:
            product_serial = SalesTestJSONLoader.to_int((line.get("source") or {}).get("itm_id"))
            prefix = _("JSON scenario %(scenario)s line %(line)s") % {
                "scenario": scenario["code"],
                "line": line.get("sequence"),
            }
            line_contract_inputs = cls._line_contract_inputs(line)
            product_card_discount = line_contract_inputs.get("product_card_discount")
            if not SalesTestJSONLoader.is_blank(product_card_discount):
                previous = product_rule_values.get(product_serial)
                current = SalesTestJSONLoader.to_float(product_card_discount)
                if previous is not None and abs(previous - current) > cls.FLOAT_TOLERANCE:
                    missing.append(
                        _("%(prefix)s has a product_card_discount that conflicts with another line for itm_id %(itm_id)s.")
                        % {"prefix": prefix, "itm_id": product_serial}
                    )
                product_rule_values[product_serial] = current

            product_inputs = cls._line_product_inputs(line)
            origin = str(product_inputs.get("origin") or "").strip()
            if origin:
                if origin not in cls.PRODUCT_ORIGINS:
                    missing.append(_("%(prefix)s has unsupported inputs.product.origin: %(origin)s.") % {
                        "prefix": prefix,
                        "origin": origin,
                    })
                    continue
                previous_origin = product_origin_values.get(product_serial)
                if previous_origin and previous_origin != origin:
                    missing.append(
                        _("%(prefix)s has an origin that conflicts with another line for itm_id %(itm_id)s.")
                        % {"prefix": prefix, "itm_id": product_serial}
                    )
                product_origin_values[product_serial] = origin

        for line in scenario["lines"]:
            product_serial = SalesTestJSONLoader.to_int((line.get("source") or {}).get("itm_id"))
            prefix = _("JSON scenario %(scenario)s line %(line)s") % {
                "scenario": scenario["code"],
                "line": line.get("sequence"),
            }
            expected_discount = abs(SalesTestJSONLoader.to_float(line["expected"].get("expected_itm_dis_per")))
            if expected_discount <= cls.FLOAT_TOLERANCE:
                continue
            if product_serial in product_rule_values:
                continue
            origin = product_origin_values.get(product_serial)
            if not origin:
                missing.append(
                    _(
                        "%(prefix)s expects a contract discount but has no product-card rule and no "
                        "inputs.product.origin for the production origin discount lookup."
                    )
                    % {"prefix": prefix}
                )
                continue
            if SalesTestJSONLoader.is_blank(cls._contract_origin_discount_value(contract_inputs, origin)):
                missing.append(
                    _(
                        "%(prefix)s expects a contract discount but inputs.contract has no discount value "
                        "for product origin %(origin)s."
                    )
                    % {"prefix": prefix, "origin": origin}
                )
        return missing

    @classmethod
    def _validate_promo_inputs(cls, scenario):
        missing = []
        promo_inputs = cls._promo_inputs(scenario)
        if not promo_inputs:
            return [_("Missing inputs.promo configuration for promo scenario.")]
        if SalesTestJSONLoader.is_blank(promo_inputs.get("name")):
            missing.append(_("Missing inputs.promo.name for promo scenario."))

        apply_disc_on = str(promo_inputs.get("apply_disc_on") or "on_order").strip() or "on_order"
        valid_modes = cls.PROMO_PERCENT_MODES | {"fixed_price", "incentives"}
        if apply_disc_on not in valid_modes:
            missing.append(_("Unsupported inputs.promo.apply_disc_on: %s.") % apply_disc_on)

        has_product_scope = any(
            SalesTestJSONLoader.to_bool(cls._line_promo_inputs(line).get("in_product_scope"))
            for line in scenario["lines"]
        )
        has_domain_scope = not SalesTestJSONLoader.is_blank(promo_inputs.get("rule_products_domain"))
        if apply_disc_on == "specific_products":
            has_discount_scope = any(
                SalesTestJSONLoader.to_bool(cls._line_promo_inputs(line).get("in_discount_scope"))
                for line in scenario["lines"]
            )
            if not has_discount_scope:
                missing.append(_("Missing inputs.promo.in_discount_scope on at least one line."))
        elif not has_product_scope and not has_domain_scope:
            missing.append(
                _(
                    "Missing promotion product scope. Provide line inputs.promo.in_product_scope "
                    "or inputs.promo.rule_products_domain."
                )
            )

        if apply_disc_on in cls.PROMO_PERCENT_MODES and SalesTestJSONLoader.is_blank(promo_inputs.get("disc_percent")):
            missing.append(_("Missing inputs.promo.disc_percent for promo scenario."))
        if apply_disc_on == "fixed_price" and SalesTestJSONLoader.is_blank(promo_inputs.get("fixed_price")):
            missing.append(_("Missing inputs.promo.fixed_price for fixed-price promo scenario."))
        if apply_disc_on == "cheapest_product":
            if SalesTestJSONLoader.is_blank(promo_inputs.get("rule_min_qty")):
                missing.append(_("Missing inputs.promo.rule_min_qty for cheapest-product promo scenario."))
            elif SalesTestJSONLoader.to_int(promo_inputs.get("rule_min_qty")) < 2:
                missing.append(_("inputs.promo.rule_min_qty must be at least 2 for cheapest-product promos."))
        return missing

    def _execute_scenario(self, scenario):
        self.fake_connection = FakeEplusConnection(scenario)
        with self._replica_fixture_create_guard():
            fixtures = self._prepare_fixtures(scenario)
            payload = self._build_payload(scenario, fixtures)

        HeaderModel = type(self.env["ab_sales_header"])
        ReplicaModel = type(self.env["ab_replica_db"])

        def fake_get_connection(recordset):
            return self.fake_connection

        def fake_get_current_from_config(recordset):
            return fixtures["replica_db"]

        with patch.object(HeaderModel, "get_connection", fake_get_connection), \
                patch.object(ReplicaModel, "get_current_from_config", fake_get_current_from_config):
            result = self.env["ab_sales_pos_api"].sudo().pos_submit(payload)

        header_id = result.get("id") if isinstance(result, dict) else False
        if header_id:
            self.header = self.env["ab_sales_header"].sudo().browse(header_id).exists()
            if self.header:
                self.created_records.append(self.header)

        return {
            "result": result,
            "header": self.header,
            "eplus_header": self.fake_connection.header,
            "eplus_lines": self.fake_connection.lines,
            "header_updates": self.fake_connection.header_updates,
            "committed": self.fake_connection.committed,
        }

    def _prepare_fixtures(self, scenario):
        prefix = "ABST-%s-%s" % (scenario["code"], uuid.uuid4().hex[:8])
        uom_category = self._create("ab_product_uom_category", {
            "name": prefix + " UoM",
            "active": True,
        })
        uom = self._create("ab_product_uom", {
            "name": prefix + " Unit",
            "category_id": uom_category.id,
            "factor": 1.0,
            "active": True,
        })
        store = self._create("ab_store", {
            "name": prefix + " Store",
            "code": prefix[:16],
            "allow_sale": True,
            "eplus_serial": self._source_int(scenario, "sto_id"),
            "ip1": "127.0.0.1",
        })
        replica_db = self._create("ab_replica_db", {
            "name": prefix + " Replica",
            "db_serial": 900000000 + int(uuid.uuid4().hex[:6], 16),
            "allowed_sales_store_ids": [(6, 0, [store.id])],
            "default_sales_store_id": store.id,
        })
        customer = self.env["ab_customer"]
        source_cust_id = self._source_int(scenario, "cust_id")
        if source_cust_id:
            customer = self._create("ab_customer", {
                "code": "ABST%s" % source_cust_id,
                "name": prefix + " Customer",
                "eplus_serial": source_cust_id,
            })

        employee = self._prepare_employee(scenario, prefix)
        products = self._prepare_products(scenario, prefix, uom_category, uom)
        contract = self._prepare_contract(scenario, prefix, store, customer, products)
        promo = self._prepare_promo(scenario, prefix, store, replica_db, products)
        doctor = self._prepare_doctor(scenario, prefix)
        pos_session = self._prepare_pos_session(scenario, prefix, store, employee)

        return {
            "prefix": prefix,
            "store": store,
            "replica_db": replica_db,
            "customer": customer,
            "employee": employee,
            "products": products,
            "contract": contract,
            "promo": promo,
            "doctor": doctor,
            "pos_session": pos_session,
            "uom": uom,
        }

    @contextmanager
    def _replica_fixture_create_guard(self):
        original_create = AbOdooReplicationOnlyAllowed.create

        def fixture_create(recordset, values):
            if (
                    recordset.env.context.get("ab_sales_test_fixture_create")
                    and recordset.env.context.get("replication")
            ):
                return super(AbOdooReplicationOnlyAllowed, recordset).create(values)
            return original_create(recordset, values)

        with patch.object(AbOdooReplicationOnlyAllowed, "create", fixture_create):
            yield

    def _prepare_employee(self, scenario, prefix):
        employee_eplus_id = 900000000 + int(uuid.uuid4().hex[:6], 16)
        costcenter = self._create("ab_costcenter", {
            "name": prefix + " Operator",
            "code": "ABST%s" % employee_eplus_id,
            "eplus_serial": employee_eplus_id,
        })
        return self._create("ab_hr_employee", {
            "name": prefix + " Operator",
            "costcenter_id": costcenter.id,
            "user_id": self.env.uid,
        })

    def _prepare_pos_session(self, scenario, prefix, store, employee):
        if "ab_employee_access_sales_pos_session" not in self.env.registry:
            return self.env["ab_hr_employee"]

        session_inputs = self._pos_session_inputs(scenario)
        device_uid = str(session_inputs.get("device_uid") or "ab_sales_test").strip()
        device_name = str(session_inputs.get("device_name") or "AB Sales Test").strip()
        device_ip = str(session_inputs.get("device_ip") or "127.0.0.1").strip()

        role = self._create("ab_employee_access_sales_role", {
            "name": prefix + " POS Role",
            "allow_pos_screen": True,
            "pin_rotation_days": 90,
        })
        profile = self._create("ab_employee_access", {
            "employee_id": employee.id,
            "pos_role_id": role.id,
            "pos_allow_login": True,
            "pos_allowed_store_ids": [(6, 0, [store.id])],
        })
        shift = self._create("ab_employee_access_sales_shift", {
            "employee_id": employee.id,
            "role_id": role.id,
            "service_user_id": self.env.uid,
            "store_id": store.id,
            "device_uid": device_uid,
            "device_name": device_name,
            "state": "open",
        })
        return self._create("ab_employee_access_sales_pos_session", {
            "session_token": "%s-%s" % (
                str(session_inputs.get("session_token_prefix") or "ab_sales_test"),
                uuid.uuid4().hex,
            ),
            "employee_id": employee.id,
            "profile_id": profile.id,
            "role_id": role.id,
            "shift_id": shift.id,
            "service_user_id": self.env.uid,
            "store_id": store.id,
            "device_uid": device_uid,
            "device_name": device_name,
            "device_ip": device_ip,
            "state": "active",
        })

    def _prepare_products(self, scenario, prefix, uom_category, uom):
        products = {}
        product_origins = self._product_origins_by_serial(scenario)
        for line in scenario["lines"]:
            product_serial = self._line_source_int(line, "itm_id")
            if product_serial in products:
                continue
            card_vals = {
                "name": "%s Product %s" % (prefix, product_serial),
            }
            if product_origins.get(product_serial):
                card_vals["origin"] = product_origins[product_serial]
            card = self._create("ab_product_card", card_vals)
            product = self._create("ab_product", {
                "product_card_id": card.id,
                "code": "ABST%s" % product_serial,
                "default_price": self._line_input_float(line, "itm_sell"),
                "default_cost": self._line_input_float(line, "itm_cost"),
                "uom_category_id": uom_category.id,
                "uom_id": uom.id,
                "allow_sell_fraction": True,
                "eplus_serial": product_serial,
            })
            products[product_serial] = product
        return products

    def _product_origins_by_serial(self, scenario):
        origins = {}
        for line in scenario["lines"]:
            product_serial = self._line_source_int(line, "itm_id")
            product_inputs = self._line_product_inputs(line)
            origin = str(product_inputs.get("origin") or "").strip()
            if origin and product_serial not in origins:
                origins[product_serial] = origin
        return origins

    def _prepare_contract(self, scenario, prefix, store, customer, products):
        contract_inputs = self._contract_inputs(scenario)
        if not contract_inputs:
            return self.env["ab_contract"]
        vals = {
            "name": prefix + " Contract",
            "paid_percentage": SalesTestJSONLoader.to_float(contract_inputs.get("paid_percentage")),
        }
        for json_key, field_name in (
            ("paid_amount", "paid_amount"),
            ("max_bill_value", "max_bill_value"),
        ):
            if not SalesTestJSONLoader.is_blank(contract_inputs.get(json_key)):
                vals[field_name] = SalesTestJSONLoader.to_float(contract_inputs.get(json_key))
        if not SalesTestJSONLoader.is_blank(contract_inputs.get("eplus_serial")):
            vals["eplus_serial"] = SalesTestJSONLoader.to_int(contract_inputs.get("eplus_serial"))
        if not SalesTestJSONLoader.is_blank(contract_inputs.get("discount_percentage_rule")):
            vals["discount_percentage_rule"] = contract_inputs.get("discount_percentage_rule")

        origin_discounts = contract_inputs.get("origin_discounts") or {}
        for json_key, field_name in (
            ("local", "local_product_discount"),
            ("imported", "imported_product_discount"),
            ("special_imported", "special_import_product_discount"),
            ("chemical", "local_made_product_discount"),
            ("other", "other_product_discount"),
        ):
            discount_value = self._contract_origin_discount_value(contract_inputs, json_key)
            if not SalesTestJSONLoader.is_blank(discount_value):
                vals[field_name] = SalesTestJSONLoader.to_float(discount_value)

        if SalesTestJSONLoader.to_bool(contract_inputs.get("allowed_current_store")):
            vals["allowed_store_ids"] = [(6, 0, [store.id])]
        if not SalesTestJSONLoader.is_blank(contract_inputs.get("eplus_cust_id")):
            vals["eplus_cust_id"] = str(contract_inputs.get("eplus_cust_id"))
        if not SalesTestJSONLoader.is_blank(contract_inputs.get("allow_total_invoice_discount")):
            vals["allow_total_invoice_discount"] = SalesTestJSONLoader.to_bool(
                contract_inputs.get("allow_total_invoice_discount")
            )
        if not SalesTestJSONLoader.is_blank(contract_inputs.get("total_invoice_discount_source")):
            vals["total_invoice_discount_source"] = contract_inputs.get("total_invoice_discount_source")

        contract = self._create("ab_contract", vals)
        rules_by_card = {}
        for line in scenario["lines"]:
            line_contract_inputs = self._line_contract_inputs(line)
            if SalesTestJSONLoader.is_blank(line_contract_inputs.get("product_card_discount")):
                continue
            product = products[self._line_source_int(line, "itm_id")]
            card_id = product.product_card_id.id
            if card_id in rules_by_card:
                continue
            rule = self._create("ab_contract_product_origin", {
                "contract_id": contract.id,
                "product_card_id": card_id,
                "discount": SalesTestJSONLoader.to_float(line_contract_inputs.get("product_card_discount")),
            })
            rules_by_card[card_id] = rule
        return contract

    def _prepare_promo(self, scenario, prefix, store, replica_db, products):
        promo_inputs = self._promo_inputs(scenario)
        if not promo_inputs.get("name"):
            return self.env["ab_promo_program"]
        product_scope = []
        discount_scope = []
        for line in scenario["lines"]:
            product = products[self._line_source_int(line, "itm_id")]
            line_promo_inputs = self._line_promo_inputs(line)
            if SalesTestJSONLoader.to_bool(line_promo_inputs.get("in_product_scope")):
                product_scope.append(product.id)
            if SalesTestJSONLoader.to_bool(line_promo_inputs.get("in_discount_scope")):
                discount_scope.append(product.id)

        vals = {
            "name": promo_inputs.get("name") or prefix + " Promo",
        }
        for json_key, field_name in (
            ("apply_disc_on", "apply_disc_on"),
            ("promo_uom_basis", "promo_uom_basis"),
            ("rule_products_domain", "rule_products_domain"),
        ):
            if not SalesTestJSONLoader.is_blank(promo_inputs.get(json_key)):
                vals[field_name] = promo_inputs.get(json_key)
        for json_key, field_name in (
            ("disc_percent", "disc_percent"),
            ("fixed_price", "fixed_price"),
            ("rule_min_amount", "rule_min_amount"),
        ):
            if not SalesTestJSONLoader.is_blank(promo_inputs.get(json_key)):
                vals[field_name] = SalesTestJSONLoader.to_float(promo_inputs.get(json_key))
        for json_key, field_name in (
            ("rule_min_qty", "rule_min_qty"),
            ("max_repetition_per_invoice", "max_repetition_per_invoice"),
        ):
            if not SalesTestJSONLoader.is_blank(promo_inputs.get(json_key)):
                vals[field_name] = SalesTestJSONLoader.to_int(promo_inputs.get(json_key))
        if not SalesTestJSONLoader.is_blank(promo_inputs.get("rule_same_reward_qty")):
            vals["rule_same_reward_qty"] = SalesTestJSONLoader.to_bool(promo_inputs.get("rule_same_reward_qty"))
        if product_scope:
            vals["product_ids"] = [(6, 0, list(set(product_scope)))]
        if discount_scope:
            vals["disc_specific_product_ids"] = [(6, 0, list(set(discount_scope)))]
        if SalesTestJSONLoader.to_bool(promo_inputs.get("store_scope_current")):
            vals["store_ids"] = [(6, 0, [store.id])]
        if SalesTestJSONLoader.to_bool(promo_inputs.get("replica_scope_current")):
            vals["replica_db_ids"] = [(6, 0, [replica_db.id])]
        return self._create("ab_promo_program", vals)

    def _prepare_doctor(self, scenario, prefix):
        doctor_inputs = self._doctor_inputs(scenario)
        if not SalesTestJSONLoader.to_bool(doctor_inputs.get("is_prescription")):
            return self.env["ab_doctor"]
        return self._create("ab_doctor", {
            "name": doctor_inputs.get("name") or prefix + " Doctor",
            "code": doctor_inputs.get("code") or "",
            "specialty": doctor_inputs.get("specialty") or "",
        })

    def _build_payload(self, scenario, fixtures):
        header = {
            "store_id": fixtures["store"].id,
            "pos_client_token": "ab_sales_test_%s_%s" % (scenario["code"], uuid.uuid4().hex),
        }
        scenario_inputs = scenario.get("inputs") or {}
        if not SalesTestJSONLoader.is_blank(scenario_inputs.get("total_invoice_discount")):
            header["total_invoice_discount"] = SalesTestJSONLoader.to_float(
                scenario_inputs.get("total_invoice_discount")
            )
        if fixtures["customer"]:
            header["customer_id"] = fixtures["customer"].id
        if fixtures["employee"]:
            header["employee_id"] = fixtures["employee"].id
        if fixtures["contract"]:
            header["contract_id"] = fixtures["contract"].id
        if fixtures["doctor"]:
            header["is_doctor_prescription"] = True
            header["doctor_id"] = fixtures["doctor"].id

        payload_lines = []
        for line_data in scenario["lines"]:
            product = fixtures["products"][self._line_source_int(line_data, "itm_id")]
            line = {
                "product_id": product.id,
                "qty_str": str(line_data["inputs"].get("qnty") or "0"),
                "sell_price": self._line_input_float(line_data, "itm_sell"),
                "uom_id": fixtures["uom"].id,
                "inventory_json": self._line_inventory_json(line_data, fixtures["store"], product),
            }
            if fixtures["doctor"]:
                line["is_doctor_prescription_product"] = True
            payload_lines.append(line)

        payload = {
            "header": header,
            "lines": payload_lines,
            "on_existing_token": "warn",
        }
        if fixtures["pos_session"]:
            payload["pos_hr_session_token"] = fixtures["pos_session"].session_token
        self._ensure_pos_hr_session_payload(scenario, fixtures, payload)
        if fixtures["promo"]:
            payload["applied_program_id"] = fixtures["promo"].id
        return payload

    def _ensure_pos_hr_session_payload(self, scenario, fixtures, payload):
        PosApi = self.env["ab_sales_pos_api"]
        if not hasattr(PosApi, "_validate_pos_hr_payload"):
            return
        if payload.get("pos_hr_session_token"):
            return
        pos_session = fixtures.get("pos_session")
        if (
                not pos_session
                or getattr(pos_session, "_name", "") != "ab_employee_access_sales_pos_session"
        ):
            pos_session = self._prepare_pos_session(
                scenario,
                fixtures["prefix"],
                fixtures["store"],
                fixtures["employee"],
            )
            fixtures["pos_session"] = pos_session
        if pos_session and getattr(pos_session, "_name", "") == "ab_employee_access_sales_pos_session":
            payload["pos_hr_session_token"] = pos_session.session_token
        if not payload.get("pos_hr_session_token"):
            raise BlockedScenario([
                "Employee POS session fixture could not be created for ab_employee_access_sales."
            ])

    def _line_inventory_json(self, line_data, store, product):
        return {
            "data": [{
                "store_id": store.id,
                "store_eplus_serial": store.eplus_serial,
                "product_id": product.id,
                "product_eplus_serial": product.eplus_serial,
                "qty": self._line_input_float(line_data, "qnty"),
                "qty_in_small_unit": self._line_input_float(line_data, "qnty"),
                "price": self._line_input_float(line_data, "itm_sell"),
                "cost": self._line_input_float(line_data, "itm_cost"),
                "source_id": self._line_source_int(line_data, "c_id"),
                "exp_date": "2099-12-31 00:00:00",
            }]
        }

    def _compare(self, scenario, actual):
        failures = []
        eplus_header = actual.get("eplus_header") or {}
        expected_header = scenario["expected"]
        for field, expected_key in (
            ("total_bill", "expected_total_bill"),
            ("total_bill_after_disc", "expected_total_bill_after_disc"),
            ("total_bill_net", "expected_total_bill_net"),
        ):
            self._compare_float(
                failures,
                field,
                SalesTestJSONLoader.to_float(expected_header.get(expected_key)),
                eplus_header.get(field),
                scenario,
            )

        actual_lines = sorted(actual.get("eplus_lines") or [], key=lambda line: int(line.get("std_id") or 0))
        expected_lines = scenario["lines"]
        if len(actual_lines) != len(expected_lines):
            failures.append(
                self._diag(
                    scenario,
                    "line_count",
                    len(expected_lines),
                    len(actual_lines),
                )
            )
        for line_data, actual_line in zip(expected_lines, actual_lines):
            context = "itm_id=%s c_id=%s" % (
                self._line_source_int(line_data, "itm_id"),
                self._line_source_int(line_data, "c_id"),
            )
            for field, expected_value in (
                ("itm_id", self._line_expected_int(line_data, "expected_itm_id")),
                ("c_id", self._line_expected_int(line_data, "expected_c_id")),
            ):
                actual_value = int(actual_line.get(field) or 0)
                if expected_value != actual_value:
                    failures.append(self._diag(scenario, "%s %s" % (context, field), expected_value, actual_value))

            for field, expected_value in (
                ("qnty", self._line_expected_float(line_data, "expected_qnty")),
                ("itm_sell", self._line_expected_float(line_data, "expected_itm_sell")),
                ("itm_cost", self._line_expected_float(line_data, "expected_itm_cost")),
                ("itm_dis_per", self._line_expected_float(line_data, "expected_itm_dis_per")),
            ):
                self._compare_float(failures, "%s %s" % (context, field), expected_value, actual_line.get(field), scenario)
        return failures

    def _compare_float(self, failures, field, expected, actual, scenario):
        actual_float = SalesTestJSONLoader.to_float(actual)
        if abs(float(expected or 0.0) - actual_float) > self.FLOAT_TOLERANCE:
            failures.append(self._diag(scenario, field, expected, actual_float))

    @staticmethod
    def _diag(scenario, field, expected, actual):
        return (
            "Scenario: %(scenario)s\n"
            "Reference sth_id: %(sth)s\n"
            "Field: %(field)s\n"
            "Expected: %(expected)s\n"
            "Actual: %(actual)s"
        ) % {
            "scenario": scenario["code"],
            "sth": SalesTestJSONLoader.to_int((scenario.get("source") or {}).get("sth_id")),
            "field": field,
            "expected": expected,
            "actual": actual,
        }

    @staticmethod
    def _source_int(scenario, field_name):
        return SalesTestJSONLoader.to_int((scenario.get("source") or {}).get(field_name))

    @staticmethod
    def _line_source_int(line_data, field_name):
        return SalesTestJSONLoader.to_int((line_data.get("source") or {}).get(field_name))

    @staticmethod
    def _line_input_float(line_data, field_name):
        return SalesTestJSONLoader.to_float((line_data.get("inputs") or {}).get(field_name))

    @staticmethod
    def _line_expected_float(line_data, field_name):
        return SalesTestJSONLoader.to_float((line_data.get("expected") or {}).get(field_name))

    @staticmethod
    def _line_expected_int(line_data, field_name):
        return SalesTestJSONLoader.to_int((line_data.get("expected") or {}).get(field_name))

    def _create(self, model_name, vals):
        record = self.env[model_name].sudo().with_context(
            replication=True,
            ab_sales_test_fixture_create=True,
        ).create(vals)
        self.created_records.append(record)
        return record

    def _cleanup_generated_records(self):
        if self.keep_generated_records:
            return
        self._cleanup_pos_session_logs()
        if self.header and self.header.exists():
            try:
                self.header.line_ids.sudo().write({"active": False})
                self.header.sudo().write({"active": False})
            except Exception:
                pass
        if self.header and self.header.store_id:
            try:
                self.env["ab_sales_inventory"].sudo().search([
                    ("store_id", "=", self.header.store_id.id),
                ]).unlink()
            except Exception:
                pass
        for record in reversed(self.created_records):
            try:
                record = record.sudo().exists()
                if not record:
                    continue
                if "active" in record._fields:
                    record.with_context(replication=True).write({"active": False})
                else:
                    record.unlink()
            except Exception:
                continue

    def _cleanup_pos_session_logs(self):
        if "ab_employee_access_sales_operation_log" not in self.env.registry:
            return
        session_ids = []
        for record in self.created_records:
            try:
                if record._name == "ab_employee_access_sales_pos_session" and record.exists():
                    session_ids.extend(record.ids)
            except Exception:
                continue
        if not session_ids:
            return
        try:
            self.env["ab_employee_access_sales_operation_log"].sudo().search([
                ("session_id", "in", session_ids),
            ]).unlink()
        except Exception:
            pass
