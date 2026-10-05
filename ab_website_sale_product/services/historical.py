import csv
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from .classification import TAXONOMY


REFERENCE = Path(__file__).resolve().parent.parent / "docs/reference/website_ecommerce/categories"
HISTORICAL_MAPPING = {
    "15": ("Medicines",), "77": ("Medicines", "Allergy"),
    "78": ("Medicines", "Pain & Fever"), "967": ("Medicines", "Pain & Fever"),
    "79": ("Medicines", "CNS / Neurology"), "80": ("Medicines", "Ear / Nose / Throat"),
    "81": ("Medicines", "Eye Care"), "82": ("Medicines", "Cardiovascular"),
    "83": ("Medicines", "Hormones"), "84": ("Medicines", "Anti-Infectives"),
    "85": ("Medicines", "Urinary / Renal"), "86": ("Medicines", "Specialized Medicines"),
    "87": ("Medicines", "Digestive"), "895": ("Medicines", "Diabetes"),
    "88": ("Medicines", "Men's Health"), "89": ("Medicines", "Oral / Throat Medicines"),
    "90": ("Medicines", "Ear / Nose / Throat"), "91": ("Medicines", "Cold & Respiratory"),
    "92": ("Medicines", "Dermatology"), "94": ("Medicines", "Women's Health"),
    "807": ("Medicines", "Specialized Medicines"), "966": ("Medicines", "Specialized Medicines"),
    "968": ("Medicines", "Specialized Medicines"), "969": ("Medicines", "Specialized Medicines"),
    "971": ("Medicines", "Specialized Medicines"), "972": ("Medicines", "Specialized Medicines"),
    "18": ("Vitamins & Supplements",), "106": ("Vitamins & Supplements", "Herbal Supplements"),
    "107": ("Vitamins & Supplements", "Minerals"), "108": ("Vitamins & Supplements", "Multivitamins"),
    "109": ("Vitamins & Supplements",), "110": ("Vitamins & Supplements", "Vitamins"),
    "1302": ("Vitamins & Supplements", "Vitamins"), "927": ("Vitamins & Supplements", "Children's Supplements"),
    "928": ("Vitamins & Supplements", "Children's Supplements"), "933": ("Vitamins & Supplements", "Omega"),
    "934": ("Vitamins & Supplements", "Pregnancy & Lactation"), "935": ("Vitamins & Supplements", "Hair / Skin / Nails"),
    "11": ("Skin Care & Beauty",), "65": ("Skin Care & Beauty",), "66": ("Skin Care & Beauty",),
    "68": ("Skin Care & Beauty",), "961": ("Skin Care & Beauty", "Body Care"),
    "962": ("Skin Care & Beauty", "Lips & Eye Care"), "964": ("Skin Care & Beauty", "Lips & Eye Care"),
    "965": ("Skin Care & Beauty", "Skin Treatment"), "1181": ("Skin Care & Beauty", "Moisturizers"),
    "1182": ("Skin Care & Beauty", "Body Care"), "1183": ("Skin Care & Beauty", "Skin Treatment"),
    "1184": ("Skin Care & Beauty", "Face Cleansing"), "1185": ("Skin Care & Beauty", "Lips & Eye Care"),
    "1186": ("Skin Care & Beauty", "Makeup"), "1187": ("Skin Care & Beauty", "Skin Treatment"),
    "1189": ("Skin Care & Beauty", "Moisturizers"), "1191": ("Skin Care & Beauty", "Sun Care"),
    "1192": ("Skin Care & Beauty", "Sun Care"), "1193": ("Skin Care & Beauty", "Face Cleansing"),
    "1194": ("Skin Care & Beauty", "Skin Treatment"), "828": ("Skin Care & Beauty", "Makeup"),
    "1205": ("Skin Care & Beauty", "Face Cleansing"), "1206": ("Skin Care & Beauty", "Nails"),
    "1207": ("Skin Care & Beauty", "Nails"), "104": ("Skin Care & Beauty", "Fragrance"),
    "67": ("Hair Care",), "855": ("Hair Care", "Hair Color"), "857": ("Hair Care", "Hair Styling"),
    "858": ("Hair Care", "Hair Loss & Scalp Care"), "859": ("Hair Care",),
    "1195": ("Hair Care", "Hair Tools"), "1198": ("Hair Care", "Hair Masks"),
    "1199": ("Hair Care", "Hair Oils & Serums"), "1200": ("Hair Care", "Hair Oils & Serums"),
    "1204": ("Hair Care", "Hair Tools"), "947": ("Hair Care", "Hair Tools"),
    "17": ("Personal Care",), "74": ("Personal Care", "Shaving & Men's Care"),
    "75": ("Personal Care", "Feminine Care"), "100": ("Personal Care", "Bath & Shower"),
    "101": ("Skin Care & Beauty", "Body Care"), "102": ("Personal Care", "Deodorants"),
    "103": ("Personal Care", "Oral Care"), "105": ("Personal Care", "Personal Care Devices"),
    "824": ("Personal Care", "Bath & Shower"), "825": ("Personal Care", "Bath & Shower"),
    "826": ("Personal Care", "Bath & Shower"), "827": ("Personal Care", "Bath & Shower"),
    "974": ("Personal Care", "Hair Removal"), "1306": ("Personal Care", "Deodorants"),
    "16": ("Mother & Baby",), "95": ("Mother & Baby", "Baby Accessories"),
    "96": ("Mother & Baby", "Diapers & Wipes"), "97": ("Mother & Baby", "Baby Food & Milk"),
    "98": ("Mother & Baby", "Baby Skin & Hair"), "99": ("Mother & Baby", "Mother Care"),
    "920": ("Mother & Baby", "Breastfeeding"),
    "14": ("Medical Devices & Supplies",), "70": ("Medical Devices & Supplies", "Patient Care"),
    "72": ("Medical Devices & Supplies", "Mobility"), "869": ("Medical Devices & Supplies", "Supports & Braces"),
    "870": ("Medical Devices & Supplies",), "874": ("Medical Devices & Supplies", "Wound Care & First Aid"),
    "1305": ("Medical Devices & Supplies", "Supports & Braces"),
    "71": ("Hygiene & Household",), "878": ("Hygiene & Household", "Air Fresheners"),
    "879": ("Hygiene & Household", "Disinfection"), "880": ("Hygiene & Household", "Household Supplies"),
    "881": ("Hygiene & Household", "Tissues & Paper"), "882": ("Hygiene & Household", "Pest Control"),
    "1504": ("Vitamins & Supplements", "Minerals"), "1505": ("Medicines", "Pain & Fever"),
    "1506": ("Medicines", "Digestive"), "1507": ("Medicines", "Cold & Respiratory"),
    "1508": ("Medicines", "Cold & Respiratory"), "1510": ("Medicines", "Specialized Medicines"),
    "1511": ("Medicines", "Digestive"), "1547": ("Vitamins & Supplements", "Multivitamins"),
    "1548": ("Vitamins & Supplements", "Vitamins"),
}


def normalize_code(value):
    return str(value or "").strip().casefold()


def build_index(products, categories, relations):
    categories = {row["id"]: row for row in categories}
    by_template = defaultdict(list)
    by_code = defaultdict(set)
    for row in products:
        code = normalize_code(row["template_default_code"])
        if code:
            by_code[code].add(row["template_id"])
    for row in relations:
        by_template[row["product_template_id"]].append(row["product_public_category_id"])
    index = {}
    for code, templates in by_code.items():
        evidence, paths, invalid = [], set(), False
        duplicate = len(templates) > 1
        for template in sorted(templates):
            ids = by_template[template]
            duplicate |= len(ids) != len(set(ids))
            for category_id in ids:
                chain, seen, node = [], set(), category_id
                while node and node in categories and node not in seen:
                    seen.add(node)
                    chain.append(categories[node])
                    node = categories[node]["parent_id"]
                names = [r["name"] for r in reversed(chain)]
                promotional = any(r["id"] in ("1222", "1279") or str(r.get("promo_cat", "")).lower() in ("true", "t", "1") for r in chain)
                path = next((HISTORICAL_MAPPING[r["id"]] for r in chain if r["id"] in HISTORICAL_MAPPING), ())
                if node or promotional:
                    path = ()
                if path:
                    assert path[0] in TAXONOMY and (len(path) == 1 or path[1] in TAXONOMY[path[0]])
                    paths.add(path)
                else:
                    invalid = True
                evidence.append({"template_id": template, "category_id": category_id, "path": names, "mapped_path": path, "promotional": promotional})
        specific = {p for p in paths if not any(len(q) > len(p) and q[:len(p)] == p for q in paths)}
        blocked = duplicate or len(specific) > 1
        path = next(iter(specific)) if len(specific) == 1 and not blocked and not invalid else ()
        index[code] = {
            "method": "historical_mapping" if path else "needs_review", "path": path,
            "confidence": 0.95 if path else 0, "historical": evidence, "blocked": blocked,
            "reason": "Duplicate historical product mapping" if duplicate else "Conflicting historical categories" if blocked else "Historical category mapping" if path else "Historical mapping is missing or unsuitable",
        }
    return index


@lru_cache(maxsize=1)
def historical_index():
    def read(name):
        with (REFERENCE / name).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    return build_index(read("ecommerce_products.csv"), read("ecommerce_categories.csv"), read("ecommerce_product_category_rel.csv"))
