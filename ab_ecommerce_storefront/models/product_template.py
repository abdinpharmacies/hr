import re

from odoo import _, models


_UNIT_LABELS = {
    "AMPOULE": "Ampoule",
    "BOTTLE": "Bottle",
    "BOX": "Box",
    "CAP": "Capsule",
    "CAPSULE": "Capsule",
    "JAR": "Jar",
    "PACK": "Pack",
    "PCS": "Piece",
    "PIECE": "Piece",
    "SACHET": "Sachet",
    "STRIP": "Strip",
    "SUPP": "Suppository",
    "SUPPOSITORY": "Suppository",
    "TAB": "Tablet",
    "TABLET": "Tablet",
    "TUBE": "Tube",
    "UNIT": "Piece",
    "VIAL": "Vial",
}

_AB_STOREFRONT_PLACEHOLDER_CHECKSUM = "85838e6e327fcf3ff85efa8cd978fe725ec5d53a"
_AB_PRODUCT_TEMPLATE_IMAGE_FIELDS = (
    "image_1920",
    "image_1024",
    "image_512",
    "image_256",
    "image_128",
)
_AB_PRODUCT_VARIANT_IMAGE_FIELDS = (
    "image_variant_1920",
    "image_variant_1024",
    "image_variant_512",
    "image_variant_256",
    "image_variant_128",
)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _ab_storefront_has_real_image(self):
        self.ensure_one()
        image_attachment = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("res_field", "in", _AB_PRODUCT_TEMPLATE_IMAGE_FIELDS),
        ], limit=1)
        return bool(
            image_attachment
            and image_attachment.checksum != _AB_STOREFRONT_PLACEHOLDER_CHECKSUM
        )

    def _ab_storefront_sales_price(self, product=None):
        """Provide website prices where a tile caller has no batch price helper."""
        target = product or self
        target.ensure_one()
        website = target.env["website"].get_current_website()
        return target._get_sales_prices(website)[target.id]

    @staticmethod
    def _ab_normalize_unit_name(name):
        return re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).strip()

    def _ab_storefront_unit_label(self, name):
        normalized = self._ab_normalize_unit_name(name)
        source = _UNIT_LABELS.get(normalized)
        return source or name or _("Unit")

    def _ab_storefront_card_data(self, price_values=None):
        self.ensure_one()
        template = self.sudo()
        ab_product = template.ab_product_id.sudo()
        price_values = price_values or {}
        reduced_price = price_values.get("price_reduce", template.list_price)
        base_price = price_values.get("base_price", reduced_price)
        result = {
            "pack_units": [],
            "purchase_options": [{
                "key": "default",
                "label": template.uom_id.name or _("Unit"),
                "unit_code": self._ab_normalize_unit_name(template.uom_id.name),
                "uom_id": template.uom_id.id,
                "price_reduce": reduced_price,
                "base_price": base_price,
            }],
            "is_service": False,
            "is_narcotic": False,
        }
        if not ab_product:
            return result

        result.update({
            "is_service": bool(ab_product.is_service),
            "is_narcotic": bool(ab_product.is_narcotic),
        })
        large_unit = ab_product.unit_l_id
        if large_unit and large_unit.type_id:
            normalized = self._ab_normalize_unit_name(large_unit.type_id.name)
            if normalized:
                result["purchase_options"][0]["label"] = self._ab_storefront_unit_label(large_unit.type_id.name)
                result["purchase_options"][0]["unit_code"] = normalized
        return result


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _ab_storefront_has_real_image(self):
        self.ensure_one()
        image_attachment = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("res_field", "in", _AB_PRODUCT_VARIANT_IMAGE_FIELDS),
        ], limit=1)
        if image_attachment:
            return image_attachment.checksum != _AB_STOREFRONT_PLACEHOLDER_CHECKSUM
        return self.product_tmpl_id._ab_storefront_has_real_image()
