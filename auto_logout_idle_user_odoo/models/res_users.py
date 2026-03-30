# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo import http


class Users(models.Model):
    """ Inherit and adding some fields to the 'res.users'"""
    _inherit = "res.users"

    enable_idle = fields.Boolean(
        default=True,
        string="Enable Idle Time",
        help="Enable Idle Timer")
    idle_time = fields.Integer(string="Idle Time (In minutes)",
                               default=10,
                               help="Set Idle Time For theis User")

    @api.model
    def auth_timeout_session_terminate(self):
        session = http.request.session

        """Pluggable method for terminating a timed-out session

        This is a late stage where a session timeout can be aborted.
        Useful if you want to do some heavy checking, as it won't be
        called unless the session inactivity deadline has been reached.

        Return:
            True: session terminated
            False: session timeout cancelled
        """
        if session.db and session.uid:
            session.logout(keep_db=True)
        return True
