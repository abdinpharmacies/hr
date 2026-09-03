import json
import logging
import secrets
import threading
import urllib.error
import urllib.request

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.modules.registry import Registry
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)
_DELIVERY_SENDER_LOCK = threading.Lock()
_DELIVERY_SENDER_RUNNING = False


class AbDeliveryRequest(models.Model):
    _name = "ab_delivery_request"
    _description = "Delivery Request"
    _order = "id desc"
    _rec_name = "name"

    active = fields.Boolean(default=True, string="Active")
    name = fields.Char(compute="_compute_name", store=True, string="Name")
    sale_header_id = fields.Many2one(
        "ab_sales_header",
        required=True,
        readonly=True,
        index=True,
        copy=False,
        ondelete="restrict",
        string="Bill",
    )
    store_id = fields.Many2one("ab_store", readonly=True, index=True, string="Branch")
    branch_code = fields.Char(readonly=True, index=True, string="Branch Code")
    branch_name = fields.Char(readonly=True, string="Branch Name")
    bill_number = fields.Char(readonly=True, index=True, string="Bill Number")
    customer_name = fields.Char(readonly=True, string="Customer")
    customer_phone = fields.Char(readonly=True, string="Phone")
    customer_address = fields.Char(readonly=True, string="Address")
    amount_total = fields.Float(readonly=True, string="Bill Sum")
    telegram_chat_id = fields.Char(readonly=True, string="Telegram Chat ID")
    telegram_message_id = fields.Char(readonly=True, copy=False, string="Telegram Message ID")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        string="Status",
    )
    sent_date = fields.Datetime(readonly=True, copy=False, string="Sent Date")
    next_attempt_date = fields.Datetime(readonly=True, copy=False, string="Next Attempt Date")
    failure_count = fields.Integer(default=0, readonly=True, copy=False, string="Failure Count")
    last_error = fields.Text(readonly=True, copy=False, string="Last Error")

    _unique_sale_header = models.Constraint(
        "UNIQUE(sale_header_id)",
        "A delivery request already exists for this bill.",
    )

    @api.depends("branch_name", "bill_number", "sale_header_id")
    def _compute_name(self):
        for request in self:
            bill_number = request.bill_number or str(request.sale_header_id.id or "")
            request.name = "%s - %s" % (
                request.branch_name or _("Delivery Request"),
                bill_number,
            )

    @api.model
    def create_from_sale_header(self, header):
        header = header.sudo().exists()
        if not header:
            return self.browse()
        header.ensure_one()

        request = self.sudo().search([("sale_header_id", "=", header.id)], limit=1)
        vals = self._delivery_request_vals_from_sale_header(header)
        if request:
            request.write(vals)
            return request
        return self.sudo().create(vals)

    @api.model
    def _delivery_request_vals_from_sale_header(self, header):
        header.ensure_one()
        snapshot = header._get_bill_customer_snapshot_vals()
        return {
            "sale_header_id": header.id,
            "store_id": header.store_id.id if header.store_id else False,
            "branch_code": (header.store_id.code or "").strip() if header.store_id else "",
            "branch_name": header.store_id.display_name if header.store_id else "",
            "bill_number": str(header.eplus_serial or header.id or ""),
            "customer_name": snapshot.get("bill_customer_name") or "",
            "customer_phone": snapshot.get("bill_customer_phone") or "",
            "customer_address": snapshot.get("bill_customer_address") or "",
            "amount_total": float(header.total_net_amount or header.total_price or 0.0),
            "telegram_chat_id": self._get_telegram_chat_id(),
        }

    def action_resend_to_telegram(self):
        for request in self.sudo().exists():
            try:
                request.write({
                    "state": "queued",
                    "last_error": False,
                    "next_attempt_date": False,
                })
                request.job_send_to_telegram(force=True)
            except RetryableJobError as ex:
                raise UserError(_("Telegram send failed: %s") % str(ex)) from ex
        return True

    def queue_send_to_telegram(self, force=False):
        requests_to_send = self.browse()
        for request in self.sudo().exists():
            if not force and request.state == "sent" and request.telegram_message_id:
                continue
            try:
                request.write({
                    "state": "queued",
                    "last_error": False,
                    "next_attempt_date": False,
                })
                request.with_delay(
                    identity_key=request._send_identity_key(),
                    description=_("Send delivery request to Telegram"),
                ).job_send_to_telegram(force=force)
                requests_to_send |= request
            except Exception as ex:
                request._mark_failed(ex)
                raise
        if requests_to_send:
            requests_to_send._send_to_telegram_now_safely(force=force)
            self._schedule_background_sender_after_commit()
        return True

    def job_send_to_telegram(self, force=False):
        self.ensure_one()
        if not force and self.state == "sent" and self.telegram_message_id:
            return {"status": "skipped", "reason": self.state}
        self._refresh_from_sale_header()
        chat_id = self._get_telegram_chat_id() or self.telegram_chat_id
        try:
            response = self._telegram_api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": self._telegram_message_text(),
                    "reply_markup": {
                        "inline_keyboard": [[{
                            "text": "تم الاستلام",
                            "callback_data": self._telegram_callback_data(),
                        }]],
                    },
                },
            )
            message = response.get("result") or {}
            self.write({
                "state": "sent",
                "telegram_message_id": str(message.get("message_id") or ""),
                "telegram_chat_id": str((message.get("chat") or {}).get("id") or chat_id or ""),
                "sent_date": fields.Datetime.now(),
                "next_attempt_date": False,
                "last_error": False,
            })
            return {"status": "sent", "message_id": self.telegram_message_id}
        except Exception as ex:
            self._mark_failed(ex)
            raise RetryableJobError(str(ex), seconds=60) from ex

    def _send_to_telegram_now_safely(self, force=False):
        for request in self.sudo().exists():
            try:
                request.job_send_to_telegram(force=force)
            except RetryableJobError:
                _logger.info("Delivery request %s send will retry later", request.id)
            except Exception:
                _logger.exception("Unexpected delivery request send failure for %s", request.id)
        return True

    def _refresh_from_sale_header(self):
        for request in self.sudo().exists():
            if not request.sale_header_id:
                continue
            request.write(
                request._delivery_request_vals_from_sale_header(request.sale_header_id.sudo())
            )
        return True

    @api.model
    def cron_send_pending_telegram_requests(self, limit=20):
        now = fields.Datetime.now()
        requests = self.sudo().search(
            [
                ("state", "in", ["pending", "queued", "failed"]),
                "|",
                ("next_attempt_date", "=", False),
                ("next_attempt_date", "<=", now),
            ],
            order="id",
            limit=limit,
        )
        return requests._send_to_telegram_now_safely()

    def _schedule_background_sender_after_commit(self):
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(
            lambda dbname=dbname: AbDeliveryRequest._start_background_sender(dbname)
        )

    @staticmethod
    def _start_background_sender(dbname):
        global _DELIVERY_SENDER_RUNNING
        with _DELIVERY_SENDER_LOCK:
            if _DELIVERY_SENDER_RUNNING:
                return
            _DELIVERY_SENDER_RUNNING = True
        worker = threading.Thread(
            target=AbDeliveryRequest._run_background_sender,
            args=(dbname,),
            daemon=True,
        )
        worker.start()

    @staticmethod
    def _run_background_sender(dbname):
        global _DELIVERY_SENDER_RUNNING
        try:
            registry = Registry(dbname)
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env["ab_delivery_request"].sudo().cron_send_pending_telegram_requests()
                cr.commit()
        except Exception:
            _logger.exception("Background delivery Telegram sender failed.")
        finally:
            with _DELIVERY_SENDER_LOCK:
                _DELIVERY_SENDER_RUNNING = False

    def _telegram_message_text(self):
        self.ensure_one()
        return "\n".join([
            "طلب توصيل جديد",
            "الفرع: %s" % self._message_value(self.branch_name),
            "رقم الفاتورة: %s" % self._message_value(self.bill_number),
            "العميل: %s" % self._message_value(self.customer_name),
            "الهاتف: %s" % self._message_value(self.customer_phone),
            "العنوان: %s" % self._message_value(self.customer_address),
            "الإجمالي: %.2f" % float(self.amount_total or 0.0),
        ])

    @api.model
    def _message_value(self, value):
        value = (value or "").strip()
        return value or "-"

    def _telegram_callback_data(self):
        self.ensure_one()
        if not self.branch_code:
            raise ValueError("Branch store code is not configured.")
        if ":" in self.branch_code:
            raise ValueError("Branch store code cannot contain ':'.")
        reference = self.bill_number or str(self.sale_header_id.id or "")
        if ":" in reference:
            raise ValueError("Delivery callback reference cannot contain ':'.")
        callback_data = "dr:%s:%s:%s" % (self.branch_code, reference, secrets.token_urlsafe(8))
        if len(callback_data.encode("utf-8")) > 64:
            raise ValueError("Telegram callback data is too long. Check the branch store code or bill number.")
        return callback_data

    def _send_identity_key(self):
        self.ensure_one()
        return "ab_delivery_request:send:%s" % self.id

    @api.model
    def _get_telegram_bot_token(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "ab_sales_delivery_tracking.telegram_bot_token",
            "",
        ).strip()

    @api.model
    def _get_telegram_chat_id(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "ab_sales_delivery_tracking.telegram_chat_id",
            "",
        ).strip()

    @api.model
    def _telegram_api(self, method, payload):
        token = self._get_telegram_bot_token()
        if not token:
            raise ValueError("Telegram bot token is not configured.")
        url = "https://api.telegram.org/bot%s/%s" % (token, method)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", errors="replace")
            raise ValueError("Telegram API error: %s" % body) from ex
        result = json.loads(body)
        if not result.get("ok"):
            raise ValueError("Telegram API error: %s" % result)
        return result

    def _mark_failed(self, error):
        self.ensure_one()
        failure_count = int(self.failure_count or 0) + 1
        self.write({
            "state": "failed",
            "failure_count": failure_count,
            "next_attempt_date": fields.Datetime.add(
                fields.Datetime.now(),
                seconds=self._retry_delay_seconds(failure_count),
            ),
            "last_error": str(error),
        })

    @api.model
    def _retry_delay_seconds(self, failure_count):
        if failure_count <= 1:
            return 60
        if failure_count == 2:
            return 300
        if failure_count == 3:
            return 900
        return 3600
