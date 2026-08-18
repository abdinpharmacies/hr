import re
import getpass
import subprocess
from pathlib import Path

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SYSTEM_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "__last_update",
    "display_name",
}
_META_FIELDS = {
    "db_serial",
    "rec_id",
    "payload_json",
    "source_revision",
    "event_uuid",
    "source_operation",
    "source_write_date",
    "synced_at",
    "active",
}


class AbOdooSyncMirrorScaffold(models.Model):
    _name = "ab_odoo_sync_mirror_scaffold"
    _description = "AB Odoo Sync Mirror Scaffold"
    _order = "id desc"

    name = fields.Char(required=True, readonly=True)
    profile_id = fields.Many2one(
        "ab_odoo_sync_apply_profile",
        string="Apply Profile",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    source_model_name = fields.Char(string="Source Model", required=True, readonly=True, index=True)
    target_model_name = fields.Char(string="Target Model", required=True, readonly=True, index=True)
    module_name = fields.Char(string="Generated Module", required=True, readonly=True, index=True)
    generated_path = fields.Char(string="Generated Path", readonly=True)
    command_hint = fields.Text(string="Upgrade Command", readonly=True)
    field_spec_json = fields.Json(string="Generated Fields", default=list, readonly=True)
    skipped_field_json = fields.Json(string="Skipped Fields", default=list, readonly=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("generated", "Generated"),
        ],
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )
    active = fields.Boolean(default=True, index=True)

    _uniq_profile = models.Constraint(
        "UNIQUE(profile_id)",
        "Only one mirror scaffold request is allowed for each apply profile.",
    )

    @api.model
    def create_from_profile(self, profile):
        profile.ensure_one()
        if profile.apply_mode != "mirror_sync":
            raise UserError(_("Mirror scaffold generation is available only for Mirror Sync Model profiles."))

        target_model_name = profile.mirror_target_from_source(profile.source_model_name)
        module_name = self._module_name_from_target(target_model_name)
        existing = self.sudo().search([("profile_id", "=", profile.id)], limit=1)
        field_specs, skipped_fields = self._field_specs_from_profile(profile)
        vals = {
            "name": _("Mirror scaffold for %(model)s") % {"model": profile.source_model_name},
            "profile_id": profile.id,
            "source_model_name": profile.source_model_name,
            "target_model_name": target_model_name,
            "module_name": module_name,
            "field_spec_json": field_specs,
            "skipped_field_json": skipped_fields,
            "state": "draft",
        }
        if existing:
            existing.write(vals)
            return existing
        return self.sudo().create(vals)

    @api.model
    def _module_name_from_target(self, target_model_name):
        clean_name = (target_model_name or "").replace(".", "_")
        return "ab_sync_mirror_%s" % clean_name.removesuffix("__sync")

    @api.model
    def _class_name_from_target(self, target_model_name):
        parts = [part for part in (target_model_name or "").split("_") if part]
        return "".join(part[:1].upper() + part[1:] for part in parts)

    @api.model
    def _field_specs_from_profile(self, profile):
        specs = []
        skipped = []
        for field_name, source_field in sorted(profile._source_field_info().items()):
            if field_name in _SYSTEM_FIELDS or field_name in _META_FIELDS:
                continue
            if not _FIELD_NAME_RE.match(field_name) or field_name.startswith("_"):
                skipped.append({"name": field_name, "reason": "invalid_field_name"})
                continue
            field_type = getattr(source_field, "type", False) or "json"
            specs.append(
                {
                    "name": field_name,
                    "source_type": field_type,
                    "target_type": self._target_field_type(field_type),
                }
            )
        return specs, skipped

    @api.model
    def _target_field_type(self, source_type):
        return {
            "binary": "Binary",
            "boolean": "Boolean",
            "char": "Char",
            "date": "Date",
            "datetime": "Datetime",
            "float": "Float",
            "html": "Html",
            "integer": "Integer",
            "json": "Json",
            "monetary": "Float",
            "selection": "Char",
            "text": "Text",
        }.get(source_type, "Json")

    def action_generate_files(self):
        for scaffold in self.sudo():
            scaffold._generate_files()
        return self._notification(
            _("Mirror Scaffold"),
            _("Generated mirror scaffold file(s). Install or upgrade the generated module to create the table."),
            "success",
        )

    def action_open_profile(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Apply Profile"),
            "res_model": "ab_odoo_sync_apply_profile",
            "res_id": self.profile_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _generate_files(self):
        self.ensure_one()
        addon_dir = Path(__file__).resolve().parents[2]
        module_dir = addon_dir / self.module_name
        marker = module_dir / ".ab_odoo_sync_generated"
        if module_dir.exists() and not marker.exists():
            raise UserError(
                _("Module path %(path)s already exists and is not marked as generated by AB Odoo Sync.")
                % {"path": str(module_dir)}
            )

        (module_dir / "models").mkdir(parents=True, exist_ok=True)
        (module_dir / "security").mkdir(parents=True, exist_ok=True)
        (module_dir / "views").mkdir(parents=True, exist_ok=True)
        (module_dir / "i18n").mkdir(parents=True, exist_ok=True)
        marker.write_text("generated by ab_odoo_sync\n", encoding="utf-8")
        (module_dir / "__init__.py").write_text("from . import models\n", encoding="utf-8")
        (module_dir / "models" / "__init__.py").write_text("from . import mirror_models\n", encoding="utf-8")
        developer = self._current_git_user(addon_dir)
        (module_dir / "__manifest__.py").write_text(self._manifest_source(developer), encoding="utf-8")
        (module_dir / "models" / "mirror_models.py").write_text(self._model_source(), encoding="utf-8")
        (module_dir / "security" / "ir.model.access.csv").write_text(self._access_source(), encoding="utf-8")
        (module_dir / "views" / "mirror_views.xml").write_text(self._views_source(), encoding="utf-8")
        (module_dir / "i18n" / "ar.po").write_text(self._translation_source("ar"), encoding="utf-8")
        (module_dir / "i18n" / "ar_001.po").write_text(self._translation_source("ar_001"), encoding="utf-8")

        command = (
            "/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin "
            "-c <config> -d <database> -i %(module)s --stop-after-init"
        ) % {"module": self.module_name}
        self.write(
            {
                "generated_path": str(module_dir),
                "command_hint": command,
                "state": "generated",
            }
        )

    def _current_git_user(self, addon_dir):
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                cwd=str(addon_dir),
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return getpass.getuser()
        return result.stdout.strip() or getpass.getuser()

    def _manifest_source(self, developer):
        return """{
    "name": "%(title)s",
    "summary": "Generated AB Odoo Sync mirror model",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Tools",
    "author": "Abdin Pharmacies",
    "developer": "%(developer)s",
    "application": False,
    "depends": ["base", "ab_odoo_sync"],
    "data": [
        "security/ir.model.access.csv",
        "views/mirror_views.xml",
    ],
    "installable": True,
}
""" % {
            "developer": developer.replace('"', "'"),
            "title": self.module_name.replace("_", " ").title(),
        }

    def _model_source(self):
        fields_source = "\n".join(self._field_source(spec) for spec in (self.field_spec_json or []))
        if fields_source:
            fields_source = "\n" + fields_source
        return """from odoo import fields, models


class %(class_name)s(models.Model):
    _name = "%(model_name)s"
    _description = "%(description)s"
    _table = "%(table_name)s"
    _order = "db_serial, rec_id"

    db_serial = fields.Integer(string="DB Serial", required=True, index=True, readonly=True)
    rec_id = fields.Integer(string="Source Record ID", required=True, index=True, readonly=True)
    payload_json = fields.Json(string="Payload", default=dict, readonly=True)
    source_revision = fields.Integer(string="Source Revision", default=0, required=True, readonly=True)
    event_uuid = fields.Char(string="Event UUID", index=True, readonly=True)
    source_operation = fields.Selection(
        selection=[("upsert", "Upsert"), ("archive", "Archive")],
        default="upsert",
        required=True,
        readonly=True,
    )
    source_write_date = fields.Datetime(string="Source Write Date", readonly=True)
    synced_at = fields.Datetime(string="Synced At", readonly=True)
    active = fields.Boolean(default=True, index=True)%(fields_source)s

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Branch source record must be unique.",
    )
""" % {
            "class_name": self._class_name_from_target(self.target_model_name),
            "description": self.name,
            "fields_source": fields_source,
            "model_name": self.target_model_name,
            "table_name": self.target_model_name,
        }

    def _field_source(self, spec):
        return '    %(name)s = fields.%(field_type)s(readonly=True)' % {
            "name": spec["name"],
            "field_type": spec["target_type"],
        }

    def _translation_source(self, language):
        xml = self.target_model_name
        entries = {}

        def add_entry(msgid, msgstr, refs=None):
            entry = entries.setdefault(msgid, {"msgstr": msgstr, "refs": []})
            entry["msgstr"] = msgstr
            entry["refs"].extend(refs or [])

        add_entry(self.module_name.replace("_", " ").title(), "نموذج مرآة مزامنة")
        add_entry("Generated AB Odoo Sync mirror model", "نموذج مرآة مولد لمزامنة Odoo")
        add_entry(
            self.name,
            "هيكل مرآة لـ %s" % self.source_model_name,
            [
                "model:ir.actions.act_window,name:%s.action_%s" % (self.module_name, xml),
                "model:ir.ui.menu,name:%s.menu_%s" % (self.module_name, xml),
                "model:ir.model,name:%s.model_%s" % (self.module_name, xml),
            ],
        )
        meta_fields = {
            "db_serial": ("DB Serial", "رقم قاعدة البيانات"),
            "rec_id": ("Source Record ID", "معرف سجل المصدر"),
            "payload_json": ("Payload", "الحمولة"),
            "source_revision": ("Source Revision", "مراجعة المصدر"),
            "event_uuid": ("Event UUID", "معرف الحدث"),
            "source_write_date": ("Source Write Date", "تاريخ تعديل المصدر"),
            "synced_at": ("Synced At", "وقت المزامنة"),
            "active": ("Active", "نشط"),
        }
        for field_name, (label, translation) in meta_fields.items():
            add_entry(
                label,
                translation,
                ["model:ir.model.fields,field_description:%s.field_%s__%s" % (self.module_name, xml, field_name)],
            )
        add_entry("Upsert", "إنشاء أو تحديث")
        add_entry("Archive", "أرشفة")
        add_entry("Branch source record must be unique.", "يجب أن يكون سجل مصدر الفرع فريدا.")
        field_words = {
            "avg": "متوسط",
            "average": "متوسط",
            "daily": "يومي",
            "growth": "نمو",
            "pct": "نسبة",
            "sales": "مبيعات",
            "products": "منتجات",
            "per": "لكل",
            "invoice": "فاتورة",
            "invoices": "فواتير",
            "store": "فرع",
            "stores": "فروع",
            "bearing": "تحمل",
            "collection": "تحصيل",
            "line": "بند",
            "lines": "بنود",
            "ids": "معرفات",
            "company": "شركة",
            "part": "حصة",
            "amount": "مبلغ",
            "customer": "عميل",
            "date": "تاريخ",
            "from": "من",
            "to": "إلى",
            "item": "صنف",
            "medicine": "دواء",
            "name": "الاسم",
            "non": "غير",
            "prev": "سابق",
            "refresh": "تحديث",
            "filter": "تصفية",
            "key": "مفتاح",
            "label": "تسمية",
            "total": "إجمالي",
            "product": "منتج",
            "units": "وحدات",
            "sold": "مباعة",
            "unique": "فريدة",
            "user": "مستخدم",
        }
        for spec in self.field_spec_json or []:
            label = spec["name"].replace("_", " ").title()
            translated = " ".join(field_words.get(part, part) for part in spec["name"].split("_"))
            add_entry(
                label,
                translated,
                [
                    "model:ir.model.fields,field_description:%s.field_%s__%s"
                    % (self.module_name, xml, spec["name"])
                ],
            )

        lines = [
            "# Translation of generated AB Odoo Sync mirror module.",
            "# This file was generated by ab_odoo_sync.",
            'msgid ""',
            'msgstr ""',
            '"Project-Id-Version: %s\\n"' % self.module_name,
            '"Language: %s\\n"' % language,
            '"MIME-Version: 1.0\\n"',
            '"Content-Type: text/plain; charset=UTF-8\\n"',
            '"Content-Transfer-Encoding: 8bit\\n"',
            "",
        ]
        for msgid, entry in sorted(entries.items()):
            lines.append("#. module: %s" % self.module_name)
            lines.extend("#: %s" % ref for ref in sorted(set(entry["refs"])))
            lines.extend(
                [
                    'msgid "%s"' % self._po_escape(msgid),
                    'msgstr "%s"' % self._po_escape(entry["msgstr"]),
                    "",
                ]
            )
        return "\n".join(lines)

    @api.model
    def _po_escape(self, value):
        return (value or "").replace("\\", "\\\\").replace('"', '\\"')

    def _access_source(self):
        return (
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
            "access_%(model)s_system,%(model)s system,model_%(model)s,base.group_system,1,1,1,0\n"
        ) % {"model": self.target_model_name}

    def _views_source(self):
        visible_fields = [
            spec["name"]
            for spec in (self.field_spec_json or [])
            if spec["target_type"] not in {"Binary", "Html", "Json", "Text"}
        ][:8]
        list_fields = "\n".join("                    <field name=\"%s\" optional=\"show\"/>" % name for name in visible_fields)
        form_fields = "\n".join("                                <field name=\"%s\"/>" % name for name in visible_fields)
        return """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>
        <record id="view_%(xml)s_list" model="ir.ui.view">
            <field name="name">%(model)s.list</field>
            <field name="model">%(model)s</field>
            <field name="arch" type="xml">
                <list create="0" edit="0" delete="0">
                    <field name="db_serial"/>
                    <field name="rec_id"/>
                    <field name="source_revision"/>
%(list_fields)s
                    <field name="active"/>
                    <field name="synced_at"/>
                </list>
            </field>
        </record>

        <record id="view_%(xml)s_form" model="ir.ui.view">
            <field name="name">%(model)s.form</field>
            <field name="model">%(model)s</field>
            <field name="arch" type="xml">
                <form create="0" edit="0" delete="0">
                    <sheet>
                        <group>
                            <group>
                                <field name="db_serial"/>
                                <field name="rec_id"/>
                                <field name="source_revision"/>
                                <field name="event_uuid"/>
                                <field name="source_operation"/>
                                <field name="source_write_date"/>
                                <field name="synced_at"/>
                            </group>
                            <group>
%(form_fields)s
                                <field name="active"/>
                            </group>
                        </group>
                        <field name="payload_json"/>
                    </sheet>
                </form>
            </field>
        </record>

        <record id="action_%(xml)s" model="ir.actions.act_window">
            <field name="name">%(action_name)s</field>
            <field name="res_model">%(model)s</field>
            <field name="view_mode">list,form</field>
        </record>

        <menuitem id="menu_%(xml)s" name="%(action_name)s"
                  parent="ab_odoo_sync.menu_ab_odoo_sync_root" action="action_%(xml)s"
                  sequence="80" groups="base.group_system"/>
    </data>
</odoo>
""" % {
            "action_name": self.name,
            "form_fields": form_fields,
            "list_fields": list_fields,
            "model": self.target_model_name,
            "xml": self.target_model_name,
        }

    @api.model
    def _notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
