from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class SupplierClaimReviewerNote(models.TransientModel):
    _name = 'ab_supplier_claim_reviewer_note'
    _description = 'Supplier Claim Reviewer Note'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, readonly=True, ondelete='cascade')
    body = fields.Text(string='Note', required=True)

    def action_post_note(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('ab_supplier_claim_cycle.supplier_claim_group_reviewer'):
            raise AccessError(_('Only Supplier Claim Reviewers can use this note dialog.'))
        claim = self.claim_id
        claim.check_access('read')
        body = (self.body or '').strip()
        if not body:
            raise ValidationError(_('Enter a note before posting.'))

        # The Reviewer can read the claim. Elevate only the internal note post.
        claim.sudo().with_context(
            mail_post_autofollow=False, mail_post_autofollow_author_skip=True,
        ).message_post(
            body=body,
            author_id=self.env.user.partner_id.id,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return {'type': 'ir.actions.act_window_close'}
