import hashlib
import json
import re
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from lxml.etree import XMLSyntaxError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from odoo import _
from odoo.exceptions import UserError
from odoo.tools import file_open


@lru_cache(maxsize=1)
def _november_offers():
    with file_open("ab_ecommerce_storefront/data/november_2026_offers.json", "rb", filter_ext=(".json",)) as source:
        return json.load(source)


def _draft_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return False


def _offer_text(value):
    if re.fullmatch(r"0?\.\d+|1(?:\.0+)?", value):
        return f"{float(value) * 100:g}%"
    return value


def draft_source_evidence(row, sheet, product_problems):
    issues = row["issues"]
    conflicts = sheet.get("conflicting_identities", {})
    products = {}
    for code in row["codes"]:
        problem = dict(product_problems.get(code, {}))
        if "identity" in issues and code in conflicts:
            problem["identities"] = conflicts[code]
        if "terms" in issues:
            values = sheet["code_offers"].get(code, [])
            if any(_benefit(value)[0] != _benefit(row["offer"])[0] for value in values):
                problem["offers"] = values
        if problem:
            products[code] = dict(problem, name=sheet["products"][code][0])
    return {key: row.get(key) for key in ("name", "offer", "description", "start", "end", "issues", "review")} | {
        "products": products,
    }


def _digest(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _text(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() if value is not None else ""


def _label(value):
    return " ".join(value.casefold().split())


def _benefit(value):
    token = value.replace(" ", "").upper()
    if re.fullmatch(r"\d+(?:\.\d+)?%", token):
        token = str(float(token[:-1]) / 100)
    if re.fullmatch(r"(?:0?\.\d+|1(?:\.0+)?)", token) and 0 < float(token) <= 1:
        rate = round(float(token) * 100, 6)
        return _text(float(token)), 1, 1, rate, 0
    bundle = re.fullmatch(r"(\d{1,3})\+(\d{1,3})(%)?", token)
    if bundle:
        buy, benefit = map(int, bundle.group(1, 2))
        percent = bool(bundle.group(3))
        if buy and benefit and (not percent or benefit <= 100):
            free = 1 if percent else benefit
            return token, buy + free, free, benefit if percent else 100, 0
    price = re.fullmatch(r"(\d+(?:\.\d+)?)(?:EGP|ج)", token)
    if price and float(price.group(1)) > 0:
        return token, 1, 1, 100, float(price.group(1))
    return value, 1, 1, 0, 0


def _read_tables(payload):
    catalog = []
    schedules = []
    try:
        with ZipFile(BytesIO(payload)) as archive:
            if sum(part.file_size for part in archive.infolist()) > 32 * 1024 * 1024:
                raise UserError(_("The workbook is too large."))
        with closing(load_workbook(BytesIO(payload), read_only=True, data_only=False, keep_links=False)) as book:
            for sheet in book.worksheets:
                sheet.reset_dimensions()
                rows = sheet.iter_rows(max_col=5, values_only=True)
                header = []
                for number, raw in enumerate(rows, 1):
                    if number > 50000:
                        raise UserError(_("The workbook is too large."))
                    cells = [_text(v) for v in raw]
                    if not any(cells):
                        continue
                    if not header:
                        header = [_label(v) for v in cells]
                        is_schedule = {"company", "offer", "from", "to"}.issubset(header)
                        is_catalog = _label(sheet.title) in {"اكواد العروض", "أكواد العروض", "offer codes"}
                        if is_schedule:
                            continue
                        if not is_catalog:
                            break
                        if header[0] in {"code", "product code", "كود", "كود الصنف"}:
                            continue
                    if is_schedule:
                        record = dict(zip(header, cells))
                        schedules.append((sheet.title.strip(), number, record))
                        if len(schedules) > 1500:
                            raise UserError(_("The workbook is too large."))
                    else:
                        code, name, offer, company = cells[:4]
                        if not all((code, name, offer, company)) or any(v.startswith("=") for v in cells[:4]):
                            raise UserError(_("Check the product code, name, offer and company on row %s of the codes tab.", number))
                        catalog.append((code, name, offer, company))
    except (BadZipFile, KeyError, ValueError, OSError, InvalidFileException, ParseError, XMLSyntaxError, IndexError, OverflowError) as exc:
        raise UserError(_("Choose a readable Excel workbook (.xlsx).")) from exc
    if not catalog or not schedules:
        raise UserError(_("Include an Offer Codes tab and an offer schedule with Company, Offer, From and To columns."))
    return catalog, schedules


def parse_offer_workbook(payload, reference):
    catalog, schedules = _read_tables(payload)
    identities = defaultdict(set)
    memberships = defaultdict(set)
    group_rows = defaultdict(set)
    code_offers = defaultdict(set)
    for code, name, offer, company in catalog:
        identities[code].add((name, company))
        memberships[_label(company), _benefit(offer)[0]].add(code)
        code_offers[code].add(offer)
        group_rows[_label(company)].add((code, name, offer, company))
    same_catalog = _digest(sorted(set(catalog))) == reference["catalog_digest"]
    profiles = reference["catalog_groups"]
    changed_groups = {
        group for group in group_rows.keys() | profiles.keys()
        if group not in profiles or _digest(sorted(group_rows[group])) != profiles[group][0]
    } if not same_catalog else set()
    products = {}
    conflicts = set()
    for code, variants in identities.items():
        name, company = sorted(variants)[0]
        if same_catalog:
            products[code] = reference["products"][code]
        elif len(variants) != 1:
            products[code] = [name, ""]
            conflicts.add(code)
        else:
            known = reference["products"].get(code)
            profile = profiles.get(_label(company))
            brand = company
            if profile:
                brands = profile[1]
                if known and name == known[0] and known[1] in brands:
                    brand = known[1]
                else:
                    brand = brands[0] if len(brands) == 1 else ""
            products[code] = [name, brand]
    reference_rows = {row["key"]: row for row in reference["offers"]}
    offers = {}
    for tab, number, values in schedules:
        name, value, start, end = (values[key] for key in ("company", "offer", "from", "to"))
        description = values.get("description", "")
        condition = _digest([name, value, description, start, end])
        reviewed = reference["reviewed_rows"].get(condition, [])
        source = f"{tab} #{number}"
        if reviewed and all(changed_groups.isdisjoint(reference_rows[k]["source_groups"]) for k in reviewed):
            for key in reviewed:
                if key not in offers:
                    offers[key] = dict(reference_rows[key], source=source)
                    if conflicts.intersection(offers[key]["codes"]):
                        offers[key]["issues"] = sorted(set(offers[key]["issues"]) | {"identity"})
                else:
                    offers[key]["source"] += " / " + source
            continue
        offer, bundle, units, rate, fixed = _benefit(value)
        codes = memberships[_label(name), offer]
        issues = set()
        if not codes:
            issues.add("codes")
        if codes & conflicts:
            issues.add("identity")
        if not rate:
            issues.add("terms")
        try:
            if date.fromisoformat(start) > date.fromisoformat(end):
                issues.add("dates")
        except ValueError:
            issues.add("dates")
        key = "xlsx-" + _digest([_label(name), offer, start, end, description])
        if reviewed:
            for previous_key in reviewed:
                previous = reference_rows[previous_key]
                issues.update(previous["issues"])
                if not previous.get("exact_group") and set(previous["codes"]) != codes:
                    issues.add("scope")
            if len(reviewed) == 1:
                key = reviewed[0]
                bundle, units = previous["bundle"], previous["units"]
        elif description:
            percentages = re.findall(r"(\d+(?:\.\d+)?)\s*[%٪]", description)
            if any(float(percent) != rate for percent in percentages):
                issues.add("terms")
            if re.search(r"ما\s*ع[اأ]?دا|لا يشمل|باستثناء|except|exclud|budget|بادجت", description + " " + name, re.I):
                issues.add("scope")
            if ("مجانا" in description or "مجانًا" in description) and units == bundle:
                issues.add("terms")
        if key in offers:
            offers[key]["source"] += " / " + source
            continue
        offers[key] = dict(key=key, name=name, offer=offer, start=start, end=end, description=description,
                           bundle=bundle, units=units, rate=rate, fixed=fixed, codes=sorted(codes),
                           source=source, issues=sorted(issues), review=True)
    return {"products": products, "offers": list(offers.values()),
            "conflicting_identities": {code: sorted(values) for code, values in identities.items() if len(values) > 1},
            "code_offers": {code: sorted(values) for code, values in code_offers.items()}}
