import re

from odoo import _, models
from odoo.tools.float_utils import float_compare


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
        """Return customer-facing card data without exposing internal unit levels.

        Packaging levels become selectable only when a matching native Odoo UoM
        has the same conversion ratio. This keeps card selection and cart lines in
        sync instead of treating descriptive E-Plus packaging as a sale UoM.
        """
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
        raw_units = [
            ("large", ab_product.unit_l_id),
            ("medium", ab_product.unit_m_id),
            ("small", ab_product.unit_s_id),
        ]
        seen_names = set()
        meaningful_units = []
        for size, unit in raw_units:
            if not unit or not unit.type_id:
                continue
            normalized = self._ab_normalize_unit_name(unit.type_id.name)
            if not normalized or normalized in seen_names:
                continue
            seen_names.add(normalized)
            item = {
                "size": size,
                "name": unit.type_id.name,
                "normalized_name": normalized,
                "label": self._ab_storefront_unit_label(unit.type_id.name),
                "count": unit.unit_no or 1,
            }
            meaningful_units.append(item)
            result["pack_units"].append(item)

        if meaningful_units:
            result["purchase_options"][0]["label"] = meaningful_units[0]["label"]
            result["purchase_options"][0]["unit_code"] = meaningful_units[0]["normalized_name"]

        # Alternate packaging is descriptive unless Odoo has a real sale UoM
        # with the same name and conversion. This avoids incorrect cart payloads.
        if not ab_product.allow_sell_fraction or len(meaningful_units) < 2:
            return result
        large_count = ab_product.unit_s_id.unit_no or 1
        root_uom_id = int(template.uom_id.parent_path.split("/")[0])
        category_uoms = self.env["uom.uom"].sudo().search([
            ("id", "child_of", root_uom_id),
            ("active", "=", True),
        ])
        for item in meaningful_units[1:]:
            if item["size"] == "medium":
                expected_base_qty = 1.0 / (ab_product.unit_m_id.unit_no or 1)
            else:
                expected_base_qty = 1.0 / large_count
            matching_uom = category_uoms.filtered(
                lambda uom: self._ab_normalize_unit_name(uom.name) == item["normalized_name"]
                and float_compare(
                    uom._compute_quantity(1, template.uom_id, round=False),
                    expected_base_qty,
                    precision_digits=6,
                ) == 0
            )[:1]
            if not matching_uom:
                continue
            result["purchase_options"].append({
                "key": item["size"],
                "label": item["label"],
                "unit_code": item["normalized_name"],
                "uom_id": matching_uom.id,
                "price_reduce": template.uom_id._compute_price(reduced_price, matching_uom),
                "base_price": template.uom_id._compute_price(base_price, matching_uom),
            })
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
