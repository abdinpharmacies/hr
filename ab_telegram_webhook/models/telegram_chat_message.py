import uuid

from odoo import api, fields, models


class AbTelegramChatMessage(models.Model):
    _name = "ab_telegram_chat_message"
    _description = "Telegram OpenAI Chat Session"
    _order = "last_message_datetime desc, id desc"

    # Kept to remain compatible with existing table constraints/data.
    direction = fields.Selection(
        [("in", "User Message"), ("out", "Bot Response")],
        required=True,
        default="in",
        index=True,
    )
    echo_status = fields.Selection(
        [("received", "Received"), ("echoed", "Echoed"), ("skipped", "Skipped"), ("failed", "Failed")],
        required=True,
        default="echoed",
        index=True,
    )
    processing_note = fields.Char()
    error_message = fields.Text()
    telegram_update_id = fields.Char(index=True)
    telegram_message_id = fields.Char(index=True)
    chat_type = fields.Selection(
        [
            ("private", "Private"),
            ("group", "Group"),
            ("supergroup", "Supergroup"),
            ("channel", "Channel"),
            ("unknown", "Unknown"),
        ],
        required=True,
        default="private",
        index=True,
    )
    content_type = fields.Char(required=True, default="text")
    content_text = fields.Text()
    message_datetime = fields.Datetime(required=True, index=True, default=fields.Datetime.now)

    telegram_chat_id = fields.Char(required=True, index=True)
    telegram_user_id = fields.Char(required=True, index=True)
    username = fields.Char()
    first_name = fields.Char()
    last_name = fields.Char()
    phone = fields.Char()
    language_code = fields.Char()
    full_name = fields.Char(compute="_compute_full_name", store=True)

    linked_user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    session_uuid = fields.Char(required=True, index=True, copy=False, default=lambda self: str(uuid.uuid4()))
    session_status = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        required=True,
        default="open",
        index=True,
    )
    close_reason = fields.Char()
    token_limit = fields.Integer(default=1000)
    token_count = fields.Integer(default=0)
    openai_messages_json = fields.Json(
        required=True,
        default=lambda self: {"messages": []},
        groups="base.group_system",
        help="OpenAI conversation history as role/content pairs.",
    )
    started_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    last_message_datetime = fields.Datetime(required=True, default=fields.Datetime.now, index=True)

    @api.depends("first_name", "last_name", "username", "telegram_user_id")
    def _compute_full_name(self):
        for rec in self:
            name = " ".join(part for part in (rec.first_name, rec.last_name) if part)
            if not name and rec.username:
                name = f"@{rec.username}"
            rec.full_name = name or rec.telegram_user_id or "-"
