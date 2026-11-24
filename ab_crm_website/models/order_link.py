from ipaddress import ip_address
from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    website_backend_url = fields.Char(string='Website Odoo base URL')

    def _check_backend_url_editor(self):
        if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_crm_core.group_manager')):
            raise AccessError(_('Only CRM managers can configure website order links.'))

    @api.model_create_multi
    def create(self, values_list):
        if any('website_backend_url' in values for values in values_list):
            self._check_backend_url_editor()
        return super().create(values_list)

    def write(self, values):
        if 'website_backend_url' in values:
            self._check_backend_url_editor()
        return super().write(values)

    @api.constrains('website_backend_url', 'provider')
    def _check_website_backend_url(self):
        for record in self:
            value = record.website_backend_url
            if not value:
                continue
            try:
                url = urlsplit(value)
                host = url.hostname
                local = host == 'localhost'
                try:
                    local = local or ip_address(host).is_loopback
                except ValueError:
                    pass
                valid = (record.provider == 'website' and value == value.strip()
                    and not any(character.isspace() for character in value)
                    and not any(character in value for character in ('\\', '?', '#'))
                    and url.scheme in ('https', 'http') and host and url.port != 0
                    and url.username is None and url.password is None and not url.query and not url.fragment
                    and url.path in ('', '/') and (url.scheme == 'https' or local))
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise ValidationError(_('Enter a valid HTTPS website origin; HTTP is allowed only for local development.'))


class Order(models.Model):
    _inherit = 'ab_crm_website_order'

    def _backend_order_url(self):
        self.ensure_one()
        self._authorize('read')
        origin = self.account_id.website_backend_url
        if not origin or not self.order_uuid or not self.account_id.provider_account:
            return False
        return (origin.rstrip('/') + '/odoo/storefront-callcenter/backend-order/'
                + self.account_id.provider_account + '/' + self.order_uuid)
