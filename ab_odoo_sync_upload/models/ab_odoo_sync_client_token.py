from datetime import timedelta

from odoo import api, fields, models, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.addons.queue_job.exception import RetryableJobError


class AbOdooSyncClientToken(models.Model):
    _name = "ab_odoo_sync_client_token"
    _description = "Branch Sync Client Token"
    _log_access = False

    fingerprint = fields.Char(required=True, index=True, groups="base.group_system")
    token = fields.Char(required=True, groups="base.group_system")
    expires_at = fields.Datetime(required=True, index=True)

    _unique_fingerprint = models.Constraint("UNIQUE(fingerprint)", "Connection fingerprint must be unique.")

    @api.model
    def _get_token(self, fingerprint, fetch, rejected_token=None):
        # An isolated, short transaction makes refresh visible to all senders even
        # when their outbox transaction subsequently retries. No business data here.
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {"lang": self.env.lang})
            cr.execute("SELECT pg_try_advisory_xact_lock(193733, 2)")
            if not cr.fetchone()[0]:
                raise RetryableJobError(_("Sync token refresh is busy"), seconds=5, ignore_retry=True)
            cache = env[self._name].search([("fingerprint", "=", fingerprint)], limit=1)
            if cache and cache.token != rejected_token and cache.expires_at > fields.Datetime.now() + timedelta(seconds=30):
                return cache.token
            response = fetch()
            token = response.get("access_token")
            ttl = response.get("expires_in")
            if not isinstance(token, str) or len(token) != 43 or not token.isascii() or not isinstance(ttl, int) or not 60 <= ttl <= 3600:
                raise ValueError(_("Invalid sync token response"))
            values = {"fingerprint": fingerprint, "token": token,
                      "expires_at": fields.Datetime.now() + timedelta(seconds=ttl)}
            if cache:
                cache.write(values)
            else:
                env[self._name].create(values)
            cr.commit()
            return token

    @api.autovacuum
    def _gc_expired_tokens(self):
        self.sudo().search([("expires_at", "<", fields.Datetime.now())], limit=1000).unlink()
