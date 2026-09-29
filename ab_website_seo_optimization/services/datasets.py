import csv
import gzip
import io
import json
import re
import tempfile
import zipfile
from contextlib import contextmanager

from lxml import etree

from .providers import ProviderFailure, digest


@contextmanager
def members(path, filename=None, depth=0):
    name = (filename or str(path)).lower()
    if depth > 2:
        raise ProviderFailure("archive_nesting_limit")
    with open(path, "rb") if isinstance(path, (str, bytes)) or hasattr(path, "__fspath__") else _borrow(path) as raw:
        if name.endswith(".zip"):
            with zipfile.ZipFile(raw) as archive:
                entries = archive.infolist()
                if len(entries) > 200000:
                    raise ProviderFailure("archive_member_limit")
                def iterator():
                    for info in entries:
                        if info.is_dir() or not info.filename.lower().endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".xml", ".rrf", ".sdf", ".zip", ".gz")):
                            continue
                        if info.file_size > 40 * 1024 ** 3 or info.file_size > max(info.compress_size, 1) * 1000:
                            raise ProviderFailure("archive_expansion_limit")
                        with archive.open(info) as member:
                            if info.filename.lower().endswith(".zip"):
                                with tempfile.TemporaryFile() as spool:
                                    for chunk in iter(lambda: member.read(1024 * 1024), b""):
                                        spool.write(chunk)
                                    spool.seek(0)
                                    with members(spool, info.filename, depth + 1) as nested:
                                        yield from nested
                            elif info.filename.lower().endswith(".gz"):
                                with gzip.GzipFile(fileobj=member) as expanded:
                                    yield info.filename[:-3], expanded
                            else:
                                yield info.filename, member
                yield iterator()
        elif name.endswith(".gz"):
            with gzip.GzipFile(fileobj=raw) as expanded:
                yield iter([(name[:-3], expanded)])
        else:
            yield iter([(name, raw)])


@contextmanager
def _borrow(handle):
    yield handle


def records(handle, filename, provider, json_prefix=""):
    name = filename.lower()
    if name.endswith((".csv", ".tsv")):
        yield from csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"), delimiter="\t" if name.endswith(".tsv") else ",")
    elif name.endswith((".jsonl", ".ndjson")):
        for line in handle:
            if line.strip():
                try:
                    yield json.loads(line)
                except (ValueError, UnicodeError):
                    yield None
    elif name.endswith(".json"):
        import ijson
        prefix = json_prefix
        if not prefix:
            if provider in ("openfda", "fda_ndc", "openfda_cosmetic_event"):
                prefix = "results.item"
            elif provider == "usda_fdc":
                prefix = "BrandedFoods.item"
            elif provider == "dsld":
                prefix = ""
            else:
                prefix = "item"
        yield from ijson.items(handle, prefix, use_float=True)
    elif name.endswith(".xml") and provider == "dailymed":
        yield from spl_records(handle)
    elif name.endswith("rxnconso.rrf") and provider == "rxnorm":
        for row in csv.reader(io.TextIOWrapper(handle, encoding="utf-8"), delimiter="|"):
            if len(row) >= 17 and row[1] == "ENG" and row[11] in ("RXNORM", "MTHSPL"):
                values = {"source_id": row[7], "rxcui": row[0], "name": row[14], "_source_active": row[16] == "N", "scientific_context": {"term_type": row[12], "vocabulary": row[11], "code": row[13]}}
                if row[12] in ("IN", "PIN", "MIN"):
                    values["active_ingredients"] = row[14]
                if row[12] == "DF":
                    values["dosage_form"] = row[14]
                yield values
    elif name.endswith("rxnsat.rrf") and provider == "rxnorm":
        for row in csv.reader(io.TextIOWrapper(handle, encoding="utf-8"), delimiter="|"):
            if len(row) >= 12 and row[9] in ("RXNORM", "MTHSPL"):
                values = {"source_id": "attribute:" + digest(row[:11]), "rxcui": row[0], "name": "RxCUI " + row[0],
                          "_source_active": row[11] == "N",
                          "scientific_context": {"attribute": row[8], "value": row[10], "vocabulary": row[9], "atom_id": row[3]}}
                if row[8] == "NDC":
                    values["ndc"] = row[10]
                if row[8] in ("RXN_STRENGTH", "RXN_AVAILABLE_STRENGTH"):
                    values["strength"] = row[10]
                yield values
    elif name.endswith("rxnrel.rrf") and provider == "rxnorm":
        for row in csv.reader(io.TextIOWrapper(handle, encoding="utf-8"), delimiter="|"):
            if len(row) >= 15 and row[10] == "RXNORM" and row[0] and row[4]:
                yield {"source_id": "relation:" + digest(row[:14]), "rxcui": row[4], "name": "RxCUI " + row[4], "_source_active": row[14] == "N",
                       "scientific_context": {"relation": row[7] or row[3], "target_rxcui": row[0], "vocabulary": row[10]}}
    elif name.endswith(".sdf"):
        values, key = {}, None
        for binary in handle:
            line = binary.decode("utf-8", errors="replace").rstrip()
            if line == "$$$$":
                if provider == "pubchem":
                    yield {"CID": values.get("PUBCHEM_COMPOUND_CID"), "Title": values.get("PUBCHEM_IUPAC_NAME"), "InChI": values.get("PUBCHEM_IUPAC_INCHI"), "CanonicalSMILES": values.get("PUBCHEM_OPENEYE_CAN_SMILES"), "properties": values}
                elif provider == "chembl":
                    yield {"molecule_chembl_id": values.get("chembl_id"), "pref_name": values.get("pref_name") or values.get("chembl_id"), "molecule_properties": values}
                else:
                    yield values
                values, key = {}, None
            elif line.startswith(">"):
                found = re.search(r"<([^>]+)>", line)
                key = found.group(1) if found else None
            elif key and line:
                values[key] = (values.get(key, "") + " " + line).strip()
            elif not line:
                key = None
    elif name.endswith(".rrf") and provider == "rxnorm":
        return
    else:
        raise ProviderFailure("unsupported_dataset_format")


def spl_records(handle):
    ns = {"s": "urn:hl7-org:v3"}
    tree = etree.parse(handle, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))
    if tree.docinfo.doctype:
        raise ProviderFailure("xml_doctype_not_allowed")
    root = tree.getroot()
    def value(node, xpath):
        found = node.xpath(xpath, namespaces=ns)
        return str(found[0]) if found else ""
    set_id = value(root, "./s:setId/@root")
    version = value(root, "./s:versionNumber/@value")
    date = value(root, "./s:effectiveTime/@value")
    sections = {}
    code_fields = {"34067-9": "indications", "34071-1": "warnings", "34070-3": "contraindications", "34073-7": "interactions"}
    for section in root.xpath(".//s:section", namespaces=ns):
        field = code_fields.get(value(section, "./s:code/@code"))
        if field:
            sections[field] = " ".join(section.xpath("./s:text//text()", namespaces=ns))
    products = root.xpath(".//s:manufacturedProduct/s:manufacturedProduct | .//s:manufacturedProduct/s:manufacturedMedicine", namespaces=ns)
    for product in products:
        ndc = value(product, "./s:code/@code")
        ingredients = []
        for ingredient in product.xpath("./s:ingredient[starts-with(@classCode, 'ACTI')]", namespaces=ns):
            ingredients.append({"name": value(ingredient, ".//s:ingredientSubstance/s:name/text()"),
                                "strength": "/".join(ingredient.xpath("./s:quantity/*/@value | ./s:quantity/*/@unit", namespaces=ns))})
        yield dict(sections, source_id="%s:%s" % (set_id, ndc), name=value(product, "./s:name/text()"), ndc=ndc,
                   active_ingredients=ingredients, dosage_form=value(product, "./s:formCode/@displayName"),
                   route=root.xpath(".//s:routeCode/@displayName", namespaces=ns),
                   manufacturer=value(root, "./s:author//s:representedOrganization/s:name/text()"),
                   package=product.xpath(".//s:containerPackagedProduct/s:code/@code", namespaces=ns),
                   scientific_context={"spl_set_id": set_id, "version": version, "effective_date": date})
