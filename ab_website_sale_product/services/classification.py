import re
from dataclasses import dataclass
from functools import lru_cache


ENGINE_VERSION = "1"
TAXONOMY = {
    "Medicines": ("Pain & Fever", "Cold & Respiratory", "Allergy", "Digestive", "Diabetes", "Cardiovascular", "CNS / Neurology", "Anti-Infectives", "Eye Care", "Ear / Nose / Throat", "Oral / Throat Medicines", "Dermatology", "Hormones", "Urinary / Renal", "Women's Health", "Men's Health", "Specialized Medicines"),
    "Vitamins & Supplements": ("Vitamins", "Minerals", "Multivitamins", "Omega", "Children's Supplements", "Pregnancy & Lactation", "Hair / Skin / Nails", "Sports Nutrition", "Herbal Supplements"),
    "Skin Care & Beauty": ("Face Cleansing", "Moisturizers", "Sun Care", "Skin Treatment", "Body Care", "Lips & Eye Care", "Makeup", "Nails", "Fragrance"),
    "Hair Care": ("Shampoo", "Conditioner", "Hair Masks", "Hair Oils & Serums", "Hair Styling", "Hair Color", "Hair Loss & Scalp Care", "Hair Tools"),
    "Personal Care": ("Oral Care", "Bath & Shower", "Deodorants", "Feminine Care", "Shaving & Men's Care", "Hair Removal", "Personal Care Devices"),
    "Mother & Baby": ("Diapers & Wipes", "Baby Food & Milk", "Breastfeeding", "Baby Skin & Hair", "Baby Accessories", "Mother Care"),
    "Medical Devices & Supplies": ("Monitoring Devices", "Test Strips", "Supports & Braces", "Mobility", "Patient Care", "Medical Consumables", "Wound Care & First Aid"),
    "Hygiene & Household": ("Tissues & Paper", "Surface Cleaning", "Disinfection", "Air Fresheners", "Pest Control", "Household Supplies"),
}

CATEGORY_ALIASES = {
    "Medicines": ("Medications",), "Skin Care & Beauty": ("Beauty & Skin Care", "Beauty", "Beauty Care", "Skin Care"),
    "Mother & Baby": ("Mom And Baby Care", "Baby Care"), "Medical Devices & Supplies": ("Health Devices & Supplies", "Health Devices", "Medical Supplies"),
    "Hygiene & Household": ("Hygenic And Household Products",),
    "Pain & Fever": ("Pain Relief", "Analgesics"), "Cold & Respiratory": ("Respiratory Care", "Respiratory System"),
    "Allergy": ("Allergy Care",), "Digestive": ("Digestive Health", "Liver And Digestive System"),
    "Cardiovascular": ("Heart & Circulation", "Heart And Blood Vessels"), "CNS / Neurology": ("Brain & Nervous System",),
    "Anti-Infectives": ("Infections",), "Eye Care": ("Eye Care Medicines",), "Ear / Nose / Throat": ("Ear Care",),
    "Oral / Throat Medicines": ("Mouth & Throat",), "Dermatology": ("Skin Medicines",), "Urinary / Renal": ("Kidney & Urinary Care",),
    "Specialized Medicines": ("Specialty Medicines",), "Omega": ("Omega & Eye Supplements",),
    "Children's Supplements": ("Kids Vitamins",), "Pregnancy & Lactation": ("Pregnancy Supplements",),
    "Hair / Skin / Nails": ("Beauty Supplements",), "Herbal Supplements": ("Herbal Products",),
    "Fragrance": ("Perfumes",), "Shaving & Men's Care": ("Men's Grooming", "Men Care"),
    "Diapers & Wipes": ("Baby Diapers & Wipes", "Baby Nappies And Wipes"),
    "Baby Food & Milk": ("Baby Nutrition",), "Breastfeeding": ("Baby Feeding",),
    "Baby Skin & Hair": ("Baby Toiletries",), "Mother Care": ("Mom Care",),
    "Monitoring Devices": ("Diagnostics",), "Supports & Braces": ("Orthopedics & Supports",),
    "Mobility": ("Mobility Aids",), "Wound Care & First Aid": ("Wound Care", "First Aid"),
}


def normalize(text):
    text = re.sub(r"\bl\d+\b", " ", (text or "").casefold()).replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", text)).strip()


@lru_cache(maxsize=4096)
def normalized_term(term):
    return f" {normalize(term)} "


def contains(text, term):
    return normalized_term(term) in f" {text} "


def taxonomy_key(path):
    return "__".join(normalize(part).replace(" ", "_") for part in path)


@dataclass(frozen=True)
class Rule:
    name: str
    path: tuple
    groups: tuple
    priority: int
    exclude: tuple = ()
    strength: float = 0.9

    def match(self, text):
        if any(contains(text, term) for term in self.exclude):
            return ()
        groups = [tuple(term for term in group if contains(text, term)) for group in self.groups]
        return tuple(term for group in groups for term in group) if all(groups) else ()


DRUG_FORMS = ("tablet", "tablets", "tab", "tabs", "capsule", "capsules", "vial", "injection", "ampoule", "suppository", "oral drops", "oral solution", "suspension", "syrup")
MEDICINE_TERMS = ("hydrocortisone", "betamethasone", "clotrimazole", "miconazole", "fusidic acid", "mupirocin", "acyclovir", "diclofenac", "tretinoin", "antibiotic", "corticosteroid")


def rule(name, root, child, terms, priority=60, required=(), exclude=(), strength=0.9):
    return Rule(name, (root, child) if child else (root,), (tuple(terms), *required), priority, tuple(exclude), strength)


RULES = (
    rule("medicine_topical", "Medicines", "Dermatology", MEDICINE_TERMS, 110, required=(("cream", "ointment", "gel", "topical"),)),
    rule("antihistamine", "Medicines", "Allergy", ("levcet", "levocetirizine", "cetirizine", "loratadine", "fexofenadine", "desloratadine"), 105, required=(DRUG_FORMS + ("cap",),)),
    rule("analgesic", "Medicines", "Pain & Fever", ("paracetamol", "ibuprofen", "analgesic", "pain relief", "panadol", "cataflam", "gout"), 100),
    rule("diabetes", "Medicines", "Diabetes", ("metformin", "insulin", "gliclazide", "glimepiride", "sitagliptin"), 100, exclude=("needle", "syringe", "pen needles")),
    rule("anti_infective", "Medicines", "Anti-Infectives", ("amoxicillin", "azithromycin", "antibiotic", "anti biotic", "ceftriaxone", "antiviral", "antifungal"), 100),
    rule("digestive", "Medicines", "Digestive", ("omeprazole", "pantoprazole", "lactulose", "antacid", "loperamide", "hyperacidity", "constipation"), 100),
    rule("respiratory", "Medicines", "Cold & Respiratory", ("salbutamol", "budesonide", "ambroxol", "dextromethorphan", "cough syrup", "asthma"), 100),
    rule("cardiovascular", "Medicines", "Cardiovascular", ("amlodipine", "bisoprolol", "atorvastatin", "rosuvastatin", "clopidogrel", "hypertension"), 100),
    rule("neurology", "Medicines", "CNS / Neurology", ("levetiracetam", "carbamazepine", "sertraline", "epilepsy", "parkinson", "alzheimer"), 100),
    rule("eye_medicine", "Medicines", "Eye Care", ("eye drops", "ophthalmic", "eye ointment"), 100),
    rule("ent_medicine", "Medicines", "Ear / Nose / Throat", ("ear drops", "nasal spray", "nasal drops", "ear wax"), 100),
    rule("throat_medicine", "Medicines", "Oral / Throat Medicines", ("sore throat", "mouth ulcer"), 100, required=(("lozenge", "lozenges", "gel", "spray", "medicine"),)),
    rule("hormones", "Medicines", "Hormones", ("levothyroxine", "thyroid hormone", "growth hormone"), 100),
    rule("urinary", "Medicines", "Urinary / Renal", ("tamsulosin", "kidney disease", "urinary tract infection"), 100),
    rule("women_medicine", "Medicines", "Women's Health", ("contraceptive", "vaginal pessary"), 100),
    rule("men_medicine", "Medicines", "Men's Health", ("sildenafil", "tadalafil", "finasteride"), 100),
    rule("specialized", "Medicines", "Specialized Medicines", ("oncology", "vaccine", "methotrexate", "infusion"), 100),
    rule("baby_skin", "Mother & Baby", "Baby Skin & Hair", ("baby", "infant"), 95, required=(("shampoo", "lotion", "wash", "cream", "oil"),)),
    rule("baby_diapers", "Mother & Baby", "Diapers & Wipes", ("baby diapers", "baby nappies", "baby wipes", "training pants", "molfix"), 95),
    rule("baby_food", "Mother & Baby", "Baby Food & Milk", ("infant milk", "infant formula", "growing up milk", "baby food", "cerelac"), 95),
    rule("breastfeeding", "Mother & Baby", "Breastfeeding", ("breast pump", "nipple shield", "breast feeding", "breastfeeding"), 95),
    rule("baby_accessories", "Mother & Baby", "Baby Accessories", ("pacifier", "teether", "feeding bottle", "baby accessories"), 95),
    rule("mother_care", "Mother & Baby", "Mother Care", ("maternity pads", "maternity belt"), 95),
    rule("test_strips", "Medical Devices & Supplies", "Test Strips", ("test strips", "glucose strips"), 95),
    rule("monitor", "Medical Devices & Supplies", "Monitoring Devices", ("glucometer", "thermometer", "blood pressure monitor", "pulse oximeter"), 95),
    rule("supports", "Medical Devices & Supplies", "Supports & Braces", ("brace", "orthopedic support", "knee support", "wrist support", "cervical collar"), 95),
    rule("mobility", "Medical Devices & Supplies", "Mobility", ("wheelchair", "walking aid", "crutches"), 95),
    rule("patient", "Medical Devices & Supplies", "Patient Care", ("bedpan", "urine bag", "hot cold compress"), 95),
    rule("consumables", "Medical Devices & Supplies", "Medical Consumables", ("syringe", "lancets", "medical gloves", "pen needles"), 95),
    rule("wound", "Medical Devices & Supplies", "Wound Care & First Aid", ("bandage", "gauze", "wound dressing", "first aid"), 95),
    rule("supplement_children", "Vitamins & Supplements", "Children's Supplements", ("children", "kids", "baby"), 90, required=(("vitamin", "multivitamin", "supplement", "gummies"),)),
    rule("supplement_pregnancy", "Vitamins & Supplements", "Pregnancy & Lactation", ("prenatal", "pregnancy supplement", "lactation supplement"), 90),
    rule("supplement_beauty", "Vitamins & Supplements", "Hair / Skin / Nails", ("hair skin nails", "hair and skin and nails", "collagen"), 90, required=(("supplement", "capsule", "tablets", "sachet", "gummies"),)),
    rule("multivitamins", "Vitamins & Supplements", "Multivitamins", ("multivitamin", "multivitamins"), 85),
    rule("omega", "Vitamins & Supplements", "Omega", ("omega 3", "fish oil"), 85),
    rule("sports_nutrition", "Vitamins & Supplements", "Sports Nutrition", ("whey protein", "creatine", "mass gainer"), 85),
    rule("herbal", "Vitamins & Supplements", "Herbal Supplements", ("herbal supplement", "ginkgo supplement"), 85),
    rule("vitamins", "Vitamins & Supplements", "Vitamins", ("vitamin", "vitamins", "cholecalciferol"), 80, required=(DRUG_FORMS + ("supplement", "gummies", "effervescent", "d3"),)),
    rule("minerals", "Vitamins & Supplements", "Minerals", ("calcium", "iron", "zinc", "magnesium"), 80, required=(DRUG_FORMS + ("supplement", "gummies", "effervescent"),)),
    rule("medicine_form", "Medicines", None, ("oral drops", "oral solution", "vial", "injection", "suppository"), 75, exclude=("supplement", "vitamin", "multivitamin", "omega", "iron", "zinc"), strength=0.82),
    rule("hair_masks", "Hair Care", "Hair Masks", ("hair mask", "rescue mask"), 70, required=(("hair", "elvive"),)),
    rule("hair_shampoo", "Hair Care", "Shampoo", ("shampoo",), 65, exclude=("baby", "infant", "carpet")),
    rule("hair_conditioner", "Hair Care", "Conditioner", ("conditioner",), 65, exclude=("fabric", "air", "baby", "infant")),
    rule("hair_oil", "Hair Care", "Hair Oils & Serums", ("hair oil", "hair serum"), 65),
    rule("hair_styling", "Hair Care", "Hair Styling", ("hair spray", "hair gel", "hair wax", "hair styling"), 65),
    rule("hair_color", "Hair Care", "Hair Color", ("hair dye", "hair color", "henna"), 65),
    rule("hair_scalp", "Hair Care", "Hair Loss & Scalp Care", ("hair loss", "scalp care", "anti dandruff", "antidandruff"), 70, exclude=("shampoo",)),
    rule("hair_tools", "Hair Care", "Hair Tools", ("hair brush", "hair dryer", "hair straightener", "comb"), 65),
    rule("face_cleanser", "Skin Care & Beauty", "Face Cleansing", ("face wash", "facial cleanser", "cleanser", "micellar", "toner"), 60, exclude=("baby", "surface", "household", "toilet")),
    rule("moisturizer", "Skin Care & Beauty", "Moisturizers", ("moisturizer", "moisturiser", "moisturizing cream", "moisturising cream"), 60, exclude=MEDICINE_TERMS + ("baby",)),
    rule("sun", "Skin Care & Beauty", "Sun Care", ("sunscreen", "sunblock", "sun protection", "spf", "photoderm"), 65),
    rule("skin_treatment", "Skin Care & Beauty", "Skin Treatment", ("anti wrinkle", "anti aging", "skin serum", "exfoliating", "scar care"), 60, exclude=MEDICINE_TERMS),
    rule("body", "Skin Care & Beauty", "Body Care", ("body care", "body lotion", "body scrub", "hand cream", "foot cream"), 60, exclude=MEDICINE_TERMS + ("baby",)),
    rule("lips_eyes", "Skin Care & Beauty", "Lips & Eye Care", ("lip balm", "eye cream", "lip care"), 60),
    rule("makeup", "Skin Care & Beauty", "Makeup", ("makeup", "make up", "mascara", "lipstick", "concealer"), 60),
    rule("nails", "Skin Care & Beauty", "Nails", ("nail polish", "nail file", "nail clipper"), 60),
    rule("fragrance", "Skin Care & Beauty", "Fragrance", ("perfume", "eau de parfum", "eau de toilette"), 60),
    rule("oral_care", "Personal Care", "Oral Care", ("toothpaste", "toothbrush", "dental floss", "mouthwash", "denture"), 65, exclude=("oral drops", "oral solution")),
    rule("bath", "Personal Care", "Bath & Shower", ("shower gel", "body wash", "hand wash", "soap bar", "bath shower"), 60, exclude=("baby", "infant")),
    rule("deodorant", "Personal Care", "Deodorants", ("deodorant", "deodorants", "antiperspirant", "roll on"), 65),
    rule("feminine", "Personal Care", "Feminine Care", ("sanitary pads", "tampons", "panty liners", "intimate wash"), 65),
    rule("shaving", "Personal Care", "Shaving & Men's Care", ("razor", "shaving", "after shave"), 65),
    rule("hair_removal", "Personal Care", "Hair Removal", ("hair removal", "depilatory", "wax strips"), 70),
    rule("personal_device", "Personal Care", "Personal Care Devices", ("electric shaver", "epilator", "electric toothbrush"), 75),
    rule("tissues", "Hygiene & Household", "Tissues & Paper", ("tissues", "toilet paper", "paper towels"), 65),
    rule("cleaning", "Hygiene & Household", "Surface Cleaning", ("surface cleaner", "floor cleaner", "dishwashing"), 65),
    rule("disinfectant", "Hygiene & Household", "Disinfection", ("surface disinfectant", "hand sanitizer", "disinfectant spray"), 65),
    rule("air", "Hygiene & Household", "Air Fresheners", ("air freshener",), 65),
    rule("pest", "Hygiene & Household", "Pest Control", ("insecticide", "mosquito repellent", "pest control"), 65),
    rule("household", "Hygiene & Household", "Household Supplies", ("batteries", "garbage bags"), 65),
)


def classify_local(facts):
    text = normalize(" ".join(str(facts.get(key) or "") for key in (
        "name", "card_name", "description", "code", "ingredient", "groups", "scientific_groups", "usage", "form", "attributes",
    )))
    matches = [(r, r.match(text)) for r in RULES]
    matches = [(r, terms) for r, terms in matches if terms]
    if not matches:
        return {"method": "needs_review", "reason": "No deterministic rule matched", "confidence": 0, "path": (), "terms": []}
    priority = max(r.priority for r, terms in matches)
    best = [(r, terms) for r, terms in matches if r.priority == priority]
    if len({r.path for r, terms in best}) != 1:
        return {"method": "needs_review", "reason": "Conflicting local rules", "confidence": 0, "path": (), "terms": sorted({term for r, terms in best for term in terms})}
    selected, terms = best[0]
    return {"method": "local_rule", "path": selected.path, "rule": selected.name, "terms": list(terms), "confidence": selected.strength, "reason": "Matched deterministic rule: " + selected.name}
