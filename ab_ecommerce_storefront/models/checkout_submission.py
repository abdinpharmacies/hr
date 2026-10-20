import hashlib
import json
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import consteq


class StorefrontSubmission(models.Model):
    _name = "ab_storefront_submission"
    _description = "Storefront Submission"

    key = fields.Char(required=True, default=lambda self: secrets.token_urlsafe(32), copy=False, index=True)
    owner_hash = fields.Char(required=True)
    kind = fields.Selection([("checkout", "Checkout"), ("prescription", "Prescription")], required=True)
    website_id = fields.Many2one("website", required=True)
    company_id = fields.Many2one("res.company", required=True)
    expires_at = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() + timedelta(days=1))
    payload_hash = fields.Char(copy=False)
    revision = fields.Char(copy=False)
    order_id = fields.Many2one("sale.order", ondelete="restrict", copy=False)
    result_partner_id = fields.Many2one("res.partner", ondelete="restrict", copy=False)
    prescription_id = fields.Many2one("ab.prescription.order", ondelete="restrict", copy=False)
    transaction_id = fields.Many2one("payment.transaction", ondelete="restrict", copy=False)

    _key_unique = models.Constraint("UNIQUE(key)", "The submission key must be unique.")

    @api.model
    def _fingerprint(self, payload):
        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        ).encode()).hexdigest()

    @api.model
    def _issue(self, kind, website, owner_hash, order=None):
        return self.sudo().create({
            "kind": kind, "website_id": website.id, "company_id": website.company_id.id,
            "owner_hash": owner_hash, "order_id": order.id if order else False,
        })

    @api.model
    def _claim(self, key, kind, website, owner_hash, payload):
        if not isinstance(key, str) or len(key) > 100:
            raise AccessError(self.env._("This submission does not belong to your session."))
        submission = self.sudo().search(
            fields.Domain("key", "=", key) & fields.Domain("kind", "=", kind)
            & fields.Domain("website_id", "=", website.id)
            & fields.Domain("company_id", "=", website.company_id.id), limit=1,
        )
        if not submission or not consteq(submission.owner_hash, owner_hash):
            raise AccessError(self.env._("This submission does not belong to your session."))
        self.env.cr.execute(
            "SELECT id FROM ab_storefront_submission WHERE id = %s FOR UPDATE", (submission.id,),
        )
        submission.invalidate_recordset()
        if submission.expires_at <= fields.Datetime.now() and not (
            submission.prescription_id or submission.transaction_id
        ):
            raise ValidationError(self.env._("This form has expired. Refresh the page and try again."))
        fingerprint = self._fingerprint(payload)
        if submission.payload_hash and not consteq(submission.payload_hash, fingerprint):
            raise ValidationError(self.env._("This submission was already used with different details. Refresh the page and try again."))
        submission.write({"payload_hash": fingerprint, "revision": secrets.token_hex(16)})
        submission.flush_recordset()
        return submission


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ab_checkout_submission_id = fields.Many2one(
        "ab_storefront_submission", string="Checkout Submission", copy=False,
        readonly=True, groups="base.group_system",
    )
