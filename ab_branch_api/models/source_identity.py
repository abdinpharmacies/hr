"""Authenticated source identity, separate from destination routing."""
from uuid import UUID
from odoo import fields, models, _
from odoo.exceptions import AccessError


class SourceAPI(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _validated_source_identity(self, serial, source=None):
        # The bearer-authenticated callcenter role may declare any active source.
        # This is deliberately independent of destination routing and user bindings.
        if not self.env.user.has_group('ab_sales.group_call_center'):
            raise AccessError(_('Only a Call Center user can submit source identity.'))
        if type(serial) is not int or serial <= 0:
            raise AccessError(_('Source DB serial must be a positive integer.'))
        replicas = self.env['ab_replica_db'].sudo().search(
            fields.Domain('db_serial', '=', serial) & fields.Domain('active', '=', True), limit=2)
        if len(replicas) != 1:
            raise AccessError(_('Source DB serial must identify exactly one active replica.'))
        identity = {'source_db_serial': serial, 'source_user_id': self.env.uid}
        if source is not None:
            try:
                identity['source'] = str(UUID(source))
            except (ValueError, TypeError, AttributeError):
                raise AccessError(_('Invalid source database UUID metadata.')) from None
        return identity

    def _sale_source_identity(self, payload):
        if 'source_db_serial' not in payload:
            return {}
        context = payload.get('metadata_context', {})
        if not isinstance(context, dict):
            raise AccessError(_('Submission source identity is invalid or unauthorized.'))
        return self._validated_source_identity(payload['source_db_serial'], context.get('source'))


class ReturnMetadata(models.Model):
    _name = 'ab_sales_return_header'
    _inherit = ['ab_sales_return_header', 'ab_branch_sale_metadata']


class SourcePromotion(models.Model):
    _inherit = 'ab_sales_header'

    def _promotion_eligibility_replica(self, program):
        self.ensure_one()
        self.check_access('read')
        # Fresh POS previews have no persisted, authenticated origin.
        # Existing-invoice onchange previews resolve their original header.
        if not self._origin:
            return super()._promotion_eligibility_replica(program)
        self._origin.check_access('read')
        metadata = self._origin.sudo().metadata or {}
        if (metadata.get('source_db_serial') and metadata.get('source_user_id')
                and metadata.get('source_promotion_id') == (program._origin or program).id):
            return self.env['ab_replica_db'].sudo().search(
                fields.Domain('db_serial', '=', metadata['source_db_serial']), limit=1)
        return super()._promotion_eligibility_replica(program)
