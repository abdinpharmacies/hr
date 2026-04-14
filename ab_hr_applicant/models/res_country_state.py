from odoo import api, models


EG_GOVERNORATE_AR_BY_CODE = {
    "ALX": "الإسكندرية",
    "ASN": "أسوان",
    "AST": "أسيوط",
    "BA": "البحر الأحمر",
    "BH": "البحيرة",
    "BNS": "بني سويف",
    "C": "القاهرة",
    "DK": "الدقهلية",
    "DT": "دمياط",
    "FYM": "الفيوم",
    "GH": "الغربية",
    "GZ": "الجيزة",
    "HU": "حلوان",
    "IS": "الإسماعيلية",
    "JS": "جنوب سيناء",
    "KB": "القليوبية",
    "KFS": "كفر الشيخ",
    "KN": "قنا",
    "LX": "الأقصر",
    "MN": "المنيا",
    "MNF": "المنوفية",
    "MT": "مطروح",
    "PTS": "بورسعيد",
    "SHG": "سوهاج",
    "SHR": "الشرقية",
    "SIN": "شمال سيناء",
    "SU": "السادس من أكتوبر",
    "SUZ": "السويس",
    "WAD": "الوادي الجديد",
}


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    @api.depends("country_id")
    @api.depends_context("formatted_display_name", "lang")
    def _compute_display_name(self):
        super()._compute_display_name()
        lang = (self.env.context.get("lang") or "").lower()
        if not lang.startswith("ar"):
            return

        formatted = bool(self.env.context.get("formatted_display_name"))
        for record in self:
            if record.country_id.code != "EG":
                continue
            ar_name = EG_GOVERNORATE_AR_BY_CODE.get(record.code)
            if not ar_name:
                continue
            if formatted:
                record.display_name = f"{ar_name} \t --{record.country_id.code}--"
            else:
                record.display_name = f"{ar_name} ({record.country_id.code})"
