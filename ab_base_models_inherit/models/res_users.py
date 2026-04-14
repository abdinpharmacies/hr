from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools import config

import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_encrypted_password(self, user_id=0, xmlrpc_pass=""):
        _logger.info('get_encrypted_password: starting  ...............')
        if xmlrpc_pass != config.get('xmlrpc_pass', ""):
            _logger.info('get_encrypted_password: failed xmlrpc_pass  ...............')
            return ""

        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s and password is not null", (user_id,))
        record = self.env.cr.fetchone()
        password = record[0] if record else ""
        _logger.info(f'get_encrypted_password: ended  ...............')

        return password
