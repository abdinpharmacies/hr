import json
from collections import OrderedDict

from odoo.tools.misc import file_path
from odoo.tools.translate import _


class SalesTestJSONError(Exception):
    pass


class SalesTestJSONLoader:
    @classmethod
    def json_path(cls):
        try:
            return file_path("ab_sales_test/data/test_cases.json")
        except FileNotFoundError:
            raise SalesTestJSONError(_("Missing ab_sales_test/data/test_cases.json."))

    @classmethod
    def load(cls):
        path = cls.json_path()
        try:
            with open(path, encoding="utf-8") as json_file:
                payload = json.load(json_file, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError as error:
            raise SalesTestJSONError(_("Invalid JSON in test_cases.json: %s") % error) from error

        if not isinstance(payload, dict):
            raise SalesTestJSONError(_("test_cases.json root must be an object."))
        scenarios = payload.get("scenarios")
        if not isinstance(scenarios, list):
            raise SalesTestJSONError(_("test_cases.json must contain a scenarios list."))

        grouped = OrderedDict()
        for index, scenario in enumerate(scenarios, start=1):
            cls._validate_scenario_shape(scenario, index)
            code = str(scenario.get("code") or "").strip()
            if code in grouped:
                raise SalesTestJSONError(_("Duplicate scenario code in JSON: %s") % code)
            normalized = cls._normalize_scenario(scenario)
            grouped[code] = normalized
        return grouped

    @classmethod
    def get_scenario(cls, code):
        return cls.load().get(code)

    @classmethod
    def sync_cases(cls, env):
        grouped = cls.load()
        Case = env["ab_sales_test.case"].sudo()
        synced = Case.browse()
        for code, scenario in grouped.items():
            source = scenario["source"]
            expected = scenario["expected"]
            vals = {
                "scenario_code": code,
                "scenario_name": scenario.get("name") or code,
                "workflow_type": scenario.get("workflow_type") or "other",
                "source_sth_id": cls.to_int(source.get("sth_id")),
                "source_sto_id": cls.to_int(source.get("sto_id")),
                "source_cust_id": cls.to_int(source.get("cust_id")),
                "expected_total_bill": cls.to_float(expected.get("expected_total_bill")),
                "expected_total_bill_after_disc": cls.to_float(expected.get("expected_total_bill_after_disc")),
                "expected_total_bill_net": cls.to_float(expected.get("expected_total_bill_net")),
                "json_line_count": len(scenario["lines"]),
                "configuration_state": "not_validated",
            }
            case = Case.search([("scenario_code", "=", code)], limit=1)
            if case:
                case.write(vals)
            else:
                vals["enabled"] = cls.to_bool(scenario.get("enabled"), default=True)
                case = Case.create(vals)
            synced |= case
        return synced

    @classmethod
    def _validate_scenario_shape(cls, scenario, index):
        if not isinstance(scenario, dict):
            raise SalesTestJSONError(_("JSON scenario %s must be an object.") % index)
        code = str(scenario.get("code") or "").strip()
        if not code:
            raise SalesTestJSONError(_("JSON scenario %s has no code.") % index)
        for object_key in ("source", "inputs", "expected"):
            if object_key not in scenario:
                raise SalesTestJSONError(_("JSON scenario %s is missing %s.") % (code, object_key))
            if not isinstance(scenario.get(object_key), dict):
                raise SalesTestJSONError(_("JSON scenario %s %s must be an object.") % (code, object_key))
        lines = scenario.get("lines")
        if not isinstance(lines, list):
            raise SalesTestJSONError(_("JSON scenario %s must contain a lines list.") % code)

        source = scenario["source"]
        for key in ("sth_id", "sto_id", "cust_id"):
            if key not in source:
                raise SalesTestJSONError(_("JSON scenario %s source is missing %s.") % (code, key))

        expected = scenario["expected"]
        for key in ("expected_total_bill", "expected_total_bill_after_disc", "expected_total_bill_net"):
            if key not in expected:
                raise SalesTestJSONError(_("JSON scenario %s expected is missing %s.") % (code, key))

        for line_index, line in enumerate(lines, start=1):
            cls._validate_line_shape(code, line, line_index)

    @classmethod
    def _validate_line_shape(cls, code, line, line_index):
        if not isinstance(line, dict):
            raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s must be an object.") % {
                "code": code,
                "line": line_index,
            })
        for object_key in ("source", "inputs", "expected"):
            if object_key not in line:
                raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s is missing %(key)s.") % {
                    "code": code,
                    "line": line_index,
                    "key": object_key,
                })
            if not isinstance(line.get(object_key), dict):
                raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s %(key)s must be an object.") % {
                    "code": code,
                    "line": line_index,
                    "key": object_key,
                })

        for key in ("itm_id", "c_id"):
            if key not in line["source"]:
                raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s source is missing %(key)s.") % {
                    "code": code,
                    "line": line_index,
                    "key": key,
                })
        for key in ("qnty", "itm_sell", "itm_cost"):
            if key not in line["inputs"]:
                raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s inputs is missing %(key)s.") % {
                    "code": code,
                    "line": line_index,
                    "key": key,
                })
        for key in (
            "expected_itm_id",
            "expected_c_id",
            "expected_qnty",
            "expected_itm_sell",
            "expected_itm_cost",
            "expected_itm_dis_per",
        ):
            if key not in line["expected"]:
                raise SalesTestJSONError(_("JSON scenario %(code)s line %(line)s expected is missing %(key)s.") % {
                    "code": code,
                    "line": line_index,
                    "key": key,
                })

    @classmethod
    def _normalize_scenario(cls, scenario):
        normalized = dict(scenario)
        normalized["code"] = str(normalized.get("code") or "").strip()
        normalized["name"] = str(normalized.get("name") or normalized["code"]).strip()
        normalized["workflow_type"] = str(normalized.get("workflow_type") or "other").strip().lower() or "other"
        normalized["source"] = dict(normalized.get("source") or {})
        normalized["inputs"] = dict(normalized.get("inputs") or {})
        normalized["expected"] = dict(normalized.get("expected") or {})
        normalized["lines"] = sorted(
            [cls._normalize_line(line, index) for index, line in enumerate(normalized.get("lines") or [], start=1)],
            key=lambda line: cls.to_int(line.get("sequence")),
        )
        return normalized

    @classmethod
    def _normalize_line(cls, line, index):
        normalized = dict(line)
        normalized["sequence"] = cls.to_int(normalized.get("sequence"), default=index)
        normalized["source"] = dict(normalized.get("source") or {})
        normalized["inputs"] = dict(normalized.get("inputs") or {})
        normalized["expected"] = dict(normalized.get("expected") or {})
        return normalized

    @staticmethod
    def to_bool(value, default=False):
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if not text:
            return default
        return text in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def to_int(value, default=0):
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def to_float(value, default=0.0):
        try:
            if value in (None, ""):
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def is_blank(value):
        return value is None or str(value).strip() == ""
