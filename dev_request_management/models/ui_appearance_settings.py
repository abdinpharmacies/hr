# -*- coding: utf-8 -*-
import base64
import json
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class UiAppearanceSettings(models.Model):
    _name = "ui.appearance.settings"
    _description = "UI Appearance Settings"
    _order = "scope desc, id desc"

    name = fields.Char(required=True, default="Development Requests Appearance")
    active = fields.Boolean(default=True)
    scope = fields.Selection(
        [
            ("global", "Global"),
            ("user", "User"),
        ],
        default="global",
        required=True,
    )
    user_id = fields.Many2one("res.users", string="User Override")
    theme_mode = fields.Selection(
        [
            ("light", "Light"),
            ("dark", "Dark"),
            ("custom", "Custom"),
        ],
        default="light",
        required=True,
    )
    preset_theme = fields.Selection(
        [
            ("default", "Default"),
            ("dark_mode", "Dark Mode"),
            ("glass_ui", "Glass UI"),
            ("corporate", "Corporate"),
            ("minimal", "Minimal"),
        ],
        default="default",
    )
    primary_color = fields.Char(default="#1e4f8c")
    secondary_color = fields.Char(default="#f4f7fb")
    accent_color = fields.Char(default="#2e9cca")
    text_color = fields.Char(default="#1f2937")
    background_type = fields.Selection(
        [
            ("solid", "Solid"),
            ("gradient", "Gradient"),
            ("image", "Image"),
        ],
        default="solid",
        required=True,
    )
    background_color = fields.Char(default="#eef4fb")
    background_gradient = fields.Char(default="linear-gradient(135deg, #eef4fb 0%, #dfeaf7 100%)")
    background_image = fields.Binary(attachment=True)
    background_image_filename = fields.Char()
    background_image_url = fields.Char()
    background_image_opacity = fields.Float(default=0.2)
    background_image_blur = fields.Integer(default=0)
    background_image_size = fields.Selection(
        [
            ("cover", "Cover"),
            ("contain", "Contain"),
            ("repeat", "Repeat"),
        ],
        default="cover",
    )
    enable_parallax = fields.Boolean()
    card_style = fields.Selection(
        [
            ("default", "Default"),
            ("glass", "Glass"),
            ("flat", "Flat"),
            ("shadowed", "Shadowed"),
        ],
        default="shadowed",
    )
    card_border_radius = fields.Integer(default=14)
    font_family = fields.Char(default="Inter, 'Segoe UI', sans-serif")
    font_size_base = fields.Integer(default=14)
    kanban_density = fields.Selection(
        [
            ("compact", "Compact"),
            ("normal", "Normal"),
            ("spacious", "Spacious"),
        ],
        default="normal",
    )
    enable_animations = fields.Boolean(default=True)
    enable_hover_effects = fields.Boolean(default=True)
    auto_dark_mode = fields.Boolean()
    custom_css = fields.Text()
    is_global = fields.Boolean(compute="_compute_is_global", store=True)

    _scope_user_unique = models.Constraint(
        "UNIQUE(scope, user_id)",
        "Only one appearance settings record is allowed per scope and user.",
    )
    _opacity_range = models.Constraint(
        "CHECK(background_image_opacity >= 0 AND background_image_opacity <= 1)",
        "Background image opacity must stay between 0 and 1.",
    )

    @api.depends("scope")
    def _compute_is_global(self):
        for record in self:
            record.is_global = record.scope == "global"

    @api.constrains("scope", "user_id")
    def _check_scope_user(self):
        for record in self:
            if record.scope == "global" and record.user_id:
                raise ValidationError(_("Global appearance settings cannot be linked to a user."))
            if record.scope == "user" and not record.user_id:
                raise ValidationError(_("User appearance overrides must target a specific user."))

    @api.model
    def _default_theme_values(self):
        return {
            "theme_mode": "light",
            "preset_theme": "default",
            "primary_color": "#1e4f8c",
            "secondary_color": "#f4f7fb",
            "accent_color": "#2e9cca",
            "text_color": "#1f2937",
            "background_type": "solid",
            "background_color": "#eef4fb",
            "background_gradient": "linear-gradient(135deg, #eef4fb 0%, #dfeaf7 100%)",
            "background_image_opacity": 0.2,
            "background_image_blur": 0,
            "background_image_size": "cover",
            "enable_parallax": False,
            "card_style": "shadowed",
            "card_border_radius": 14,
            "font_family": "Inter, 'Segoe UI', sans-serif",
            "font_size_base": 14,
            "kanban_density": "normal",
            "enable_animations": True,
            "enable_hover_effects": True,
            "auto_dark_mode": False,
            "custom_css": False,
        }

    @api.model
    def _default_theme_payload(self):
        values = self._default_theme_values().copy()
        values.update(
            {
                "id": False,
                "name": "Global Development Requests Theme",
                "scope": "global",
                "background_image_url": "",
                "background_image_src": "",
                "can_customize": self._can_customize(),
                "can_edit_global": self._can_edit_global(),
                "can_edit_personal": True,
            }
        )
        values["effective_mode"] = self._resolve_theme_mode(values)
        return values

    @api.model
    def _preset_values(self):
        return {
            "default": {
                "theme_mode": "light",
                "primary_color": "#1e4f8c",
                "secondary_color": "#f4f7fb",
                "accent_color": "#2e9cca",
                "text_color": "#1f2937",
                "background_type": "solid",
                "background_color": "#eef4fb",
                "background_gradient": "linear-gradient(135deg, #eef4fb 0%, #dfeaf7 100%)",
                "card_style": "shadowed",
                "card_border_radius": 14,
                "font_family": "Inter, 'Segoe UI', sans-serif",
                "font_size_base": 14,
                "kanban_density": "normal",
                "enable_animations": True,
                "enable_hover_effects": True,
            },
            "dark_mode": {
                "theme_mode": "dark",
                "primary_color": "#60a5fa",
                "secondary_color": "#111827",
                "accent_color": "#22d3ee",
                "text_color": "#f3f4f6",
                "background_type": "gradient",
                "background_color": "#0f172a",
                "background_gradient": "linear-gradient(135deg, #0f172a 0%, #111827 45%, #1e293b 100%)",
                "card_style": "shadowed",
                "card_border_radius": 16,
                "font_family": "Inter, 'Segoe UI', sans-serif",
                "font_size_base": 14,
                "kanban_density": "normal",
                "enable_animations": True,
                "enable_hover_effects": True,
            },
            "glass_ui": {
                "theme_mode": "custom",
                "primary_color": "#3b82f6",
                "secondary_color": "#dbeafe",
                "accent_color": "#8b5cf6",
                "text_color": "#0f172a",
                "background_type": "gradient",
                "background_color": "#dbeafe",
                "background_gradient": "linear-gradient(135deg, rgba(219,234,254,1) 0%, rgba(191,219,254,1) 45%, rgba(221,214,254,1) 100%)",
                "card_style": "glass",
                "card_border_radius": 20,
                "font_family": "Inter, 'Segoe UI', sans-serif",
                "font_size_base": 14,
                "kanban_density": "normal",
                "enable_animations": True,
                "enable_hover_effects": True,
            },
            "corporate": {
                "theme_mode": "light",
                "primary_color": "#12355b",
                "secondary_color": "#f8fafc",
                "accent_color": "#2a9d8f",
                "text_color": "#1f2937",
                "background_type": "solid",
                "background_color": "#f1f5f9",
                "background_gradient": "linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)",
                "card_style": "shadowed",
                "card_border_radius": 12,
                "font_family": "IBM Plex Sans, 'Segoe UI', sans-serif",
                "font_size_base": 14,
                "kanban_density": "normal",
                "enable_animations": False,
                "enable_hover_effects": True,
            },
            "minimal": {
                "theme_mode": "light",
                "primary_color": "#111827",
                "secondary_color": "#ffffff",
                "accent_color": "#6b7280",
                "text_color": "#111827",
                "background_type": "solid",
                "background_color": "#f9fafb",
                "background_gradient": "linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%)",
                "card_style": "flat",
                "card_border_radius": 10,
                "font_family": "Inter, 'Segoe UI', sans-serif",
                "font_size_base": 13,
                "kanban_density": "compact",
                "enable_animations": False,
                "enable_hover_effects": False,
            },
        }

    @api.model
    def _ensure_global_settings(self):
        record = self.sudo().search([("scope", "=", "global")], limit=1)
        if not record:
            values = self._default_theme_values()
            values.update({"name": "Global Development Requests Theme", "scope": "global"})
            record = self.sudo().create(values)
        return record.with_env(self.env)

    @api.model
    def _get_target_record(self, scope="auto"):
        if scope == "auto":
            scope = "global" if self._can_edit_global() else "user"
        if scope == "global":
            return self._ensure_global_settings()
        record = self.sudo().search([("scope", "=", "user"), ("user_id", "=", self.env.user.id)], limit=1)
        if not record:
            values = self._default_theme_values()
            values.update(
                {
                    "name": _("Theme Override for %s") % self.env.user.display_name,
                    "scope": "user",
                    "user_id": self.env.user.id,
                }
            )
            record = self.sudo().create(values)
        return record.with_env(self.env)

    @api.model
    def _get_effective_record(self):
        user_record = self.sudo().search(
            [("scope", "=", "user"), ("user_id", "=", self.env.user.id), ("active", "=", True)],
            limit=1,
        )
        return user_record or self._ensure_global_settings()

    @api.model
    def _can_customize(self):
        return self.env.user.has_group("dev_request_management.group_development_request_admin") or self.env.user.has_group(
            "dev_request_management.group_development_request_ui_customizer"
        )

    @api.model
    def _can_edit_global(self):
        return self.env.user.has_group("dev_request_management.group_development_request_admin")

    @api.model
    def _serialize_record(self, record):
        values = {
            "id": record.id,
            "name": record.name,
            "scope": record.scope,
            "theme_mode": record.theme_mode,
            "preset_theme": record.preset_theme,
            "primary_color": record.primary_color or "#1e4f8c",
            "secondary_color": record.secondary_color or "#f4f7fb",
            "accent_color": record.accent_color or "#2e9cca",
            "text_color": record.text_color or "#1f2937",
            "background_type": record.background_type or "solid",
            "background_color": record.background_color or "#eef4fb",
            "background_gradient": record.background_gradient or "",
            "background_image_url": record.background_image_url or "",
            "background_image_opacity": record.background_image_opacity,
            "background_image_blur": record.background_image_blur,
            "background_image_size": record.background_image_size or "cover",
            "enable_parallax": record.enable_parallax,
            "card_style": record.card_style or "shadowed",
            "card_border_radius": record.card_border_radius or 14,
            "font_family": record.font_family or "Inter, 'Segoe UI', sans-serif",
            "font_size_base": record.font_size_base or 14,
            "kanban_density": record.kanban_density or "normal",
            "enable_animations": record.enable_animations,
            "enable_hover_effects": record.enable_hover_effects,
            "auto_dark_mode": record.auto_dark_mode,
            "custom_css": record.custom_css or "",
            "can_customize": self._can_customize(),
            "can_edit_global": self._can_edit_global(),
            "can_edit_personal": True,
        }
        if record.background_image:
            values["background_image_src"] = "data:image/*;base64,%s" % record.background_image.decode() if isinstance(record.background_image, bytes) else "data:image/*;base64,%s" % record.background_image
        else:
            values["background_image_src"] = values["background_image_url"]
        values["effective_mode"] = self._resolve_theme_mode(values)
        return values

    @api.model
    def _resolve_theme_mode(self, values):
        if values.get("auto_dark_mode"):
            hour = datetime.now().hour
            if hour >= 18 or hour < 6:
                return "dark"
        return values.get("theme_mode") or "light"

    @api.model
    def get_current_theme_payload(self):
        try:
            record = self._get_effective_record()
            if not record:
                return self._default_theme_payload()
            return self._serialize_record(record)
        except Exception:
            return self._default_theme_payload()

    @api.model
    def save_theme_payload(self, payload, scope="auto"):
        if not self._can_customize():
            raise AccessError(_("You do not have permission to customize the appearance."))
        if scope == "global" and not self._can_edit_global():
            raise AccessError(_("Only administrators can change the global appearance."))
        record = self._get_target_record(scope=scope)
        vals = self._prepare_payload_values(payload, scope=record.scope)
        record.write(vals)
        return self._serialize_record(record)

    @api.model
    def apply_preset_theme(self, preset_theme, scope="auto"):
        if preset_theme not in self._preset_values():
            raise UserError(_("Unknown theme preset."))
        record = self._get_target_record(scope=scope)
        if record.scope == "global" and not self._can_edit_global():
            raise AccessError(_("Only administrators can change the global appearance."))
        vals = self._preset_values()[preset_theme].copy()
        vals["preset_theme"] = preset_theme
        record.write(vals)
        return self._serialize_record(record)

    @api.model
    def reset_theme_payload(self, scope="auto"):
        record = self._get_target_record(scope=scope)
        if record.scope == "global" and not self._can_edit_global():
            raise AccessError(_("Only administrators can reset the global appearance."))
        vals = self._default_theme_values()
        vals["preset_theme"] = "default"
        vals["background_image"] = False
        vals["background_image_url"] = False
        record.write(vals)
        return self._serialize_record(record)

    @api.model
    def export_theme_payload(self, scope="auto"):
        record = self._get_target_record(scope=scope)
        payload = self._serialize_record(record)
        payload.pop("id", None)
        payload.pop("can_customize", None)
        payload.pop("can_edit_global", None)
        payload.pop("can_edit_personal", None)
        return json.dumps(payload, indent=2)

    @api.model
    def import_theme_payload(self, payload_json, scope="auto"):
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise UserError(_("Invalid JSON payload: %s") % exc) from exc
        return self.save_theme_payload(payload, scope=scope)

    @api.model
    def _prepare_payload_values(self, payload, scope="global"):
        allowed_fields = {
            "theme_mode",
            "preset_theme",
            "primary_color",
            "secondary_color",
            "accent_color",
            "text_color",
            "background_type",
            "background_color",
            "background_gradient",
            "background_image",
            "background_image_url",
            "background_image_opacity",
            "background_image_blur",
            "background_image_size",
            "enable_parallax",
            "card_style",
            "card_border_radius",
            "font_family",
            "font_size_base",
            "kanban_density",
            "enable_animations",
            "enable_hover_effects",
            "auto_dark_mode",
            "custom_css",
        }
        vals = {key: payload[key] for key in allowed_fields if key in payload}
        vals["scope"] = scope
        if scope == "user":
            vals["user_id"] = self.env.user.id
            vals.setdefault("name", _("Theme Override for %s") % self.env.user.display_name)
        if vals.get("background_image") and vals["background_image"].startswith("data:"):
            vals["background_image"] = vals["background_image"].split(",", 1)[1]
        if vals.get("background_image"):
            try:
                base64.b64decode(vals["background_image"])
            except Exception as exc:
                raise ValidationError(_("Background image payload is not valid base64.")) from exc
        if vals.get("background_image_opacity") is not None:
            vals["background_image_opacity"] = float(vals["background_image_opacity"])
        if vals.get("background_image_blur") is not None:
            vals["background_image_blur"] = int(vals["background_image_blur"])
        if vals.get("card_border_radius") is not None:
            vals["card_border_radius"] = int(vals["card_border_radius"])
        if vals.get("font_size_base") is not None:
            vals["font_size_base"] = int(vals["font_size_base"])
        return vals
