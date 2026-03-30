# -*- coding: utf-8 -*-
import logging
import re
import calendar
from datetime import datetime, date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import pyodbc
except ImportError:
    pyodbc = None


action_mapping = {
    "Accepted-Job Offer": "accepted_job_offer",
    "Accepted-Short List": "accepted_short_list",
    "Accepted-Waiting List": "accepted_waiting_list",
    "Training": "training",
    "S.List": "s_list",
    "Rejected": "rejected",
    "Archived": "archived",
    "Advanced Training": "advanced_training",
    "Duplicated Training": "duplicated_training",
    "Re-Appraisal Interview": "re_appraisal_interview",
}


INTERVIEWER_AR_MAP = {
    "Dr.Sherif Mamdouh": "شريف ممدوح كامل محمود",
    "Dr.Mina Kameil": "مينا كميل عزمى غبرس",
    "Mr.Ahmed Esmail": "احمد اسماعيل إبراهيم محمد",
    "Mr.Ashraf Kallaf": "اشرف خلف محمود حسين",
    "Mr.Marina Atef": "مارينا عاطف أنور بولس",
    "Dr.Hazem Abdin": "حازم عابدين محمود",
    "Dr.Hiatham Ahmed": "سعد أحمد محمد علي",
    "Dr.Mohamed salah": "محمد صلاح حسن ابراهيم",
    "DR.Engy Refat": "انجي رفعت بطرس لمعي",
    "Mr.Mohamed Omer": "محمد عمر عبد الحفيظ محمد",
    "Dr.Ahmad ezzat": "أحمد عزت فهمى السيد",
    "Ms.Hoda": "هدى سيد شوقي سليمان",
    "Mr.Eslam": "إسلام محمد محمد عبد الفتاح",
    "Dr.mayar mustafa": "ميار مصطفى مصطفى علي منسي",
    "Mr.Ahmed Assem": "أحمد عاصم أحمد برغش",
    "Mr.Esmail Atallah": "إسماعيل عطا الله اسماعيل حماد",
    "Mr.Amr EZZ": "عمرو محمود على محمد عز",
    "Dr.Saed Ramadan": "سعيد رمضان عزيز صالح",
    "Dr.Tamer Amin": "تامر امين عبدالماجد ابراهيم",
    "Mr.mohamed elsibay": "محمد أحمد أحمد السباعي",
    "Mr.Kareem Shindy": "كريم جمال شندى حمد حماد",
    "Dr.Hager Ali": "هاجر علي محمد حسين",
    "Mr.Mohamed Ayman": "محمد أيمن فوزى صبحى",
    "Mr.Mohamed abdelwahed": "محمد احمد طه عبدالواحد",
    "Mr.Mahmoud Ramadan": "محمود رمضان عبد العزيز خالد",
    "Dr.Mohamed Saad": "محمد سعد مجدى محمود",
    "Mr.Ahmed Asam": "أحمد عاصم أحمد برغش",
    "mrs mai mahmoud": "مي محمود علي احمد",
    "mr.mahmoug kalf": "محمود خلف محمد عبد الله",
    "ms. toqa hagag": "تقى حجاج محمد حجاج عامر",
    "Mr. Muhmoud Elbadry": "محمود البدري عبد الباسط علي",
    "Dr. Mohamed Abd-Elhakeem": "محمد عبدالحكيم محمد محمد",
    "Dr.Mohamed Abd-Elhakeem": "محمد عبدالحكيم محمد محمد",
    "Mr.Mostafa Maeruf": "مصطفى عبد المنعم عمر سيد معروف",
    "MR.Hany abdelshafy": "هانى أحمد عبد الشافى محمد",
    "Mrs. Hager Mohamed": "هاجر محمد عباس علي",
    "Miss. Aghaby Fathy": "اغابي فتحي باخوم شنوده",
    "Dr.Abd-Elrahman shaban": "عبدالرحمن شعبان خليفه عبدالحكيم",
    "mr.hany abd-elshafy": "هانى أحمد عبد الشافى محمد",
    "Miss Sadeen Salah": "سادين صلاح السيد محمد",
    "Miss Amira Mohamed": "اميره محمد محمد وحشي",
    "Dr.Abdul Rahman Akram": "عبدالرحمن اكرم محمد خليل",
    "miss.mona": "منى عبد الرحمن أحمد محمد",
    "Dr. Omnia Naser": "امنيه ناصر محمد عبدالرحمن",
    "miss yara ahmed": "يارا احمد عبدالعظيم عبدالوهاب",
    "Ms.Yara Ahmed": "يارا احمد عبدالعظيم عبدالوهاب",
    "Ms. Dalia Othman": "داليا عثمان عبدالرحمن محمد",
    "DR. Ebrahim EL-najar": "ابراهيم محمد ابراهيم احمد",
    "Mr. Ahmed Zenham": "أحمد زينهم عبد العزيز عبد العظيم",
    "Engineer Imad Abdeen": "عماد الدين عابدين محمود أحمد",
    "Dr. Rasha Maher": "رشا ماهر محمد بطيخ",
    "DR. Armia Nassar Fouad": "ارميا نصار فؤاد ملك",
    "DR. Armia Nassar": "ارميا نصار فؤاد ملك",
}


DEFAULT_DATE = date(1900, 1, 1)


JOB_MANUAL_MAP = {
    "أمين مخزن": "امين مخزن",
    "امين مخزن": "امين مخزن",
    "سائق": "سائق",
    "سكرتارية": "سكرتارية",
    "صيدلي": "صيدلي",
    "صيدلي تجميل": "صيدلي تجميل",
    "طالب صيدلي": "طالب صيدلي",
    "عامل خدمات": "عامل خدمات",
    "قائم بأعمال مدير فرع": "قائم باعمال مدير فرع",
    "قائم باعمال مدير فرع": "قائم باعمال مدير فرع",
    "كاشير": "كاشير",
    "محاسب": "محاسب",
    "محاسب منطقة": "محاسب منطقة",
    "محامي": "محامي",
    "محضر": "محضر",
    "مدخل بيانات": "مدخل بيانات",
    "مدرب ميداني": "مدرب ميداني",
    "مدير الرقابة على المخزون": "مدير الرقابة على المخزون",
    "مدير المخزون": "مدير مخزون",
    "مدير مخزون": "مدير مخزون",
    "مدير مخزن": "مدير مخزن",
    "مدير المخزن": "مدير مخزن",
    "مدير إدارة التعاقدات": "مدير ادارة التعاقدات",
    "مدير إدارة التوسعات": "مدير ادارة التوسعات",
    "مدير تكنولوجيا المعلومات": "مدير ادارة النظم والمعلومات",
    "مدير قسم إدخال البيانات": "مدير قسم ادخال البيانات",
    "مدير لجنة الجرد": "مدير لجنة الجرد",
    "مدير مشتريات التجميل": "مدير مشتريات التجميل",
    "مدير مشتريات الدواء": "مدير مشتريات الدواء",
    "مسئول علاقات عامة": "اخصائي علاقات عامة",
    "مدير منطقة": "مدير منطقة",
    "مدير موارد بشرية": "مدير ادارة الموارد بشرية",
    "مدير إدارة الموارد بشرية": "مدير ادارة الموارد بشرية",
    "مدير وردية": "مدير وردية",
    "مراجع": "مراجع مخزن",
    "مساعد صيدلي": "مساعد صيدلي",
    "مساعد مدير البيع": "مساعد مدير البيع",
    "مساعد مدير التشغيل": "مساعد مدير التشغيل",
    "مساعد مدير المخزون": "مساعد مدير المخزون",
    "مسئول تجميل": "مسئول تجميل",
    "مسئول تعاقدات": "اخصائى تعاقدات",
    "مسئول تكنولوجيا المعلومات": "اخصائى نظم و معلومات",
    "مسئول خدمة عملاء": "اخصائي خدمة عملاء",
    "مسئول رقابة ومتابعة": "اخصائي رقابة ومتابعة",
    "مسئول شحن": "اخصائي شحن",
    "مسئول شحن وحسابات": "اخصائي شحن وحسابات",
    "مسئول شئون عاملين": "اخصائي شئون عاملين",
    "مسئول صيانة": "اخصائي صيانة",
    "اخصائي صيانة": "اخصائي صيانة",
    "مسئول لجنة جرد": "اخصائي لجنة جرد",
    "مسئول مشتريات": "اخصائي مشتريات ادوية",
    "مسئول موارد بشرية": "اخصائي موارد بشرية",
    "اخصائي موارد بشرية": "اخصائي موارد بشرية",
    "مشرف تجميل منطقة": "مشرف تجميل",
    "مندوب توصيل": "مندوب توصيل",
    "منسق تسويق رقمي": "منسق تسويق رقمي",
    "منسق موارد بشرية": "منسق موارد بشرية",
    "موظف أمن": "موظف امن",
    "نائب مدير فرع": "نائب مدير فرع",
    "مدير فرع": "مدير فرع",
    "مصمم جرافيك": "مصمم جرافيك",
    "اخصائي كول سنتر": "اخصائي كول سنتر",
    "كول سنتر": "اخصائي كول سنتر",
    "مبرمج": "مطور برنامج",
    "مطور أودو": "مطور أودو",
    "أخرى": "مراجع عام",
    "اخري": "مراجع عام",
    "اخرى": "مراجع عام",
    "اخصائي رقابة وجودة": "اخصائي رقابة وجودة",
    "تسجيل مدير": "تسجيل مدير",
    "تسجيل صاحب": "تسجيل صاحب",
    "مسئول متابعة": "اخصائي رقابة ومتابعة",
    "مسئول نظم ومعلومات": "اخصائي نظم ومعلومات",
    "مدير إدارة النظم والمعلومات": "مدير ادارة النظم والمعلومات",
    "مسنق تسويق رقمي": "اخصائي تسويق رقمي",
    "مسئول توظيف": "اخصائي توظيف",
    "مدير مشروع": "مدير مشروع",
    "اخصائي مشتريات تجميل": "اخصائي مشتريات تجميل",
    "اخصائي توظيف": "اخصائي توظيف",
    "محضر تجميل": "محضر",
    "مراجع تعاقدات": "مراجع تعاقدات",
    "مدير الحسابات": "مدير حسابات الخزائن والعملاء والموردين",
    "أخصائي مشتريات أدوية": "اخصائي مشتريات ادوية",
    "اخصائي مشتريات ادوية": "اخصائي مشتريات ادوية",
    "محاسب ضرائب": "مدير قسم الضرائب",
    "مدير قسم التوظيف والتطوير المؤسسي": "مدير قسم التوظيف",
    "اخصائي تسويق رقمي": "اخصائي تسويق رقمي",
    "اخصائي خدمة عملاء": "اخصائي خدمة عملاء",
    "قائم بأعمال مدير إدارة التسويق": "قائم بأعمال مدير إدارة التسويق",
    "محرر محتوى رقمي": "محرر محتوى رقمي",
    "منسق ايفنتات": "منسق إيفنتات",
    "أخصائي صيانة": "اخصائي صيانة",
    "مدرب": "مدرب",
    "مدير قسم حسابات الخزائن": "مدير قسم حسابات الخزائن",
    "أخصائي توظيف وتطوير مؤسسي": "أخصائي توظيف وتطوير مؤسسي",
    "اخصائي عروض": "أخصائي عروض",
    "اخصائي تسويق": "اخصائي تسويق رقمي",
    "اخصائي شئون عاملين": "اخصائي شئون عاملين",
    "مدير إدارة التسويق": "مدير إدارة التسويق",
    "Online Marketing Manager": "مدير قسم التسويق الرقمي",
    "محاسب خزنة": "محاسب خزينة",
    "محاسب بنوك": "محاسب",
    "محاسب موردين": "محاسب موردين",
    "مدير إدارة الكول سنتر": "مدير الكول سنتر",
    "اخصائي مرتبات": "اخصائي مرتبات",
    "اخصائي تدريب": "منسق تدريب",
    "مدير الادارة الهندسية": "مدير الادارة الهندسية",
    "فني صيانة": "اخصائي صيانة",
    "اخصائي تجارية": "اخصائي تجارية",
    "Content Creator": "محرر محتوى رقمي",
    "مدير قطاع البيع": "مدير البيع",
    "أخصائي تسويق وحملات تسويقية": "اخصائي تسويق",
    "مدير وحدة الاستلامات والمراجعة وإدخال البيانات": "مدير وحدة الاستلامات والمراجعة وإدخال البيانات",
    "اخصائي نظم ومعلومات it": "اخصائي نظم ومعلومات",
    "اخصائي نظم ومعلومات": "اخصائي نظم ومعلومات",
    "محاسب الاصوال الثابتة": "محاسب اصول ثابتة",
    "اخصائى شئون قانونية": "اخصائي شئون قانونية",
    "مدير التسويق غير الرقمي": "مدير التسويق غير الرقمي",
    "اخصائي شحن": "اخصائي شحن",
    "اخصائي تجميل": "اخصائي تجميل",
    "مدير إدارة التدريب": "مدير إدارة التدريب",
    "مساعد مدير مشتريات التجميل": "مساعد مدير مشتريات التجميل",
    "مشرف كول سنتر": "مشرف كول سنتر",
    "أخصائي إعلانات مرئية ومطبوعات دعائية": "أخصائي إعلانات مرئية ومطبوعات دعائية",
    "مدير بيع وتشغيل اقليم": "مدير بيع وتشغيل اقليم",
    "بديل راحات": "بديل راحات",
    "اخصائي لجنة جرد": "اخصائي لجنة جرد",
    "مراقب امن": "مراقب امن",
    "اخصائي كنترول": "اخصائي كنترول",
    "CRM & Customer Support Officer": "اخصائي خدمة عملاء",
    "مراجع كنترول": "مراجع كنترول",
}


PRESENT_WORDS = {
    "present", "now", "till now", "up till now", "current",
    "حتى الآن", "حتى الان", "حتي الان", "الى الان", "إلى الآن",
    "حاليا", "الان", "مازال", "مازال مستمر", "ما زال مستمر", "مستمر",
    "still", "tillnow", "until now", "till now", "to date", "حتى تاريخه",
}

AR_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "إبريل": 4, "أبريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7,
    "اغسطس": 8, "أغسطس": 8,
    "سبتمبر": 9, "سبتمر": 9, "سبتمير": 9, "سبتنبر": 9, "سبتمرر": 9,
    "اكتوبر": 10, "أكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}

EN_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8, "augst": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_AR_NUM_WORDS = {
    "صفر": 0,
    "واحد": 1, "واحدة": 1,
    "اتنين": 2, "اثنين": 2, "إثنين": 2, "اثنان": 2,
    "ثلاثة": 3, "ثلاث": 3,
    "اربعة": 4, "أربعة": 4, "اربع": 4, "أربع": 4,
    "خمسة": 5, "خمس": 5,
    "ستة": 6, "ست": 6,
    "سبعة": 7, "سبع": 7,
    "ثمانية": 8, "ثمان": 8, "تمنية": 8,
    "تسعة": 9, "تسع": 9,
    "عشرة": 10, "عشر": 10,
    "احد عشر": 11, "إحدى عشر": 11,
    "اثنا عشر": 12, "إثنا عشر": 12,
    "نصف": 0.5,
    "ربع": 0.25,
    "ثلاثة ارباع": 0.75, "ثلاثة أرباع": 0.75,
}

MILITARY_MAP = {
    "أدى": "perform",
    "غير مطلوب": "unrequired",
    "لم يؤد": "did_not_perform",
    "مؤجل": "delayed",
    "معافى": "exempt",
}

RELIGION_MAP = {
    "مسلم/ة": "muslim",
    "مسيحي/ة": "christian",
    "يهودي/ة": "jewish",
    "undefined": "undefined",
    None: False,
    "": False,
}

GENDER_MAP = {
    "ذكر": "male",
    "انثي": "female",
    "أنثى": "female",
}

MARITAL_MAP = {
    "أرمل/ة": "widower",
    "أعزب/عزباء": "single",
    "متزوج/ة": "married",
    "مطلق/ة": "divorced",
}

FORMTYPE_MAP = {
    "تدريب": "training",
    "توظيف": "recruit",
}


def _norm(s):
    if not s:
        return ""
    s = str(s).strip()
    s = s.replace("\u00a0", " ")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي")
    s = " ".join(s.split())
    return s


GOV_TRANSLATE = {
    "القاهرة": "Cairo",
    "الجيزة": "Giza",
    "الإسكندرية": "Alexandria",
    "الإسماعيلية": "Ismailia",
    "السويس": "Suez",
    "الدقهلية": "Dakahlia",
    "الشرقية": "Al Sharqia",
    "الغربية": "Gharbia",
    "القليوبية": "Qalyubia",
    "المنوفية": "Monufia",
    "البحيرة": "Beheira",
    "كفر الشيخ": "Kafr el-Sheikh",
    "دمياط": "Damietta",
    "بورسعيد": "Port Said",
    "بني سويف": "Beni Suef",
    "الفيوم": "Faiyum",
    "المنيا": "Minya",
    "أسيوط": "Asyut",
    "سوهاج": "Sohag",
    "قنا": "Qena",
    "الأقصر": "Luxor",
    "أسوان": "Aswan",
    "البحر الأحمر": "Red Sea",
    "الوادي الجديد": "New Valley",
    "مطروح": "Matrouh",
    "شمال سيناء": "North Sinai",
    "جنوب سيناء": "South Sinai",
    "حلوان": "Cairo",
    "السادس من اكتوبر": "Giza",
    "العاصمة الإدارية": "Cairo",
}


def _clean_date_text(v):
    if v is None or v is False:
        return ""
    s = str(v).strip()
    s = s.replace("\u00a0", " ")
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = s.replace("\\", "/")
    s = s.replace("ـ", "-")
    s = re.sub(r"\s+", " ", s).strip()
    # remove spaces around separators
    s = re.sub(r"\s*([/\-\.])\s*", r"\1", s)
    return s


def _safe_make_date(y, m, d=None, end_like=False):
    if not (1900 <= int(y) <= 2100 and 1 <= int(m) <= 12):
        return None
    y = int(y)
    m = int(m)
    last = calendar.monthrange(y, m)[1]
    if d is None:
        d = last if end_like else 1
    d = max(1, min(int(d), last))
    return date(y, m, d)


def _add_months(d, months):
    whole = int(months)
    frac = months - whole
    y = d.year + (d.month - 1 + whole) // 12
    m = (d.month - 1 + whole) % 12 + 1
    base = _safe_make_date(y, m, d.day, end_like=False) or _safe_make_date(y, m, 1, end_like=False)
    if abs(frac) > 1e-9:
        base = base + timedelta(days=int(round(frac * 30)))
    return base


def _extract_float_number(s):
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b:
            return a / b
    return None


def _parse_duration_to_delta(s):
    """
    Returns (months_float, days_int) or None.
    Handles: سنة ونصف, 3 شهور, اسبوعين, 15 يوم, 12 (assume months), خمس سنوات...
    """
    if not s:
        return None
    s0 = s
    s = s.lower().strip()
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = re.sub(r"\s+", " ", s)

    # ignore obvious non-duration phrases
    if any(x in s for x in ["فتره", "فترة", "تدريب", "اجازه", "اجازة", "8 صباح", "8 مساء", "&", "and"]):
        return None

    # normalize common typos
    s = s.replace("ىشهور", "شهور").replace("اشهر", "شهور").replace("سنه", "سنة")

    # Try numeric
    num = _extract_float_number(s)

    # Try arabic word numbers (longest first)
    if num is None:
        keys = sorted(_AR_NUM_WORDS.keys(), key=len, reverse=True)
        for w in keys:
            if re.search(rf"\b{re.escape(w)}\b", s):
                num = float(_AR_NUM_WORDS[w])
                break

    # standalone unit (e.g. "شهر", "سنة")
    if num is None:
        if re.search(r"\b(شهر|شهور)\b", s):
            num = 1.0
        elif re.search(r"\b(سنة|سنوات|عام|اعوام|أعوام|سنين)\b", s):
            num = 1.0
        elif re.search(r"\b(اسبوع|أسبوع|اسابيع|أسابيع)\b", s):
            num = 1.0
        elif re.search(r"\b(يوم|ايام|أيام)\b", s):
            num = 1.0

    # "سنة ونصف" / "2 ونص" cases
    if ("ونصف" in s or "و نصف" in s) and num is not None:
        # ensure +0.5
        num = float(num) + 0.5

    # bare number only -> assume months if reasonable
    if re.fullmatch(r"\d+(\.\d+)?", s.strip()):
        n = float(s.strip())
        if 1 <= n <= 24:
            return (n, 0)
        return None

    if num is None:
        return None

    # dual / plural like "اسبوعين" "شهرين" "سنتين"
    if "ين" in s and num == 1.0:
        if any(u in s for u in ["اسبوعين", "أسبوعين"]):
            num = 2.0
        elif "شهرين" in s:
            num = 2.0
        elif "سنتين" in s:
            num = 2.0

    if re.search(r"\b(سنة|سنوات|عام|اعوام|أعوام|سنين)\b", s):
        return (num * 12.0, 0)
    if re.search(r"\b(شهر|شهور)\b", s):
        return (num, 0)
    if re.search(r"\b(اسبوع|أسبوع|اسابيع|أسابيع)\b", s):
        return (0.0, int(round(num * 7)))
    if re.search(r"\b(يوم|ايام|أيام)\b", s):
        return (0.0, int(round(num)))

    return None


def _parse_first_real_date_inside(s, ref_date=None, end_like=False):
    # full d/m/y or d-m-y
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", s)
    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        yy = int(m.group(3))
        y = (2000 + yy) if yy < 100 else yy
        return _safe_make_date(y, mo, d, end_like=end_like)

    # any a/b without year
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", s)
    if m:
        a = int(m.group(1))
        b = int(m.group(2))

        # Case A: month/year like 7/18 => 07-2018
        # rule: treat as month/year ONLY if second part > 12 (so 1/07 won't become 2007)
        if 1 <= a <= 12 and b > 12:
            y = 2000 + b  # 18 => 2018
            return _safe_make_date(y, a, None, end_like=end_like)

        # Case B: day/month like 1/7 => 01-07-(ref_year)
        if ref_date:
            y = ref_date.year
            d, mo = a, b

            # heuristic: if first <=12 and second >12 -> month/day (rare) otherwise day/month
            if a <= 12 and b > 12:
                mo, d = a, b

            return _safe_make_date(y, mo, d, end_like=end_like)

    return None


def _parse_monthname_year(s, ref_date=None, end_like=False):
    # Arabic month name with year (optional day)
    m = re.search(r"(?:(\d{1,2})\s*)?([اأإآء-ي]+)\s*(\d{4})", s)
    if m:
        d = m.group(1)
        mon_name = m.group(2).strip()
        y = int(m.group(3))
        mon_name_n = mon_name.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        mon = AR_MONTHS.get(mon_name) or AR_MONTHS.get(mon_name_n)
        if mon:
            return _safe_make_date(y, mon, int(d) if d else None, end_like=end_like)

    # English: Jul-20
    s2 = s.lower().strip()
    m2 = re.search(r"\b([a-z]{3,9})[-/](\d{2,4})\b", s2)
    if m2:
        mon = EN_MONTHS.get(m2.group(1))
        yy = int(m2.group(2))
        if mon:
            y = (2000 + yy) if yy < 100 else yy
            return _safe_make_date(y, mon, None, end_like=end_like)

    # English: march2019, september 2018
    m3 = re.search(r"\b([a-z]{3,9})\s*(\d{4})\b", s2)
    if m3:
        mon = EN_MONTHS.get(m3.group(1))
        y = int(m3.group(2))
        if mon:
            return _safe_make_date(y, mon, None, end_like=end_like)

    # Month only: "september" with ref_date
    m4 = re.fullmatch(r"([a-z]{3,9})", s2)
    if m4 and ref_date:
        mon = EN_MONTHS.get(m4.group(1))
        if mon:
            y = ref_date.year
            dt = _safe_make_date(y, mon, None, end_like=end_like)
            if dt and dt < ref_date:
                dt2 = _safe_make_date(y + 1, mon, None, end_like=end_like)
                return dt2 or dt
            return dt

    return None


def _parse_year_only(s, end_like=False):
    m = re.search(r"\b(19\d{2}|20\d{2})\b", s)
    if not m:
        return None
    y = int(m.group(1))
    return date(y, 12, 31) if end_like else date(y, 1, 1)


def _parse_season(s, end_like=False):
    # صيف2018 / summer2017
    s2 = s.lower().replace(" ", "")
    m = re.search(r"(صيف|summer)(19\d{2}|20\d{2})", s2)
    if not m:
        return None
    y = int(m.group(2))
    # summer ~ Jun..Aug
    return date(y, 8, 31) if end_like else date(y, 6, 1)


def _parse_mid_year(s, end_like=False):
    # 2020 منتصف / mid 2020
    s2 = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    if "منتصف" in s2 or "mid" in s2.lower():
        y = _parse_year_only(s2, end_like=False)
        if y:
            return date(y.year, 6, 30) if end_like else date(y.year, 6, 15)
    return None


# =========================================================
# 5) Import Log Model
# =========================================================
class AbHrImportLog(models.Model):
    _name = "ab_hr_import_log"
    _description = "MSSQL Import Log"

    import_date = fields.Datetime(default=fields.Datetime.now, required=True)
    mssql_app_id = fields.Integer(index=True)
    stage = fields.Selection([
        ("selection", "Selection Mapping"),
        ("m2o", "Many2one Lookup"),
        ("sql", "SQL Read"),
        ("write", "Create/Write"),
    ], default="m2o", required=True)
    message = fields.Text(required=True)
    payload = fields.Text()


class AbHrApplication(models.Model):
    _inherit = "ab_hr_application"

    mssql_app_id = fields.Integer(index=True, copy=False)

    def _resolve_job_by_map(self, cache, app_id_sql, raw_job_name):

        key_name = raw_job_name
        if key_name not in JOB_MANUAL_MAP:
            self._log_import(
                app_id_sql,
                "m2o",
                f"Job not found in map -> linked to unknown: {raw_job_name}",
                payload={"job_raw": raw_job_name, "job_norm": key_name},
            )
            return None

        target = JOB_MANUAL_MAP.get(key_name)

        # 2) If mapped empty -> unknown

        RequiredJob = self.env["ab_required_job"].sudo()
        required_job = RequiredJob.search([("name", "=ilike", target)], limit=1)
        return required_job.id or None

    # =========================
    # Smart Date API (inside model)
    # =========================

    def _smart_parse_date(self, v, ref_date=None, end_like=False, allow_open_end=False):
        """
        Returns:
          - date (best effort)
          - False if allow_open_end and present-like (useful for ending_date)
          - DEFAULT_DATE if cannot parse
        """
        if v in (None, "", False):
            return DEFAULT_DATE

        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()

        s = _clean_date_text(v)
        if not s or s == "0":
            return DEFAULT_DATE

        s_low = s.lower()
        # ------------------------------------------
        # Month-only patterns in same ref_date year:
        # "9" / "شهر 9" / "شهر9" / "9 شهر"
        # ------------------------------------------
        if ref_date:
            compact = s.replace(" ", "")

            # Case 1: "9" (number only) => month in same year
            if re.fullmatch(r"\d{1,2}", compact):
                mo = int(compact)
                if 1 <= mo <= 12:
                    return _safe_make_date(ref_date.year, mo, None, end_like=end_like) or DEFAULT_DATE

            # Case 2: "شهر9" or "شهر 9"
            m = re.search(r"\bشهر\s*(\d{1,2})\b", s)
            if m:
                mo = int(m.group(1))
                if 1 <= mo <= 12:
                    return _safe_make_date(ref_date.year, mo, None, end_like=end_like) or DEFAULT_DATE

            # Case 3: "9 شهر"
            m = re.search(r"\b(\d{1,2})\s*شهر\b", s)
            if m:
                mo = int(m.group(1))
                if 1 <= mo <= 12:
                    return _safe_make_date(ref_date.year, mo, None, end_like=end_like) or DEFAULT_DATE

        if allow_open_end:
            # present-like anywhere in text
            present_lows = [x.lower() for x in PRESENT_WORDS]
            if any(p in s_low for p in present_lows):
                return False

        # if contains a real date inside
        inside = _parse_first_real_date_inside(s, ref_date=ref_date, end_like=end_like)
        if inside:
            return inside

        # try Odoo parsing
        try:
            dt = fields.Date.to_date(s)
            if dt:
                return dt
        except Exception:
            pass

        # "شهر11" or "شهر 11" without year -> infer from ref_date
        compact = s.replace(" ", "")
        m = re.search(r"\bشهر(\d{1,2})\b", compact)
        if m and ref_date:
            mo = int(m.group(1))
            if 1 <= mo <= 12:
                y = ref_date.year
                dt = _safe_make_date(y, mo, None, end_like=end_like)
                if dt and dt < ref_date:
                    dt2 = _safe_make_date(y + 1, mo, None, end_like=end_like)
                    return dt2 or dt
                return dt or DEFAULT_DATE

        # month names / seasons / mid-year
        dt = _parse_monthname_year(s, ref_date=ref_date, end_like=end_like)
        if dt:
            return dt

        dt = _parse_season(s, end_like=end_like) or _parse_mid_year(s, end_like=end_like)
        if dt:
            return dt

        # year-only
        dt = _parse_year_only(s, end_like=end_like)
        if dt:
            return dt

        # known formats after cleaning spaces
        fmts = [
            "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d",
            "%d.%m.%Y", "%Y.%m.%d",
            "%m/%Y", "%m-%Y", "%Y/%m", "%Y-%m",
            "%Y",
        ]
        for fmt in fmts:
            try:
                dt2 = datetime.strptime(s, fmt)
                if fmt == "%Y":
                    return date(dt2.year, 12, 31) if end_like else date(dt2.year, 1, 1)
                if fmt in ("%m/%Y", "%m-%Y", "%Y/%m", "%Y-%m"):
                    return _safe_make_date(dt2.year, dt2.month, None, end_like=end_like) or DEFAULT_DATE
                return dt2.date()
            except Exception:
                continue

        _logger.warning("Unparseable date %r -> using %s", s, DEFAULT_DATE)
        return DEFAULT_DATE

    def _smart_end_date(self, end_value, start_date):
        """
        - If end_value is a real date => return it (end_like=True)
        - If end_value is present-like => return False (open-ended)
        - If end_value is a duration text/number => start_date + duration
        - Else => DEFAULT_DATE
        """
        d = self._smart_parse_date(end_value, ref_date=start_date, end_like=True, allow_open_end=True)
        if d is False:
            return False
        if d != DEFAULT_DATE:
            return d

        s = _clean_date_text(end_value)
        if not s or s == "0":
            return DEFAULT_DATE

        dur = _parse_duration_to_delta(s)
        if dur and isinstance(start_date, date) and start_date != DEFAULT_DATE:
            months, days = dur
            out = start_date
            if abs(months) > 1e-9:
                out = _add_months(out, months)
            if days:
                out = out + timedelta(days=days)
            return out

        return DEFAULT_DATE

    # -------------------------
    # Policy for missing refs
    # -------------------------
    def _get_policy(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "mssql.import_policy", "default"
        ).strip()

    # =========================
    # MSSQL Connection
    # =========================
    def _mssql_connect(self):
        if not pyodbc:
            raise UserError(_("pyodbc غير مثبت. نفّذ: pip install pyodbc"))

        ICP = self.env["ir.config_parameter"].sudo()
        driver = ICP.get_param("mssql.driver", "ODBC Driver 17 for SQL Server")
        server = ICP.get_param("mssql.server")
        database = ICP.get_param("mssql.database")
        username = ICP.get_param("mssql.username")
        password = ICP.get_param("mssql.password")

        if not server or not database:
            raise UserError(_("لازم تضبط system parameters: mssql.server و mssql.database"))

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};PWD={password};"
            "TrustServerCertificate=yes;"
        )
        return pyodbc.connect(conn_str)

    # =========================
    # Egypt country helper
    # =========================
    def _egypt_country(self):
        eg = self.env["res.country"].sudo().search([("code", "=", "EG")], limit=1)
        if not eg:
            raise UserError(_("مش لاقي دولة مصر (EG) في res.country. لازم تكون موجودة."))
        return eg

    # =========================
    # Default Unknown Records
    # =========================
    def _unknown_job(self):
        RequiredJob = self.env["ab_required_job"].sudo()
        required_job = RequiredJob.search([("name", "=", "غير محدد")], limit=1)
        if not required_job:
            required_job = RequiredJob.search([], order="id", limit=1)
        if not required_job:
            raise UserError(_("No Required Job found. Please create at least one Required Job before import."))
        return required_job.id

    def _unknown_city(self):
        city = self.env["ab_city"].sudo().search([("name", "=", "غير محدد")], limit=1)
        if not city:
            city = self.env["ab_city"].sudo().create({"name": "غير محدد"})
        return city.id

    def _unknown_state(self):
        eg = self._egypt_country()
        st = self.env["res.country.state"].sudo().search(
            [("name", "=", "غير محدد"), ("country_id", "=", eg.id)],
            limit=1
        )
        if not st:
            st = self.env["res.country.state"].sudo().create({
                "name": "غير محدد",
                "country_id": eg.id,
            })
        return st.id

    # =========================
    # Logging
    # =========================
    def _log_import(self, mssql_app_id, stage, message, payload=None):
        try:
            self.env["ab_hr_import_log"].sudo().create({
                "mssql_app_id": int(mssql_app_id or 0),
                "stage": stage,
                "message": message,
                "payload": payload and str(payload) or False,
            })
        except Exception:
            _logger.exception("Failed writing import log")

    # =========================
    # Many2one helpers
    # =========================
    def _get_or_create_center_city(self, cache, center_ar, gov_id):
        name = _norm(center_ar)
        if not name:
            return self._unknown_city()

        key = ("ab_city", name, gov_id or 0)
        if key in cache:
            return cache[key]

        City = self.env["ab_city"].sudo()
        rec = City.search([("name", "=ilike", name), ("state_id", "=", gov_id)], limit=1)

        if not rec:
            rec = City.search([("name", "=ilike", name)], limit=1)
            if rec and gov_id and rec.state_id.id != gov_id:
                _logger.warning(
                    "City exists with different governorate: city=%s (%s) mssql_gov_id=%s. Keeping existing link.",
                    rec.name, rec.state_id.name, gov_id
                )

        if not rec:
            if not gov_id:
                gov_id = self._unknown_state()
            rec = City.create({"name": name, "state_id": gov_id})
            _logger.info("Created city from MSSQL: %s (state_id=%s)", name, gov_id)

        cache[key] = rec.id
        return rec.id

    def _resolve_m2o(self, cache, model, raw_name, unknown_getter=None, create_extra_vals=None):
        policy = self._get_policy()
        name = _norm(raw_name)

        if not name:
            if policy == "default" and unknown_getter:
                return unknown_getter()
            if policy == "skip":
                return None
            return False

        key = (model, name)
        if key in cache:
            return cache[key]

        env = self.env[model].sudo()

        rec = env.search([("name", "=ilike", name)], limit=1)
        if not rec:
            rec = env.search([("name", "ilike", name)], limit=1)

        if rec:
            cache[key] = rec.id
            return rec.id

        if policy == "create":
            vals = {"name": name}
            if model == "res.country.state":
                vals["country_id"] = self._egypt_country().id
            if create_extra_vals:
                vals.update(create_extra_vals)
            rec = env.create(vals)
            cache[key] = rec.id
            return rec.id

        if policy == "default" and unknown_getter:
            uid = unknown_getter()
            cache[key] = uid
            return uid

        cache[key] = None
        return None

    def _get_governorate_id_from_mssql(self, gov_ar):
        if not gov_ar:
            return False
        gov_en = GOV_TRANSLATE.get(gov_ar)
        if not gov_en:
            return False
        st = self.env["res.country.state"].sudo().search([
            ("name", "=", gov_en),
            ("country_id.code", "=", "EG"),
        ], limit=1)
        return st.id or False

    def _safe_salary(self, v):
        INT32_MAX = 2147483647
        INT32_MIN = -2147483648

        if v in (None, False, ""):
            return 0
        try:
            n = int(v)
        except Exception:
            return 0
        if n > INT32_MAX or n < INT32_MIN:
            return 0
        return n

    # =========================
    # Map selections (strict)
    # =========================
    def _map_selections_or_raise(self, app_id_sql, military_serv, relig_t, gender_type, socialst_type, formtype):
        mil = MILITARY_MAP.get(military_serv)
        rel = RELIGION_MAP.get(relig_t)
        gen = GENDER_MAP.get(gender_type)
        mar = MARITAL_MAP.get(socialst_type)
        frm = FORMTYPE_MAP.get(formtype)

        missing = []
        if mil is None:
            missing.append(("Military_serv", military_serv))
        if gen is None:
            missing.append(("Gender_type", gender_type))
        if mar is None:
            missing.append(("Socialst_type", socialst_type))
        if frm is None:
            missing.append(("formtype", formtype))

        if missing:
            msg = f"Unmapped selection values App_Id={app_id_sql}: {missing}"
            self._log_import(app_id_sql, "selection", msg, payload={
                "Military_serv": military_serv,
                "Relig_t": relig_t,
                "Gender_type": gender_type,
                "Socialst_type": socialst_type,
                "formtype": formtype,
            })
            raise UserError(msg)

        return mil, rel, gen, mar, frm

    # =========================
    # One2many builders
    # =========================
    def _build_experiences(self, data):
        cmds = [(5, 0, 0)]

        ref = data.get("insert_time")
        ref_date = (ref.date() if isinstance(ref, datetime) else None) or fields.Date.context_today(self)

        for i in range(1, 7):
            company_name = data.get(f"Exp_company{i}")
            title = data.get(f"Exp_Title{i}")
            date_from = data.get(f"Exp_from{i}")
            date_to = data.get(f"Exp_to{i}")
            reason = data.get(f"Re_Le{i}")
            salary = data.get(f"Sa_Le{i}")

            if not company_name and not title and not date_from and not date_to and not reason and not salary:
                continue

            # هنا بقى ref_date سنة الانشاء
            start_dt = self._smart_parse_date(date_from, ref_date=ref_date, end_like=False, allow_open_end=False)
            end_dt = self._smart_end_date(date_to, start_dt)

            cmds.append((0, 0, {
                "company_name": company_name or "Unknown",
                "job_title": title or False,
                "starting_date": start_dt,
                "ending_date": end_dt,
                "reason_for_leaving": reason or False,
                "salary": self._safe_salary(salary) or False,
            }))

        return cmds

    def _build_courses(self, data):
        cmds = [(5, 0, 0)]
        for i in range(1, 3):
            specialty = data.get(f"Train_Specialty{i}")
            org = data.get(f"Train_org{i}")
            ttime = data.get(f"Train_time{i}")
            grade = data.get(f"Train_grade{i}")

            if not specialty and not org and not ttime and not grade:
                continue

            cmds.append((0, 0, {
                "specialty": specialty or False,
                "organization": org or False,
                "time_period": ttime or False,
                "grade": grade or False,
            }))
        return cmds

    # =========================================================
    # MAIN IMPORT
    # =========================================================
    @api.model
    def import_from_mssql(self, insert_from, insert_to, app_id=None, commit_every=200, sync_children=True):
        if not insert_from or not insert_to:
            raise UserError(_("لازم تحدد insert_from و insert_to"))

        insert_from_dt = fields.Datetime.to_datetime(insert_from)
        insert_to_dt = fields.Datetime.to_datetime(insert_to)

        conn = self._mssql_connect()
        cur = conn.cursor()

        sql = """
        SELECT
            t1.App_Id,
            t1.app_nam,
            t1.App_NatId,
            t2.Military_serv,
            CAST(t1.App_Birthdate as date) AS App_Birthdate,
            t3.Governo,
            t4.Center,
            t1.App_address,
            t5.Relig_t,
            t1.App_Mobile,
            t1.App_tel,
            t1.App_Email,
            t6.Gender_type,
            t1.App_Qual,
            CAST(t1.App_Graddate as date) AS App_Graddate,
            t8.Socialst_type,
            t9.formtype,
            t10.Job_Name,
            t1.Exp_salary,
            t1.W_Morning,
            t1.W_After,
            t1.W_Night,
            t1.W_Eplus,
            t1.insert_time,

            t1.Exp_company1, t1.Exp_Title1, t1.Exp_from1, t1.Exp_to1, t1.Re_Le1, t1.Sa_Le1,
            t1.Exp_company2, t1.Exp_Title2, t1.Exp_from2, t1.Exp_to2, t1.Re_Le2, t1.Sa_Le2,
            t1.Exp_company3, t1.Exp_Title3, t1.Exp_from3, t1.Exp_to3, t1.Re_Le3, t1.Sa_Le3,
            t1.Exp_company4, t1.Exp_Title4, t1.Exp_from4, t1.Exp_to4, t1.Re_Le4, t1.Sa_Le4,
            t1.Exp_company5, t1.Exp_Title5, t1.Exp_from5, t1.Exp_to5, t1.Re_Le5, t1.Sa_Le5,
            t1.Exp_company6, t1.Exp_Title6, t1.Exp_from6, t1.Exp_to6, t1.Re_Le6, t1.Sa_Le6,

            t1.Train_Specialty1, t1.Train_org1, t1.Train_time1, t1.Train_grade1,
            t1.Train_Specialty2, t1.Train_org2, t1.Train_time2, t1.Train_grade2

        FROM dbo.Applications t1
        LEFT JOIN dbo.[Military ] t2 ON t1.App_mili = t2.Mil_id
        LEFT JOIN dbo.Governorates t3 ON t1.App_Gov = t3.Gove_id
        LEFT JOIN dbo.Gov_Cen t4 ON t1.App_Cen = t4.Gov_id
        LEFT JOIN dbo.Religion t5 ON t1.App_relig = t5.Relig_id
        LEFT JOIN dbo.Gender t6 ON t1.App_gen = t6.Gend_id
        LEFT JOIN dbo.Social_status t8 ON t1.App_Sos = t8.Socialst_id
        LEFT JOIN dbo.Form_type t9 ON t1.Requ_type = t9.Id_formtype
        LEFT JOIN dbo.Required_Job t10 ON t1.Requ_job = t10.Job_Id
        WHERE
            t1.insert_time > ? AND t1.insert_time < ?
            AND (? IS NULL OR t1.App_Id = ?)
        ORDER BY t1.App_Id
        """

        try:
            cur.execute(sql, insert_from_dt, insert_to_dt, app_id, app_id)
        except Exception as e:
            self._log_import(app_id, "sql", f"SQL execute error: {e}")
            raise

        cols = [c[0] for c in cur.description]
        cache = {}

        processed = created = updated = skipped = 0
        policy = self._get_policy()

        while True:
            rows = cur.fetchmany(500)
            if not rows:
                break

            for r in rows:
                data = dict(zip(cols, r))
                app_id_sql = data.get("App_Id")
                print("Processing App_Id:", app_id_sql)
                if not app_id_sql:
                    continue

                # ---- selections ----
                try:
                    mil, rel, gen, mar, frm = self._map_selections_or_raise(
                        app_id_sql,
                        data.get("Military_serv"),
                        data.get("Relig_t"),
                        data.get("Gender_type"),
                        data.get("Socialst_type"),
                        data.get("formtype"),
                    )
                except Exception:
                    skipped += 1
                    if policy == "skip":
                        continue
                    raise

                # governorate lookup only
                gov_ar = data.get("Governo")
                gov_id = self._get_governorate_id_from_mssql(gov_ar)
                if not gov_id and gov_ar:
                    self._log_import(
                        app_id_sql,
                        "m2o",
                        f"Governorate not found in Odoo (lookup only): {gov_ar}",
                        payload={"Governo_ar": gov_ar, "mapped": GOV_TRANSLATE.get(_norm(gov_ar))}
                    )

                # city
                center_ar = data.get("Center")
                city_id = self._get_or_create_center_city(cache, center_ar, gov_id)

                # job
                # job (strict by map: link or empty; no create)
                required_job_id = self._resolve_job_by_map(cache, app_id_sql, data.get("Job_Name"))

                if policy == "skip" and (gov_id is False or gov_id is None or city_id is None or required_job_id is None):
                    self._log_import(app_id_sql, "m2o", "Skipped بسبب مرجع غير موجود", payload={
                        "Governo_ar": data.get("Governo"),
                        "Governo_mapped": GOV_TRANSLATE.get(_norm(data.get("Governo")) or ""),
                        "Center_ar": data.get("Center"),
                        "Center_used": city_id,
                        "Job_Name": data.get("Job_Name"),
                    })
                    skipped += 1
                    continue

                # upsert
                rec = self.sudo().search([("mssql_app_id", "=", int(app_id_sql))], limit=1)

                vals = {
                    "mssql_app_id": int(app_id_sql),
                    "name": data.get("app_nam") or False,
                    "national_identity": data.get("App_NatId") or False,
                    "birth_date": data.get("App_Birthdate") or False,
                    "address": data.get("App_address") or False,
                    "mobile": data.get("App_Mobile") or False,
                    "telephone": data.get("App_tel") or False,
                    "email": data.get("App_Email") or False,
                    "qualification": data.get("App_Qual") or False,
                    "graduate_date": data.get("App_Graddate") or False,
                    "expected_salary": float(data.get("Exp_salary") or 0.0),

                    "military_status": mil,
                    "religion": rel or False,
                    "gender": gen,
                    "marital_status": mar,
                    "type_of_form": frm,

                    "governorate_id": gov_id or False,
                    "city_id": city_id or False,
                    "required_job_id": required_job_id or False,

                    "morning": bool(data.get("W_Morning")),
                    "evening": bool(data.get("W_After")),
                    "after_midnight": bool(data.get("W_Night")),
                    "bconnect_experience": bool(data.get("W_Eplus")),
                }

                if sync_children:
                    vals["experience_ids"] = self._build_experiences(data)
                    vals["trainingcourses_ids"] = self._build_courses(data)

                try:
                    if rec:
                        rec.sudo().write(vals)
                        updated += 1
                    else:
                        self.sudo().create(vals)
                        created += 1
                except Exception as e:
                    self._log_import(app_id_sql, "write", f"Write error: {e}", payload={"vals": vals})
                    if policy == "skip":
                        skipped += 1
                        continue
                    raise

                processed += 1
                if commit_every and processed % int(commit_every) == 0:
                    self.env.cr.commit()
                    _logger.info("MSSQL Import progress: %s", processed)

            self.env.cr.commit()

        try:
            conn.close()
        except Exception:
            pass

        msg = f"Done. processed={processed}, created={created}, updated={updated}, skipped={skipped}, policy={policy}"
        _logger.info(msg)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "MSSQL Import",
                "message": msg,
                "type": "success" if skipped == 0 else "warning",
                "sticky": False,
            }
        }


class AbHrInterviewInherit(models.Model):
    _inherit = "ab_hr_interview"

    # MSSQL Interviews.int_Id
    mssql_int_id = fields.Integer(string="MSSQL Interview ID", index=True, copy=False)

    @api.model
    def _float_from_time(self, t):
        """Convert time (HH:MM:SS) -> float hours (HH + MM/60)."""
        if not t:
            return 0.0
        try:
            hh = int(getattr(t, "hour", 0))
            mm = int(getattr(t, "minute", 0))
            ss = int(getattr(t, "second", 0))
        except Exception:
            s = str(t).strip()
            if not s:
                return 0.0
            parts = s.split(":")
            hh = int(parts[0]) if len(parts) > 0 and parts[0] else 0
            mm = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            ss = int(parts[2]) if len(parts) > 2 and parts[2] else 0

        return hh + (mm / 60.0) + (ss / 3600.0)

    def _mssql_connect(self):
        if not pyodbc:
            raise UserError(_("pyodbc غير مثبت. نفّذ: pip install pyodbc"))

        ICP = self.env["ir.config_parameter"].sudo()
        driver = ICP.get_param("mssql.driver", "ODBC Driver 17 for SQL Server")
        server = ICP.get_param("mssql.server")
        database = ICP.get_param("mssql.database")
        username = ICP.get_param("mssql.username")
        password = ICP.get_param("mssql.password")

        if not server or not database:
            raise UserError(_("لازم تضبط system parameters: mssql.server و mssql.database"))

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};PWD={password};"
            "TrustServerCertificate=yes;"
        )
        return pyodbc.connect(conn_str)

        if pyodbc is None:
            raise UserError(_("pyodbc is not installed on the server."))

    @api.model
    def import_interviews_from_mssql(self):
        """
        - Upsert by mssql_int_id (t11.int_Id)
        - Interviewer mapping: MANUAL Arabic mapping using FULL interviewer_Name (titles kept)
        - Action: NO mapping (only accept if matches selection key)
        """

        sql = """
        WITH q AS (
            select
                t11.int_Id as int_Id,
                t1.App_Id as App_Id,
                LTRIM(RTRIM(t12.interviewer_Name)) as interviewer_Name,
                t11.int_interview_date as int_interview_date,
                t14.Acton as Acton,
                LTRIM(RTRIM(t15.Hsto_name)) as Hsto_name,
                t13.Fr_Ac as Fr_Ac,
                t13.To_Ac as To_Ac,
                cast(t13.Fr_Tra as time(0)) as Fr_Tra,
                cast(t13.To_Tra as time(0)) as To_Tra,
                row_number() over (partition by t11.int_Id order by t13.Int_Id_Ac desc) as rn
            from Applications t1
            left join Interviews t11 on t1.App_Id=t11.int_App_Id
            left join interviewers t12 on t11.int_interviewer=t12.interviewer_id
            left join Int_Action t13 on t13.Int_Id_Ac=t11.int_Id
            left join Acti_App t14 on t13.Int_Ac=t14.Id_Ac
            left join EStore t15  on t15.S_id=t13.Br_Ac
            where t11.int_type='1'
              and t11.int_status='1'
              and t11.int_st=1
              and ( t13.Int_Ac is not null or t11.int_interview_insert_date >'2021-03-17 11:31:00')
        )
        SELECT * FROM q WHERE rn = 1;
        """
        conn = self._mssql_connect()
        cur = conn.cursor()
        cur.execute(sql)

        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()

        Applicant = self.env["ab_hr_application"].sudo()
        Interview = self.env["ab_hr_interview"].sudo()
        Employee = self.env["ab_hr_employee"].sudo()
        Store = self.env["ab_store"].sudo()

        created = updated = skipped = no_map = no_employee = 0
        missing_mssql_names = set()
        missing_ar_names = set()

        action_keys = set(dict(self._fields["action"].selection).keys())

        for row in rows:
            rec = dict(zip(cols, row))

            int_id = rec.get("int_Id")
            app_id = rec.get("App_Id")

            if not int_id or not app_id:
                skipped += 1
                continue

            applicant = Applicant.search([("mssql_app_id", "=", int(app_id))], limit=1)
            if not applicant:
                skipped += 1
                continue

            # ✅ interviewer mapping (FULL NAME WITH TITLES, no changes)
            mssql_name = (rec.get("interviewer_Name") or "").strip()
            ar_name = INTERVIEWER_AR_MAP.get(mssql_name)

            if not ar_name:
                no_map += 1
                missing_mssql_names.add(mssql_name or "(empty)")
                continue  # interviewer_id required -> skip

            interviewer = Employee.search([("name", "=", ar_name.strip())], limit=1)
            if not interviewer:
                no_employee += 1
                missing_ar_names.add(ar_name.strip())
                continue

            # store (optional)
            store_id = False
            store_name = rec.get("Hsto_name")
            if store_name:
                st = Store.search([("name", "=", store_name)], limit=1)
                store_id = st.id if st else False

            # action without mapping (must be a selection key)
            action_val = rec.get("Acton")
            action_val = action_mapping.get(action_val)
            action_key = action_val if action_val in action_keys else False

            vals = {
                "mssql_int_id": int(int_id),
                "applicant_id": applicant.id,
                "interviewer_id": interviewer.id,
                "interview_date": rec.get("int_interview_date") or fields.Datetime.now(),
                "action": action_key or False,
                "store_id": store_id,
                "starting_date": rec.get("Fr_Ac") or False,
                "ending_date": rec.get("To_Ac") or False,
                "from_hour": self._float_from_time(rec.get("Fr_Tra")),
                "to_hour": self._float_from_time(rec.get("To_Tra")),
            }

            # keep your logic: if not training, clear training fields
            # if vals.get("action") != "training":
            #     vals.update({
            #         "store_id": False,
            #         "starting_date": False,
            #         "ending_date": False,
            #         "from_hour": 0.0,
            #         "to_hour": 0.0,
            #     })

            existing = Interview.search([("mssql_int_id", "=", int(int_id))], limit=1)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                Interview.create(vals)
                created += 1

        cur.close()
        conn.close()

        if missing_mssql_names:
            _logger.warning("No Arabic map for these MSSQL interviewer names: %s", sorted(missing_mssql_names))
        if missing_ar_names:
            _logger.warning("Arabic names in map not found as employees in Odoo: %s", sorted(missing_ar_names))

        _logger.info(
            "Import done created=%s updated=%s skipped=%s no_map=%s no_employee=%s",
            created, updated, skipped, no_map, no_employee
        )

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "no_map": no_map,
            "no_employee": no_employee,
            "missing_mssql_names_no_map": sorted(missing_mssql_names),
            "missing_ar_names_not_found": sorted(missing_ar_names),
        }
