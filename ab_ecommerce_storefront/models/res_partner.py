from odoo import fields, models

AVATAR_SELECTION = [
    ("avatar_none", "No Profile Picture"),
    ("custom", "Uploaded Profile Picture"),
    ("avatar_01", "Friendly Pharmacist"),
    ("avatar_02", "Healthcare Shopper"),
    ("avatar_03", "Wellness Care"),
    ("avatar_04", "Family Care"),
    ("avatar_05", "Daily Health"),
    ("avatar_06", "Support Care"),
    ("avatar_07", "Pharmacy Friend"),
    ("avatar_08", "Active Wellness"),
    ("avatar_09", "Bright Care"),
    ("avatar_10", "Medicine Care"),
    ("avatar_11", "Trusted Care"),
    ("avatar_12", "Healthy Lifestyle"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    ab_storefront_avatar = fields.Selection(
        selection=AVATAR_SELECTION,
        string="Storefront Avatar",
        default="avatar_none",
        required=True,
        copy=False,
    )
    ab_storefront_has_cart_history = fields.Boolean(
        string="Has Storefront Cart History",
        copy=False,
        readonly=True,
    )
    ab_storefront_has_wishlist_history = fields.Boolean(
        string="Has Storefront Wishlist History",
        copy=False,
        readonly=True,
    )
    ab_storefront_seen_profile_onboarding = fields.Boolean(
        string="Seen Storefront Profile Onboarding",
        copy=False,
        readonly=True,
    )
