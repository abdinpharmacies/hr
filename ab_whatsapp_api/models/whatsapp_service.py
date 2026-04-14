import base64
import binascii
import re
from typing import Any

import requests

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config
from odoo.tools.translate import _


class AbWhatsAppService(models.Model):
    _name = "ab.whatsapp.service"
    _description = "AB WhatsApp Service"

    _TEMPLATE_PLACEHOLDER_REGEX = re.compile(r"\{\{\d+\}\}")
    _STATUS_RANK = {
        "": 0,
        "failed": 1,
        "sent": 1,
        "delivered": 2,
        "read": 3,
    }

    @api.model
    def _ensure_system_access(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only system administrators can access WhatsApp API."))

    @api.model
    def _config_value(self, key: str, default: str = "") -> str:
        return (config.get(key, default) or "").strip()

    @api.model
    def _settings(self) -> dict[str, str]:
        return {
            "token": self._config_value("whatsapp_token"),
            "default_phone_number_id": self._config_value("whatsapp_phone_number_id"),
            "verify_token": self._config_value(
                "whatsapp_verify_token",
                "local-dev-verify-token",
            ),
            "waba_id": self._config_value("whatsapp_business_account_id"),
            "api_version": self._config_value("whatsapp_api_version", "v22.0"),
        }

    @api.model
    def _require_token(self) -> str:
        token = self._settings()["token"]
        if not token:
            raise UserError(
                _(
                    "Missing whatsapp_token in Odoo config. "
                    "Set it in odoo.conf and restart Odoo."
                )
            )
        return token

    @api.model
    def _normalize_wa_id(self, value: str | None) -> str:
        return "".join(ch for ch in (value or "") if ch.isdigit())

    @api.model
    def _validate_phone_number_id(
        self,
        phone_number_id: str,
        recipient_wa_id: str | None = None,
    ) -> str:
        normalized = "".join(ch for ch in (phone_number_id or "") if ch.isdigit())
        if not normalized:
            raise UserError(_("Phone Number ID must contain digits only."))
        if recipient_wa_id and normalized == self._normalize_wa_id(recipient_wa_id):
            raise UserError(
                _(
                    "Phone Number ID is incorrect. Use Meta Phone Number ID "
                    "(sender object id), not recipient number."
                )
            )
        return normalized

    @api.model
    def _graph_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @api.model
    def _extract_graph_error(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            payload = {"error": {"message": response.text}}
        message = (payload.get("error") or {}).get("message") or "Unknown Meta API error"
        return f"HTTP {response.status_code}: {message}"

    @api.model
    def _post_graph_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = requests.post(
                url,
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise UserError(_("Network error while calling Meta API: %s") % exc) from exc

        if not response.ok:
            raise UserError(self._extract_graph_error(response))
        return response.json()

    @api.model
    def _get_graph_json(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise UserError(_("Network error while calling Meta API: %s") % exc) from exc

        if not response.ok:
            raise UserError(self._extract_graph_error(response))
        return response.json()

    @api.model
    def _upload_graph_media(
        self,
        url: str,
        headers: dict[str, str],
        filename: str,
        content_type: str,
        binary_data: bytes,
    ) -> dict[str, Any]:
        files = {"file": (filename, binary_data, content_type)}
        data = {"messaging_product": "whatsapp"}
        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise UserError(_("Network error while uploading media: %s") % exc) from exc

        if not response.ok:
            raise UserError(self._extract_graph_error(response))
        return response.json()

    @api.model
    def _extract_filename_from_disposition(self, disposition_value: str | None) -> str:
        value = (disposition_value or "").strip()
        if not value:
            return ""
        match = re.search(r"filename\\*=UTF-8''([^;]+)", value, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('"')
        match = re.search(r'filename="?([^";]+)"?', value, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    @api.model
    def _download_graph_media(
        self,
        media_id: str,
    ) -> tuple[bytes, str, str]:
        normalized_media_id = (media_id or "").strip()
        if not normalized_media_id:
            raise UserError(_("Media id is required."))

        settings = self._settings()
        token = self._require_token()
        headers = self._graph_headers(token)
        meta_url = f"https://graph.facebook.com/{settings['api_version']}/{normalized_media_id}"
        meta_payload = self._get_graph_json(meta_url, headers)
        download_url = (meta_payload.get("url") or "").strip()
        if not download_url:
            raise UserError(_("Unable to resolve media URL from Meta API."))

        try:
            response = requests.get(
                download_url,
                headers=headers,
                timeout=60,
            )
        except requests.RequestException as exc:
            raise UserError(_("Network error while downloading media: %s") % exc) from exc

        if not response.ok:
            raise UserError(self._extract_graph_error(response))

        mime_type = (
            (response.headers.get("Content-Type") or "").split(";")[0].strip()
            or (meta_payload.get("mime_type") or "").strip()
            or "application/octet-stream"
        )
        filename = (
            (meta_payload.get("filename") or "").strip()
            or self._extract_filename_from_disposition(response.headers.get("Content-Disposition"))
            or f"media_{normalized_media_id}"
        )
        return response.content, mime_type, filename

    @api.model
    def _infer_message_type(self, content_type: str | None) -> str:
        normalized = (content_type or "").lower()
        if normalized.startswith("image/"):
            return "image"
        if normalized.startswith("video/"):
            return "video"
        if normalized.startswith("audio/"):
            return "audio"
        return "document"

    @api.model
    def _status_rank(self, status: str | None) -> int:
        normalized = (status or "").strip().lower()
        return self._STATUS_RANK.get(normalized, 0)

    @api.model
    def _merge_status(self, current_status: str | None, incoming_status: str | None) -> str | None:
        incoming = (incoming_status or "").strip().lower()
        current = (current_status or "").strip().lower()

        if not incoming:
            return current_status
        if incoming == "failed":
            if current in {"", "sent", "failed"}:
                return "failed"
            return current_status
        if self._status_rank(incoming) >= self._status_rank(current):
            return incoming
        return current_status

    @api.model
    def _preview_for_message(self, message_type: str, text_content: str | None) -> str:
        if message_type == "reaction":
            emoji = (text_content or "").strip()
            return f"[reaction] {emoji}" if emoji else "[reaction]"
        if message_type == "deleted":
            return "[deleted]"
        if text_content:
            return text_content[:120]
        return f"[{message_type}]"

    @api.model
    def _template_body_preview(self, components: list[dict[str, Any]] | None) -> str:
        for component in components or []:
            if (component.get("type") or "").upper() != "BODY":
                continue
            text = (component.get("text") or "").strip()
            if text:
                return text
        return ""

    @api.model
    def _template_has_placeholders(self, components: list[dict[str, Any]] | None) -> bool:
        for component in components or []:
            text = component.get("text")
            if isinstance(text, str) and self._TEMPLATE_PLACEHOLDER_REGEX.search(text):
                return True
            example = component.get("example")
            if isinstance(example, dict):
                for value in example.values():
                    if isinstance(value, str) and self._TEMPLATE_PLACEHOLDER_REGEX.search(value):
                        return True
                    if isinstance(value, list):
                        for row in value:
                            if isinstance(row, str) and self._TEMPLATE_PLACEHOLDER_REGEX.search(row):
                                return True
                            if isinstance(row, list):
                                for item in row:
                                    if isinstance(item, str) and self._TEMPLATE_PLACEHOLDER_REGEX.search(item):
                                        return True
        return False

    @api.model
    def _serialize_template(self, template) -> dict[str, Any]:
        placeholder_indexes = self._template_required_placeholder_indexes(template)
        return {
            "id": template.id,
            "template_uid": template.template_uid,
            "name": template.name,
            "language": template.language,
            "status": template.status,
            "category": template.category,
            "quality_score": template.quality_score,
            "body_preview": template.body_preview,
            "has_placeholders": bool(placeholder_indexes),
            "placeholder_indexes": placeholder_indexes,
            "placeholder_count": len(placeholder_indexes),
            "is_sendable": (template.status or "").upper() == "APPROVED",
            "last_synced_at": fields.Datetime.to_string(template.last_synced_at)
            if template.last_synced_at
            else "",
        }

    @api.model
    def _normalize_template_name(self, value: str | None) -> str:
        normalized = re.sub(r"[^a-z0-9_]+", "_", (value or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    @api.model
    def _template_placeholder_indexes(self, body_text: str) -> list[int]:
        indexes = {int(item) for item in re.findall(r"\{\{(\d+)\}\}", body_text or "")}
        return sorted(indexes)

    @api.model
    def _template_required_placeholder_indexes(self, template) -> list[int]:
        components = template.components_payload
        if isinstance(components, list):
            for component in components:
                if (component.get("type") or "").upper() != "BODY":
                    continue
                text = component.get("text")
                if isinstance(text, str):
                    indexes = self._template_placeholder_indexes(text)
                    if indexes:
                        return indexes
        return self._template_placeholder_indexes(template.body_preview or "")

    @api.model
    def _touch_contact_message_meta(self, contact, preview: str, at_datetime):
        contact.sudo().write(
            {
                "last_message_at": at_datetime,
                "last_message_preview": preview,
            }
        )

    @api.model
    def _find_or_create_contact(
        self,
        wa_id: str,
        name: str | None = None,
        preferred_phone_number_id: str | None = None,
    ):
        Contact = self.env["ab.whatsapp.contact"].sudo()
        contact = Contact.search([("wa_id", "=", wa_id)], limit=1)

        vals: dict[str, Any] = {}
        clean_name = (name or "").strip()
        clean_phone_number_id = (preferred_phone_number_id or "").strip()

        if clean_name:
            vals["name"] = clean_name
        if clean_phone_number_id:
            vals["preferred_phone_number_id"] = clean_phone_number_id

        if contact:
            if vals:
                contact.write(vals)
            return contact

        return Contact.create(
            {
                "wa_id": wa_id,
                **vals,
            }
        )

    @api.model
    def _serialize_message(self, message) -> dict[str, Any]:
        return {
            "id": message.id,
            "direction": message.direction,
            "wa_id": message.wa_id,
            "phone_number_id": message.phone_number_id,
            "message_type": message.message_type,
            "text_content": message.text_content,
            "media_id": message.media_id,
            "media_mime_type": message.media_mime_type,
            "media_filename": message.media_filename,
            "status": message.status,
            "meta_message_id": message.meta_message_id,
            "reply_to_meta_message_id": message.reply_to_meta_message_id,
            "reaction_target_meta_message_id": message.reaction_target_meta_message_id,
            "is_deleted": bool(message.is_deleted),
            "edited_from_text": message.edited_from_text,
            "edited_at": fields.Datetime.to_string(message.edited_at) if message.edited_at else "",
            "created_at": fields.Datetime.to_string(message.create_date) if message.create_date else "",
        }

    @api.model
    def _serialize_contact(self, contact, latest_message=None) -> dict[str, Any]:
        message = latest_message
        if message is None:
            message = self.env["ab.whatsapp.message"].sudo().search(
                [("contact_id", "=", contact.id)],
                order="id desc",
                limit=1,
            )

        return {
            "id": contact.id,
            "wa_id": contact.wa_id,
            "name": contact.name,
            "preferred_phone_number_id": contact.preferred_phone_number_id,
            "created_at": fields.Datetime.to_string(contact.create_date) if contact.create_date else "",
            "updated_at": fields.Datetime.to_string(contact.write_date) if contact.write_date else "",
            "last_text_content": message.text_content if message else "",
            "last_message_type": message.message_type if message else "",
            "last_direction": message.direction if message else "",
            "last_message_at": fields.Datetime.to_string(message.create_date) if message and message.create_date else "",
        }

    @api.model
    def _create_message(
        self,
        direction: str,
        wa_id: str,
        message_type: str,
        phone_number_id: str | None = None,
        text_content: str | None = None,
        media_id: str | None = None,
        media_mime_type: str | None = None,
        media_filename: str | None = None,
        status: str | None = None,
        meta_message_id: str | None = None,
        reply_to_meta_message_id: str | None = None,
        reaction_target_meta_message_id: str | None = None,
        is_deleted: bool = False,
        edited_from_text: str | None = None,
        edited_at=None,
        raw_payload: dict[str, Any] | list[Any] | None = None,
        contact_name: str | None = None,
    ):
        normalized_wa_id = self._normalize_wa_id(wa_id)
        if not normalized_wa_id:
            raise UserError(_("Contact WhatsApp number is missing."))

        normalized_phone_number_id = (phone_number_id or "").strip() or None
        contact = self._find_or_create_contact(
            wa_id=normalized_wa_id,
            name=contact_name,
            preferred_phone_number_id=normalized_phone_number_id,
        )

        message = self.env["ab.whatsapp.message"].sudo().create(
            {
                "direction": direction,
                "contact_id": contact.id,
                "phone_number_id": normalized_phone_number_id,
                "message_type": message_type or "text",
                "text_content": text_content,
                "media_id": media_id,
                "media_mime_type": (media_mime_type or "").strip() or None,
                "media_filename": (media_filename or "").strip() or None,
                "status": (status or "").strip().lower() or None,
                "meta_message_id": (meta_message_id or "").strip() or None,
                "reply_to_meta_message_id": (reply_to_meta_message_id or "").strip() or None,
                "reaction_target_meta_message_id": (reaction_target_meta_message_id or "").strip() or None,
                "is_deleted": bool(is_deleted),
                "edited_from_text": edited_from_text,
                "edited_at": edited_at,
                "raw_payload": raw_payload or {},
            }
        )

        preview = self._preview_for_message(message.message_type, message.text_content)
        self._touch_contact_message_meta(contact, preview, message.create_date)
        return message

    @api.model
    def _get_phone_number_id_from_waba(self, token: str, api_version: str, waba_id: str) -> str:
        if not waba_id:
            return ""
        url = f"https://graph.facebook.com/{api_version}/{waba_id}/phone_numbers"
        payload = self._get_graph_json(
            url=url,
            headers=self._graph_headers(token),
            params={"fields": "id,display_phone_number,verified_name"},
        )
        for item in payload.get("data", []):
            candidate = self._validate_phone_number_id(item.get("id") or "")
            if candidate:
                return candidate
        return ""

    @api.model
    def _resolve_sender_phone_number_id(
        self,
        to_wa_id: str,
        requested_phone_number_id: str | None = None,
    ) -> str:
        normalized_to = self._normalize_wa_id(to_wa_id)
        if not normalized_to:
            raise UserError(_("Recipient number is required."))

        explicit = (requested_phone_number_id or "").strip()
        if explicit:
            valid = self._validate_phone_number_id(explicit, normalized_to)
            self._find_or_create_contact(
                wa_id=normalized_to,
                preferred_phone_number_id=valid,
            )
            return valid

        Contact = self.env["ab.whatsapp.contact"].sudo()
        contact = Contact.search([("wa_id", "=", normalized_to)], limit=1)
        if contact and contact.preferred_phone_number_id:
            return self._validate_phone_number_id(contact.preferred_phone_number_id, normalized_to)

        Message = self.env["ab.whatsapp.message"].sudo()
        last_message = Message.search(
            [
                ("direction", "=", "outgoing"),
                ("wa_id", "=", normalized_to),
                ("phone_number_id", "!=", False),
            ],
            order="id desc",
            limit=1,
        )
        if last_message and last_message.phone_number_id:
            resolved = self._validate_phone_number_id(last_message.phone_number_id, normalized_to)
            self._find_or_create_contact(
                wa_id=normalized_to,
                preferred_phone_number_id=resolved,
            )
            return resolved

        settings = self._settings()
        if settings["default_phone_number_id"]:
            resolved = self._validate_phone_number_id(settings["default_phone_number_id"], normalized_to)
            self._find_or_create_contact(
                wa_id=normalized_to,
                preferred_phone_number_id=resolved,
            )
            return resolved

        token = self._require_token()
        resolved = self._get_phone_number_id_from_waba(
            token=token,
            api_version=settings["api_version"],
            waba_id=settings["waba_id"],
        )
        if resolved:
            self._find_or_create_contact(
                wa_id=normalized_to,
                preferred_phone_number_id=resolved,
            )
            return resolved

        raise UserError(
            _(
                "Unable to resolve sender phone number ID. Set whatsapp_phone_number_id "
                "or whatsapp_business_account_id in Odoo config."
            )
        )

    @api.model
    def _update_outgoing_message_status(
        self,
        meta_message_id: str,
        status: str | None,
        recipient_wa_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_meta_id = (meta_message_id or "").strip()
        if not normalized_meta_id:
            return []

        Message = self.env["ab.whatsapp.message"].sudo()
        messages = Message.search(
            [
                ("direction", "=", "outgoing"),
                ("meta_message_id", "=", normalized_meta_id),
            ],
            order="id desc",
        )

        if not messages and recipient_wa_id:
            normalized_wa_id = self._normalize_wa_id(recipient_wa_id)
            if normalized_wa_id:
                messages = Message.search(
                    [
                        ("direction", "=", "outgoing"),
                        ("wa_id", "=", normalized_wa_id),
                        ("meta_message_id", "=", normalized_meta_id),
                    ],
                    order="id desc",
                )

        normalized_phone_number_id = (phone_number_id or "").strip()
        output: list[dict[str, Any]] = []
        for message in messages:
            merged_status = self._merge_status(message.status, status)
            vals: dict[str, Any] = {}
            if merged_status != message.status:
                vals["status"] = merged_status
            if normalized_phone_number_id and not message.phone_number_id:
                vals["phone_number_id"] = normalized_phone_number_id
            if vals:
                message.write(vals)
            output.append(self._serialize_message(message))
        return output

    @api.model
    def api_health(self) -> dict[str, Any]:
        self._ensure_system_access()
        settings = self._settings()
        return {
            "status": "ok",
            "token_configured": bool(settings["token"]),
            "verify_token": settings["verify_token"],
        }

    @api.model
    def api_list_contacts(self, limit: int = 300) -> list[dict[str, Any]]:
        self._ensure_system_access()
        safe_limit = max(1, min(int(limit or 300), 1000))
        Contact = self.env["ab.whatsapp.contact"].sudo()
        Message = self.env["ab.whatsapp.message"].sudo()

        contacts = Contact.search([], order="last_message_at desc, id desc", limit=safe_limit)
        if not contacts:
            return []

        messages = Message.search(
            [("contact_id", "in", contacts.ids)],
            order="id desc",
        )
        latest_by_contact: dict[int, Any] = {}
        for message in messages:
            if message.contact_id.id not in latest_by_contact:
                latest_by_contact[message.contact_id.id] = message

        return [self._serialize_contact(contact, latest_by_contact.get(contact.id)) for contact in contacts]

    @api.model
    def api_list_conversation(self, wa_id: str, limit: int = 300) -> list[dict[str, Any]]:
        self._ensure_system_access()
        normalized_wa_id = self._normalize_wa_id(wa_id)
        if not normalized_wa_id:
            return []

        safe_limit = max(1, min(int(limit or 300), 1000))
        contact = self.env["ab.whatsapp.contact"].sudo().search(
            [("wa_id", "=", normalized_wa_id)],
            limit=1,
        )
        if not contact:
            return []

        messages = self.env["ab.whatsapp.message"].sudo().search(
            [("contact_id", "=", contact.id)],
            order="id desc",
            limit=safe_limit,
        )
        return [self._serialize_message(message) for message in reversed(messages)]

    @api.model
    def api_mark_incoming_read(self, wa_id: str, limit: int = 100) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_wa_id = self._normalize_wa_id(wa_id)
        if not normalized_wa_id:
            return {"ok": False, "reason": "invalid_wa_id", "attempted": 0, "updated": 0, "failed": 0}

        contact = self.env["ab.whatsapp.contact"].sudo().search(
            [("wa_id", "=", normalized_wa_id)],
            limit=1,
        )
        if not contact:
            return {"ok": True, "attempted": 0, "updated": 0, "failed": 0}

        safe_limit = max(1, min(int(limit or 100), 300))
        Message = self.env["ab.whatsapp.message"].sudo()
        messages = Message.search(
            [
                ("contact_id", "=", contact.id),
                ("direction", "=", "incoming"),
                ("meta_message_id", "!=", False),
                ("status", "!=", "read"),
            ],
            order="id asc",
            limit=safe_limit,
        )
        if not messages:
            return {"ok": True, "attempted": 0, "updated": 0, "failed": 0}

        settings = self._settings()
        token = settings["token"]
        if not token:
            return {
                "ok": False,
                "reason": "missing_token",
                "attempted": 0,
                "updated": 0,
                "failed": len(messages),
            }

        headers = self._graph_headers(token)
        default_phone_number_id = (settings["default_phone_number_id"] or "").strip()
        attempted = 0
        updated = 0
        failed = 0

        for message in messages:
            message_meta_id = (message.meta_message_id or "").strip()
            if not message_meta_id:
                continue

            sender_phone_number_id = (message.phone_number_id or "").strip() or default_phone_number_id
            if not sender_phone_number_id:
                failed += 1
                continue

            url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_meta_id,
            }

            attempted += 1
            try:
                self._post_graph_json(url, payload, headers)
            except UserError:
                failed += 1
                continue

            message.write({"status": "read"})
            updated += 1

        return {
            "ok": failed == 0,
            "attempted": attempted,
            "updated": updated,
            "failed": failed,
        }

    @api.model
    def api_upsert_contact(
        self,
        wa_id: str,
        name: str | None = None,
        preferred_phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_wa_id = self._normalize_wa_id(wa_id)
        if not normalized_wa_id:
            raise UserError(_("WhatsApp number is required."))

        resolved_phone_number_id = None
        if preferred_phone_number_id:
            resolved_phone_number_id = self._validate_phone_number_id(preferred_phone_number_id)

        contact = self._find_or_create_contact(
            wa_id=normalized_wa_id,
            name=name,
            preferred_phone_number_id=resolved_phone_number_id,
        )
        return self._serialize_contact(contact)

    @api.model
    def api_delete_contact(self, wa_id: str) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_wa_id = self._normalize_wa_id(wa_id)
        if not normalized_wa_id:
            raise UserError(_("WhatsApp number is required."))

        contact = self.env["ab.whatsapp.contact"].sudo().search(
            [("wa_id", "=", normalized_wa_id)],
            limit=1,
        )
        if not contact:
            raise UserError(_("Contact not found."))

        contact.unlink()
        return {"ok": True, "wa_id": normalized_wa_id}

    @api.model
    def api_list_templates(self) -> list[dict[str, Any]]:
        self._ensure_system_access()
        templates = self.env["ab.whatsapp.template"].sudo().search(
            [],
            order="name asc, language asc, id desc",
        )
        return [self._serialize_template(template) for template in templates]

    @api.model
    def api_sync_templates(self, page_limit: int = 100) -> dict[str, Any]:
        self._ensure_system_access()
        safe_page_limit = max(1, min(int(page_limit or 100), 100))
        settings = self._settings()
        waba_id = (settings["waba_id"] or "").strip()
        if not waba_id:
            raise UserError(
                _(
                    "Missing whatsapp_business_account_id in Odoo config. "
                    "Set it in odoo.conf and restart Odoo."
                )
            )

        token = self._require_token()
        headers = self._graph_headers(token)
        url = f"https://graph.facebook.com/{settings['api_version']}/{waba_id}/message_templates"
        params: dict[str, Any] = {
            "fields": "id,name,language,status,category,quality_score,components",
            "limit": safe_page_limit,
        }

        Template = self.env["ab.whatsapp.template"].sudo()
        now = fields.Datetime.now()
        created_count = 0
        updated_count = 0
        fetched_count = 0

        while True:
            payload = self._get_graph_json(url=url, headers=headers, params=params)
            rows = payload.get("data", []) or []
            fetched_count += len(rows)

            for row in rows:
                template_uid = (row.get("id") or "").strip()
                template_name = (row.get("name") or "").strip()
                if not template_uid or not template_name:
                    continue

                components = row.get("components")
                if not isinstance(components, list):
                    components = []
                quality_score = row.get("quality_score")
                if isinstance(quality_score, dict):
                    quality_score = (quality_score.get("score") or "").strip() or None
                elif isinstance(quality_score, str):
                    quality_score = quality_score.strip() or None
                else:
                    quality_score = None

                vals = {
                    "name": template_name,
                    "language": (row.get("language") or "").strip() or "en_US",
                    "status": (row.get("status") or "").strip() or None,
                    "category": (row.get("category") or "").strip() or None,
                    "quality_score": quality_score,
                    "components_payload": components,
                    "body_preview": self._template_body_preview(components) or None,
                    "has_placeholders": self._template_has_placeholders(components),
                    "raw_payload": row,
                    "last_synced_at": now,
                }

                template = Template.search([("template_uid", "=", template_uid)], limit=1)
                if template:
                    template.write(vals)
                    updated_count += 1
                else:
                    Template.create(
                        {
                            "template_uid": template_uid,
                            **vals,
                        }
                    )
                    created_count += 1

            paging = payload.get("paging") or {}
            next_link = (paging.get("next") or "").strip()
            cursors = paging.get("cursors") or {}
            next_after = (cursors.get("after") or "").strip()
            if not next_link or not next_after:
                break
            params["after"] = next_after

        templates = Template.search([], order="name asc, language asc, id desc")
        return {
            "ok": True,
            "created": created_count,
            "updated": updated_count,
            "fetched": fetched_count,
            "templates": [self._serialize_template(template) for template in templates],
        }

    @api.model
    def api_submit_template(
        self,
        name: str,
        body: str,
        language: str = "en_US",
        category: str = "UTILITY",
    ) -> dict[str, Any]:
        self._ensure_system_access()
        safe_name = self._normalize_template_name(name)
        if not safe_name:
            raise UserError(_("Template name is required."))
        if len(safe_name) > 512:
            raise UserError(_("Template name is too long (max 512 characters)."))

        safe_body = (body or "").strip()
        if not safe_body:
            raise UserError(_("Template body is required."))
        placeholder_indexes = self._template_placeholder_indexes(safe_body)

        safe_language = (language or "").strip() or "en_US"
        safe_category = (category or "UTILITY").strip().upper() or "UTILITY"
        if safe_category not in {"UTILITY", "MARKETING", "AUTHENTICATION"}:
            safe_category = "UTILITY"

        settings = self._settings()
        waba_id = (settings["waba_id"] or "").strip()
        if not waba_id:
            raise UserError(
                _(
                    "Missing whatsapp_business_account_id in Odoo config. "
                    "Set it in odoo.conf and restart Odoo."
                )
            )

        token = self._require_token()
        url = f"https://graph.facebook.com/{settings['api_version']}/{waba_id}/message_templates"
        body_component: dict[str, Any] = {
            "type": "BODY",
            "text": safe_body,
        }
        if placeholder_indexes:
            body_component["example"] = {
                "body_text": [[f"sample_{index}" for index in placeholder_indexes]],
            }
        payload = {
            "name": safe_name,
            "language": safe_language,
            "category": safe_category,
            "components": [body_component],
        }
        response = self._post_graph_json(url, payload, self._graph_headers(token))

        template_uid = (response.get("id") or "").strip()
        response_status = (response.get("status") or "PENDING").strip().upper() or "PENDING"
        now = fields.Datetime.now()
        template = self.env["ab.whatsapp.template"]
        if template_uid:
            Template = self.env["ab.whatsapp.template"].sudo()
            existing = Template.search([("template_uid", "=", template_uid)], limit=1)
            vals = {
                "name": safe_name,
                "language": safe_language,
                "status": response_status,
                "category": safe_category,
                "quality_score": None,
                "components_payload": payload["components"],
                "body_preview": safe_body,
                "has_placeholders": bool(placeholder_indexes),
                "raw_payload": response,
                "last_synced_at": now,
            }
            if existing:
                existing.write(vals)
                template = existing
            else:
                template = Template.create(
                    {
                        "template_uid": template_uid,
                        **vals,
                    }
                )

        return {
            "ok": True,
            "template_uid": template_uid,
            "submitted_name": safe_name,
            "status": response_status,
            "template": self._serialize_template(template) if template else None,
            "response": response,
        }

    @api.model
    def api_send_template(
        self,
        to: str,
        template_id: int,
        contact_name: str | None = None,
        phone_number_id: str | None = None,
        template_params: list[str] | None = None,
    ) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_to = self._normalize_wa_id(to)
        if not normalized_to:
            raise UserError(_("Recipient WhatsApp number is required."))

        safe_template_id = int(template_id or 0)
        if safe_template_id <= 0:
            raise UserError(_("Template is required."))

        template = self.env["ab.whatsapp.template"].sudo().browse(safe_template_id).exists()
        if not template:
            raise UserError(_("Template not found."))
        if (template.status or "").upper() != "APPROVED":
            raise UserError(_("Only APPROVED templates can be sent."))

        required_placeholder_indexes = self._template_required_placeholder_indexes(template)
        clean_template_params: list[str] = []
        if template_params not in (None, False):
            if not isinstance(template_params, list):
                raise UserError(_("Template parameters must be a list of values."))
            clean_template_params = [str(item or "").strip() for item in template_params]

        if required_placeholder_indexes:
            required_count = len(required_placeholder_indexes)
            if len(clean_template_params) != required_count:
                raise UserError(
                    _(
                        "Template requires %s parameter values for placeholders %s."
                    )
                    % (
                        required_count,
                        ", ".join(f"{{{{{item}}}}}" for item in required_placeholder_indexes),
                    )
                )
            if any(not item for item in clean_template_params):
                raise UserError(_("Template parameter values cannot be empty."))

        settings = self._settings()
        token = self._require_token()
        sender_phone_number_id = self._resolve_sender_phone_number_id(
            to_wa_id=normalized_to,
            requested_phone_number_id=phone_number_id,
        )

        url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized_to,
            "type": "template",
            "template": {
                "name": template.name,
                "language": {
                    "code": template.language,
                },
            },
        }
        if required_placeholder_indexes:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value}
                        for value in clean_template_params
                    ],
                }
            ]
        response = self._post_graph_json(url, payload, self._graph_headers(token))
        meta_message_id = ""
        if response.get("messages"):
            meta_message_id = response["messages"][0].get("id") or ""

        preview_text = f"[template] {template.name} ({template.language})"
        record = self._create_message(
            direction="outgoing",
            wa_id=normalized_to,
            phone_number_id=sender_phone_number_id,
            message_type="template",
            text_content=preview_text,
            status="sent",
            meta_message_id=meta_message_id,
            raw_payload={
                "template_id": template.id,
                "template_uid": template.template_uid,
                "response": response,
            },
            contact_name=contact_name,
        )
        return {
            "ok": True,
            "message": self._serialize_message(record),
            "template": self._serialize_template(template),
            "response": response,
        }

    @api.model
    def api_send_text(
        self,
        to: str,
        message: str,
        contact_name: str | None = None,
        phone_number_id: str | None = None,
        reply_to_meta_message_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_system_access()
        text = (message or "").strip()
        if not text:
            raise UserError(_("Message text is required."))

        normalized_to = self._normalize_wa_id(to)
        if not normalized_to:
            raise UserError(_("Recipient WhatsApp number is required."))

        settings = self._settings()
        token = self._require_token()
        sender_phone_number_id = self._resolve_sender_phone_number_id(
            to_wa_id=normalized_to,
            requested_phone_number_id=phone_number_id,
        )

        url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized_to,
            "type": "text",
            "text": {"body": text},
        }
        normalized_reply_meta_id = (reply_to_meta_message_id or "").strip()
        if normalized_reply_meta_id:
            payload["context"] = {"message_id": normalized_reply_meta_id}
        response = self._post_graph_json(url, payload, self._graph_headers(token))
        meta_message_id = ""
        if response.get("messages"):
            meta_message_id = response["messages"][0].get("id") or ""

        record = self._create_message(
            direction="outgoing",
            wa_id=normalized_to,
            phone_number_id=sender_phone_number_id,
            message_type="text",
            text_content=text,
            status="sent",
            meta_message_id=meta_message_id,
            reply_to_meta_message_id=normalized_reply_meta_id or None,
            raw_payload=response,
            contact_name=contact_name,
        )

        return {
            "ok": True,
            "message": self._serialize_message(record),
            "response": response,
        }

    @api.model
    def api_send_media_base64(
        self,
        to: str,
        filename: str,
        content_type: str,
        data_base64: str,
        caption: str | None = None,
        contact_name: str | None = None,
        phone_number_id: str | None = None,
        reply_to_meta_message_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_to = self._normalize_wa_id(to)
        if not normalized_to:
            raise UserError(_("Recipient WhatsApp number is required."))

        if not data_base64:
            raise UserError(_("File data is empty."))

        try:
            binary_data = base64.b64decode(data_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise UserError(_("Invalid base64 file payload.")) from exc

        if not binary_data:
            raise UserError(_("File data is empty."))

        safe_filename = (filename or "attachment").strip() or "attachment"
        safe_content_type = (content_type or "application/octet-stream").strip()

        settings = self._settings()
        token = self._require_token()
        sender_phone_number_id = self._resolve_sender_phone_number_id(
            to_wa_id=normalized_to,
            requested_phone_number_id=phone_number_id,
        )

        message_type = self._infer_message_type(safe_content_type)
        upload_url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/media"
        upload_response = self._upload_graph_media(
            url=upload_url,
            headers=self._graph_headers(token),
            filename=safe_filename,
            content_type=safe_content_type,
            binary_data=binary_data,
        )
        media_id = (upload_response.get("id") or "").strip()
        if not media_id:
            raise UserError(_("Meta API did not return media id after upload."))

        send_url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": normalized_to,
            "type": message_type,
            message_type: {"id": media_id},
        }
        normalized_reply_meta_id = (reply_to_meta_message_id or "").strip()
        if normalized_reply_meta_id:
            payload["context"] = {"message_id": normalized_reply_meta_id}
        safe_caption = (caption or "").strip()
        if safe_caption and message_type in {"image", "video", "document"}:
            payload[message_type]["caption"] = safe_caption
        if message_type == "document":
            payload["document"]["filename"] = safe_filename

        send_response = self._post_graph_json(send_url, payload, self._graph_headers(token))
        meta_message_id = ""
        if send_response.get("messages"):
            meta_message_id = send_response["messages"][0].get("id") or ""

        record = self._create_message(
            direction="outgoing",
            wa_id=normalized_to,
            phone_number_id=sender_phone_number_id,
            message_type=message_type,
            text_content=safe_caption or None,
            media_id=media_id,
            media_mime_type=safe_content_type,
            media_filename=safe_filename,
            status="sent",
            meta_message_id=meta_message_id,
            reply_to_meta_message_id=normalized_reply_meta_id or None,
            raw_payload=send_response,
            contact_name=contact_name,
        )
        return {
            "ok": True,
            "message": self._serialize_message(record),
            "upload": upload_response,
            "response": send_response,
        }

    @api.model
    def api_send_reaction(
        self,
        to: str,
        message_meta_id: str,
        emoji: str,
        contact_name: str | None = None,
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_system_access()
        normalized_to = self._normalize_wa_id(to)
        if not normalized_to:
            raise UserError(_("Recipient WhatsApp number is required."))

        target_meta_id = (message_meta_id or "").strip()
        if not target_meta_id:
            raise UserError(_("Target message id is required for reactions."))

        normalized_emoji = (emoji or "").strip()
        if not normalized_emoji:
            raise UserError(_("Emoji is required."))

        settings = self._settings()
        token = self._require_token()
        sender_phone_number_id = self._resolve_sender_phone_number_id(
            to_wa_id=normalized_to,
            requested_phone_number_id=phone_number_id,
        )

        url = f"https://graph.facebook.com/{settings['api_version']}/{sender_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized_to,
            "type": "reaction",
            "reaction": {
                "message_id": target_meta_id,
                "emoji": normalized_emoji,
            },
        }
        response = self._post_graph_json(url, payload, self._graph_headers(token))
        meta_message_id = ""
        if response.get("messages"):
            meta_message_id = response["messages"][0].get("id") or ""

        record = self._create_message(
            direction="outgoing",
            wa_id=normalized_to,
            phone_number_id=sender_phone_number_id,
            message_type="reaction",
            text_content=normalized_emoji,
            status="sent",
            meta_message_id=meta_message_id,
            reaction_target_meta_message_id=target_meta_id,
            raw_payload=response,
            contact_name=contact_name,
        )
        return {
            "ok": True,
            "message": self._serialize_message(record),
            "response": response,
        }

    @api.model
    def api_edit_message_local(self, message_id: int, new_text: str) -> dict[str, Any]:
        self._ensure_system_access()
        safe_message_id = int(message_id or 0)
        if safe_message_id <= 0:
            raise UserError(_("Message id is required."))

        text = (new_text or "").strip()
        if not text:
            raise UserError(_("Message text is required."))

        message = self.env["ab.whatsapp.message"].sudo().browse(safe_message_id).exists()
        if not message:
            raise UserError(_("Message not found."))
        if message.direction != "outgoing":
            raise UserError(_("Only outgoing messages can be edited."))
        if message.message_type != "text":
            raise UserError(_("Only text messages can be edited."))
        if message.is_deleted:
            raise UserError(_("Deleted messages cannot be edited."))

        old_text = message.text_content
        message.write(
            {
                "text_content": text,
                "edited_from_text": old_text,
                "edited_at": fields.Datetime.now(),
            }
        )
        self._touch_contact_message_meta(
            message.contact_id,
            self._preview_for_message(message.message_type, message.text_content),
            message.create_date,
        )
        return self._serialize_message(message)

    @api.model
    def api_delete_message_local(self, message_id: int) -> dict[str, Any]:
        self._ensure_system_access()
        safe_message_id = int(message_id or 0)
        if safe_message_id <= 0:
            raise UserError(_("Message id is required."))

        message = self.env["ab.whatsapp.message"].sudo().browse(safe_message_id).exists()
        if not message:
            raise UserError(_("Message not found."))

        message.write(
            {
                "is_deleted": True,
                "message_type": "deleted",
                "text_content": _("This message was deleted."),
                "media_id": None,
                "media_mime_type": None,
                "media_filename": None,
            }
        )
        self._touch_contact_message_meta(
            message.contact_id,
            self._preview_for_message(message.message_type, message.text_content),
            message.create_date,
        )
        return self._serialize_message(message)

    @api.model
    def get_message_media_content(self, message_id: int) -> tuple[bytes, str, str]:
        self._ensure_system_access()
        safe_message_id = int(message_id or 0)
        if safe_message_id <= 0:
            raise UserError(_("Message id is required."))

        message = self.env["ab.whatsapp.message"].sudo().browse(safe_message_id).exists()
        if not message:
            raise UserError(_("Message not found."))
        if not message.media_id:
            raise UserError(_("Selected message has no media."))

        data, mime_type, filename = self._download_graph_media(
            media_id=message.media_id,
        )
        vals: dict[str, Any] = {}
        if mime_type and not message.media_mime_type:
            vals["media_mime_type"] = mime_type
        if filename and not message.media_filename:
            vals["media_filename"] = filename
        if vals:
            message.write(vals)
        return data, mime_type, filename

    @api.model
    def process_webhook_payload(self, payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
        data = payload or {}
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []

        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")

                contact_profiles: dict[str, str | None] = {}
                for contact in value.get("contacts", []):
                    wa_id = self._normalize_wa_id(contact.get("wa_id"))
                    profile_name = (contact.get("profile") or {}).get("name")
                    if wa_id:
                        self._find_or_create_contact(wa_id=wa_id, name=profile_name)
                        contact_profiles[wa_id] = profile_name

                for message in value.get("messages", []):
                    message_type = (message.get("type") or "text").strip().lower()
                    sender = self._normalize_wa_id(message.get("from"))
                    meta_message_id = (message.get("id") or "").strip()
                    context = message.get("context") or {}
                    reply_to_meta_message_id = (context.get("id") or "").strip()

                    text_content = None
                    media_id = None
                    media_mime_type = None
                    media_filename = None
                    reaction_target_meta_message_id = None

                    if message_type == "text":
                        text_content = (message.get("text") or {}).get("body")
                    elif message_type in {"image", "video", "audio", "document", "sticker"}:
                        media_block = message.get(message_type) or {}
                        media_id = media_block.get("id")
                        text_content = media_block.get("caption")
                        media_mime_type = media_block.get("mime_type")
                        media_filename = media_block.get("filename")
                    elif message_type == "reaction":
                        reaction_block = message.get("reaction") or {}
                        text_content = (reaction_block.get("emoji") or "").strip() or None
                        reaction_target_meta_message_id = (reaction_block.get("message_id") or "").strip() or None
                    elif message_type == "button":
                        text_content = (message.get("button") or {}).get("text")
                    elif message_type == "location":
                        location_block = message.get("location") or {}
                        location_name = (location_block.get("name") or "").strip()
                        location_address = (location_block.get("address") or "").strip()
                        latitude = location_block.get("latitude")
                        longitude = location_block.get("longitude")

                        location_lines: list[str] = []
                        if location_name:
                            location_lines.append(location_name)
                        if location_address and location_address != location_name:
                            location_lines.append(location_address)
                        if latitude is not None and longitude is not None:
                            location_lines.append(f"https://maps.google.com/?q={latitude},{longitude}")
                        text_content = "\n".join(line for line in location_lines if line) or _("Location")
                    elif message_type == "interactive":
                        text_content = str(message.get("interactive") or {})

                    if not sender:
                        continue

                    record = self._create_message(
                        direction="incoming",
                        wa_id=sender,
                        phone_number_id=phone_number_id,
                        message_type=message_type,
                        text_content=text_content,
                        media_id=media_id,
                        media_mime_type=media_mime_type,
                        media_filename=media_filename,
                        status="received",
                        meta_message_id=meta_message_id,
                        reply_to_meta_message_id=reply_to_meta_message_id,
                        reaction_target_meta_message_id=reaction_target_meta_message_id,
                        raw_payload=message,
                        contact_name=contact_profiles.get(sender),
                    )
                    created.append(self._serialize_message(record))

                for status in value.get("statuses", []):
                    status_rows = self._update_outgoing_message_status(
                        meta_message_id=(status.get("id") or "").strip(),
                        status=status.get("status"),
                        recipient_wa_id=status.get("recipient_id"),
                        phone_number_id=phone_number_id,
                    )
                    updated.extend(status_rows)

        return {"created": created, "updated": updated}
