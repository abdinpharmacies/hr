from odoo import models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    def _ab_storefront_name(self):
        self.ensure_one()
        if not (self.env.lang or "").startswith("ar") or self.country_id.code != "EG":
            return self.name

        match self.code:
            case "DK":
                return self.env._("Dakahlia")
            case "BA":
                return self.env._("Red Sea")
            case "BH":
                return self.env._("Beheira")
            case "FYM":
                return self.env._("Faiyum")
            case "GH":
                return self.env._("Gharbia")
            case "ALX":
                return self.env._("Alexandria")
            case "IS":
                return self.env._("Ismailia")
            case "GZ":
                return self.env._("Giza")
            case "MNF":
                return self.env._("Monufia")
            case "MN":
                return self.env._("Minya")
            case "C":
                return self.env._("Cairo")
            case "KB":
                return self.env._("Qalyubia")
            case "LX":
                return self.env._("Luxor")
            case "WAD":
                return self.env._("New Valley")
            case "SHR":
                return self.env._("Al Sharqia")
            case "SU":
                return self.env._("6th of October")
            case "SUZ":
                return self.env._("Suez")
            case "ASN":
                return self.env._("Aswan")
            case "AST":
                return self.env._("Asyut")
            case "BNS":
                return self.env._("Beni Suef")
            case "PTS":
                return self.env._("Port Said")
            case "DT":
                return self.env._("Damietta")
            case "HU":
                return self.env._("Helwan")
            case "JS":
                return self.env._("South Sinai")
            case "KFS":
                return self.env._("Kafr el-Sheikh")
            case "MT":
                return self.env._("Matrouh")
            case "KN":
                return self.env._("Qena")
            case "SIN":
                return self.env._("North Sinai")
            case "SHG":
                return self.env._("Sohag")

        return self.name
