import hashlib
import json
import logging
import time
from datetime import timedelta

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import _, _lt, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_escape
from odoo.addons.integration_queue_job.exception import RetryableJobError

from ..services.classification import CATEGORY_ALIASES, ENGINE_VERSION, classify_local, normalize, taxonomy_key
from ..services.historical import historical_index, normalize_code
from ..services.web_research import BraveResearchProvider, WebResearchProvider


_logger = logging.getLogger(__name__)
_INTERNAL = object()
METHODS = [("forced", "Force Categorized"), ("manual", "Manual"), ("historical_mapping", "Historical Mapping"), ("local_rule", "Local Rule"), ("web_research", "Web Research"), ("needs_review", "Needs Review"), ("failed", "Failed")]
STATUSES = [("pending", "Pending"), ("processing", "Processing"), ("classified", "Classified"), ("needs_review", "Needs Review"), ("failed", "Failed")]

ROOT_DESCRIPTIONS = {
    'medicines': _lt('Medicines organized by their intended therapeutic category, dosage form, and pharmaceutical information.'),
    'vitamins_and_supplements': _lt('Vitamins, minerals, and nutritional supplements organized by their stated nutritional purpose and intended users.'),
    'skin_care_and_beauty': _lt('Skin care and beauty products organized by skin concern, product function, and area of use.'),
    'hair_care': _lt('Hair and scalp products organized by cleansing, conditioning, styling, and specific hair concerns.'),
    'personal_care': _lt('Daily personal care products for oral hygiene, bathing, deodorants, shaving, and feminine care.'),
    'mother_and_baby': _lt('Products for mothers and children, including feeding, baby care, diapers, and accessories.'),
    'medical_devices_and_supplies': _lt('Medical devices and supplies for monitoring, patient care, mobility, wound care, and first aid.'),
    'hygiene_and_household': _lt('Hygiene and household essentials for cleaning, disinfection, paper products, and home care.'),
}


def check_manager(env):
    if not env.user.has_group("base.group_system"):
        raise AccessError(env._("Only administrators can manage product classification."))


def product_facts(product, template):
    p, t = product.with_context(lang="en_US"), template.with_context(lang="en_US")
    return {
        "name": (p.name or p.product_card_name) if p else t.name,
        "card_name": p.product_card_name if p else "", "code": p.code if p else t.default_code,
        "description": p.description if p else t.description_sale,
        "ingredient": p.effective_material if p else "", "strength": p.effective_material_conc if p else "",
        "manufacturer": p.company_id.name if p else "", "is_medicine": p.is_medicine if p else False,
        "groups": " | ".join(p.groups_ids.mapped("website_sync_group_path")) if p else "",
        "scientific_groups": " | ".join(p.scientific_groups_ids.mapped("display_name")) if p else "",
        "usage": p.usage_causes_id.display_name if p else "", "form": p.usage_manner_id.display_name if p else "",
        "attributes": " | ".join(t.attribute_line_ids.value_ids.mapped("name")) if t else "",
    }


def outcome_reason(env, outcome):
    reasons = {
        "No deterministic rule matched": env._("No deterministic rule matched"),
        "Conflicting local rules": env._("Conflicting local rules"),
        "Duplicate historical product mapping": env._("Duplicate historical product mapping"),
        "Conflicting historical categories": env._("Conflicting historical categories"),
        "Historical category mapping": env._("Historical category mapping"),
        "Historical mapping is missing or unsuitable": env._("Historical mapping is missing or unsuitable"),
        "Permanent manual decision": env._("Permanent manual decision"),
        "Explicit force categorization": env._("Explicit force categorization"),
        "Conflicting web evidence": env._("Conflicting web evidence"),
    }
    if outcome.get("method") == "local_rule":
        return env._("Matched deterministic rule: %s", outcome.get("rule", ""))
    if outcome.get("method") == "web_research":
        return env._("Trusted web evidence matched deterministic rule: %s", outcome.get("rule", ""))
    return reasons.get(outcome.get("reason"), outcome.get("reason"))


class AbProductClassification(models.Model):
    _inherit = "ab_product"

    ab_classification_assignment_ids = fields.One2many("ab_product_classification_assignment", "ab_product_id", groups="base.group_system")
    ab_classification_result_ids = fields.One2many("ab_product_classification_result", "ab_product_id", groups="base.group_system")

    def _classification_facts(self):
        self.ensure_one()
        return product_facts(self, self.website_product_tmpl_id)


class ProductTemplateClassification(models.Model):
    _inherit = "product.template"

    ab_classification_assignment_ids = fields.One2many("ab_product_classification_assignment", "product_id", groups="base.group_system")
    ab_classification_result_ids = fields.One2many("ab_product_classification_result", "product_id", groups="base.group_system")


class ClassificationAudit(models.AbstractModel):
    _name = "ab_classification_audit"
    _description = "Classification Audit Protection"

    def _internal(self):
        return self.sudo().with_context(classification_internal=_INTERNAL)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("classification_internal") is not _INTERNAL:
            raise AccessError(_("Use classification workflow actions to create audit records."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("classification_internal") is not _INTERNAL:
            raise AccessError(_("Classification audit records cannot be edited directly."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Classification audit records must be retained."))


class ClassificationTaxonomy(models.Model):
    _name = "ab_product_classification_taxonomy"
    _description = "Approved Product Taxonomy"
    _order = "sequence, id"
    _key_unique = models.Constraint("UNIQUE(key)", "Taxonomy keys must be unique.")
    _category_unique = models.Constraint("UNIQUE(category_id)", "Each website category can represent only one taxonomy node.")

    name = fields.Char(required=True, translate=True)
    key = fields.Char(required=True, index=True)
    parent_id = fields.Many2one("ab_product_classification_taxonomy", ondelete="restrict")
    sequence = fields.Integer()
    category_id = fields.Many2one("product.public.category", string="Website Category", ondelete="restrict")
    description = fields.Text(string="Category Description", translate=True)
    need_ids = fields.Many2many(
        'product.tag', 'ab_classification_taxonomy_need_rel', 'taxonomy_id', 'tag_id',
        string='Shop by Need', domain=[('ab_shop_need_key', '!=', False)],
        help='Choose needs for this category. Needs on a main category also apply to its subcategories.',
    )
    ready = fields.Boolean(compute="_compute_ready")

    @api.constrains('need_ids')
    def _check_need_ids(self):
        if any(not need.ab_shop_need_key for need in self.need_ids):
            raise ValidationError(_('Choose only approved shop needs.'))

    @api.depends("category_id", "category_id.parent_id", "category_id.name", "parent_id.category_id")
    def _compute_ready(self):
        for node in self:
            category = node.category_id.with_context(lang="en_US")
            node.ready = bool(category and not category.website_id and category.parent_id == node.parent_id.category_id and category.name == node.with_context(lang="en_US").name)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get("install_mode")):
            raise AccessError(_("The approved taxonomy is closed."))
        return super().create(vals_list)

    def write(self, vals):
        if not (self.env.su and self.env.context.get("install_mode")) and set(vals) - {"category_id", "description", "need_ids"}:
            raise AccessError(_("The approved taxonomy is closed."))
        if set(vals) & {'description', 'need_ids'}:
            check_manager(self.env)
            if self.env['ab_product_classification_run'].sudo().search_count(fields.Domain('state', 'in', ['queued', 'running', 'paused', 'stopping']) | fields.Domain('force_state', 'in', ['queued', 'running'])):
                raise UserError(_('Stop the active classification run before changing taxonomy bindings.'))
        if "category_id" in vals and not (self.env.su and self.env.context.get("install_mode")):
            check_manager(self.env)
            self.env["ab_product"]._lock_website_sync()
            if self.env["ab_product_classification_run"].sudo().search_count(fields.Domain("state", "in", ["queued", "running", "paused", "stopping"]) | fields.Domain("force_state", "in", ["queued", "running"])):
                raise UserError(_("Stop the active classification run before changing taxonomy bindings."))
            if any(node.category_id and node.category_id.id != vals["category_id"] for node in self):
                raise UserError(_("An established taxonomy binding cannot be replaced. Correct the linked category structure instead."))
        result = super().write(vals)
        if 'description' in vals:
            self._sync_category_descriptions()
        if 'need_ids' in vals:
            self.env['product.template'].invalidate_model(['ab_shop_need_ids'])
            self.env['ab_product'].invalidate_model(['ab_shop_need_ids'])
        return result

    def _sync_category_descriptions(self):
        for node in self.filtered(lambda n: n.ready and n.description):
            value = '<p>%s</p>' % html_escape(node.description).replace('\n', '<br/>')
            if node.category_id.website_description != value:
                node.category_id.write({'website_description': value})

    def _ensure_default_descriptions(self):
        languages = self.env['res.lang'].search([('code', 'in', ['ar', 'ar_001'])])
        for node in self.with_context(lang='en_US').filtered(lambda n: not n.parent_id):
            default = ROOT_DESCRIPTIONS.get(node.key)
            if default:
                source = str(default)
                if not node.description:
                    node.description = source
                if node.description == source:
                    for language in languages:
                        translated = node.with_context(lang=language.code)
                        if not translated.description or translated.description == source:
                            translated.description = translated.env._(default)

    def unlink(self):
        raise AccessError(_("The approved taxonomy must be retained."))

    @api.model
    def action_prepare(self):
        check_manager(self.env)
        self.env["ab_product"]._lock_website_sync()
        if self.env["ab_product_classification_run"].sudo().search_count(fields.Domain("force_state", "in", ["queued", "running"])):
            raise UserError(_("Finish or stop the active classification operation first."))
        nodes = self.search([]).with_context(lang="en_US")
        nodes._ensure_default_descriptions()
        Category = self.env["product.public.category"].with_context(lang="en_US")
        categories = Category.search([])
        used = nodes.category_id
        problems = []
        for node in nodes.sorted(key=lambda n: (bool(n.parent_id), n.sequence, n.id)):
            parent = node.parent_id.category_id
            if node.parent_id and not parent:
                problems.append(node.name)
                continue
            if node.category_id:
                if not node.ready:
                    problems.append(node.name)
                continue
            names = {normalize(n) for n in (node.name, *CATEGORY_ALIASES.get(node.name, ()))}
            candidates = categories.filtered(lambda c: not c.website_id and normalize(c.name) in names)
            correct = candidates.filtered(lambda c: c.parent_id == parent and c not in used)
            exact = correct.filtered(lambda c: c.name == node.name)
            if len(exact) == 1 or len(correct) == 1:
                category = exact if len(exact) == 1 else correct
                if category.name != node.name:
                    category.name = node.name
            elif correct:
                problems.append(node.name)
                continue
            else:
                category = Category.create({"name": node.name, "parent_id": parent.id, "sequence": node.sequence})
                categories |= category
            node.category_id = category
            used |= category
        for lang in self.env["res.lang"].search([("code", "in", ["ar", "ar_001"])]):
            for node in nodes.filtered("ready"):
                translated = node.with_context(lang=lang.code).name
                if node.category_id.with_context(lang=lang.code).name != translated:
                    node.category_id.with_context(lang=lang.code).name = translated
        for language in ['en_US', *self.env['res.lang'].search([('code', 'in', ['ar', 'ar_001'])]).mapped('code')]:
            nodes.with_context(lang=language)._sync_category_descriptions()
        return {"ready": len(nodes.filtered("ready")), "total": len(nodes), "unresolved": problems}

    @api.model
    def _category_map(self):
        return {node.key: node for node in self.search([])}


class ClassificationRun(models.Model):
    _name = "ab_product_classification_run"
    _inherit = "ab_classification_audit"
    _description = "Product Classification Run"
    _order = "id desc"

    name = fields.Char(required=True, readonly=True)
    state = fields.Selection([(s, label) for s, label in (
        ("draft", "Draft"), ("queued", "Queued"), ("running", "Running"), ("paused", "Paused"),
        ("stopping", "Stopping"), ("stopped", "Stopped"), ("completed", "Completed"), ("failed", "Failed"),
    )], default="draft", required=True, index=True)
    scope = fields.Selection([("website", "Website Products"), ("all", "All Abdin Products")], required=True, default="website")
    website_id = fields.Many2one("website", ondelete="restrict")
    requested_by = fields.Many2one("res.users", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    total_products = fields.Integer()
    processed_products = fields.Integer()
    classified_products = fields.Integer()
    needs_review_count = fields.Integer()
    failed_count = fields.Integer()
    batch_size = fields.Integer(default=250)
    current_batch = fields.Integer()
    current_product = fields.Char()
    progress_percent = fields.Float(compute="_compute_progress")
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    paused_at = fields.Datetime()
    stopped_at = fields.Datetime()
    last_error = fields.Text()
    upper_id = fields.Integer()
    last_snapshot_id = fields.Integer()
    snapshot_done = fields.Boolean()
    checkpoint = fields.Integer()
    queue_uuid = fields.Char(index=True)
    engine_version = fields.Char(default=ENGINE_VERSION)
    result_ids = fields.One2many("ab_product_classification_result", "run_id")

    @api.depends("total_products", "processed_products", "state")
    def _compute_progress(self):
        for run in self:
            run.progress_percent = min(100, 100 * run.processed_products / run.total_products) if run.total_products else (100 if run.state == "completed" else 0)

    @api.model
    def _scope_model_domain(self, scope, website_id):
        if scope == "all":
            return self.env["ab_product"].with_context(active_test=False), fields.Domain.TRUE
        domain = fields.Domain("active", "=", True) & fields.Domain("sale_ok", "=", True)
        domain &= fields.Domain("website_id", "in", [False, website_id])
        return self.env["product.template"].with_context(active_test=False), domain

    @api.model
    def _catalog_domains(self, scope):
        """Live category coverage and never-attempted products, without loading IDs."""
        if scope == "website":
            categorized = fields.Domain("public_categ_ids", "!=", False)
            paths = ("", "ab_product_id.")
        else:
            categorized = fields.Domain("website_sync_template_ids.public_categ_ids", "!=", False)
            categorized |= fields.Domain("website_sync_template_ids", "=", False) & fields.Domain(
                "ab_classification_assignment_ids", "any",
                fields.Domain("node_id", "!=", False) & fields.Domain("mode", "!=", "ignored"),
            )
            paths = ("", "website_sync_template_ids.")
        handled = fields.Domain.FALSE
        reset = fields.Domain.FALSE
        for path in paths:
            handled |= fields.Domain(path + "ab_classification_result_ids", "any", fields.Domain("status", "in", ["classified", "needs_review", "failed"]))
            handled |= fields.Domain(path + "ab_classification_assignment_ids", "any", fields.Domain.TRUE)
            reset |= fields.Domain(
                path + "ab_classification_assignment_ids", "any",
                fields.Domain("mode", "=", "automatic") & fields.Domain("fingerprint", "=", False),
            )
        # Reset Manual Decision is an explicit request to allow another attempt.
        eligible = (~categorized & ~handled) | reset
        return categorized, eligible

    @api.model
    def dashboard(self, run_id=False, scope="website", website_id=False):
        check_manager(self.env)
        if scope not in ("website", "all"):
            raise ValidationError(_("Invalid product scope."))
        websites = self.env["website"].search([("company_id", "in", self.env.companies.ids)])
        website_id = website_id or websites[:1].id
        if website_id not in websites.ids:
            raise AccessError(_("Website is outside your allowed companies."))
        run_domain = fields.Domain("scope", "=", scope)
        if scope == "website":
            run_domain &= fields.Domain("website_id", "=", website_id)
        run = self.browse(run_id).exists() if run_id else self.search(run_domain, limit=1)
        run.check_access("read")
        Model, domain = self._scope_model_domain(scope, website_id)
        categorized, eligible = self._catalog_domains(scope)
        population = Model.search_count(domain)
        classified = Model.search_count(domain & categorized)
        nodes = self.env["ab_product_classification_taxonomy"].search([])
        return {
            "population": population, "website_id": website_id,
            "coverage": {
                "classified": classified, "unclassified": population - classified,
                "percent": 100 * classified / population if population else 0,
                "pending": Model.search_count(domain & eligible),
            },
            "websites": [{"id": w.id, "name": w.name} for w in websites],
            "taxonomy_ready": bool(nodes) and all(nodes.mapped("ready")),
            "run": run.get_status() if run else False,
        }

    @api.model
    def start_classification(self, scope="website", website_id=False, batch_size=250):
        check_manager(self.env)
        if scope not in ("website", "all") or type(batch_size) is not int or not 1 <= batch_size <= 250:
            raise ValidationError(_("Choose a valid scope and a batch size from 1 to 250."))
        dashboard = self.dashboard(scope=scope, website_id=website_id)
        if not dashboard["taxonomy_ready"]:
            raise UserError(_("Prepare and resolve all approved taxonomy bindings before starting."))
        if not self.env["ab_product"]._lock_website_sync(wait=False):
            raise UserError(_("A batch is being committed. Try again shortly."))
        if self.sudo().search_count(fields.Domain("state", "in", ["queued", "running", "paused", "stopping"]) | fields.Domain("force_state", "in", ["queued", "running"])):
            raise UserError(_("A classification run is already active. Resume or stop it first."))
        Model, domain = self._scope_model_domain(scope, dashboard["website_id"])
        domain &= self._catalog_domains(scope)[1]
        upper = Model.search(domain, order="id desc", limit=1).id
        if not upper:
            raise UserError(_("There are no new products to classify. Existing unresolved products remain in the review queue."))
        run = self._internal().create({
            "name": _("Product Classification %s", fields.Datetime.now()), "state": "queued", "scope": scope,
            "website_id": dashboard["website_id"], "company_id": self.env.company.id,
            "requested_by": self.env.uid, "total_products": Model.search_count(domain), "batch_size": batch_size,
            "upper_id": upper, "started_at": fields.Datetime.now(),
        })
        run._enqueue()
        return run.id

    def _enqueue(self):
        self.ensure_one()
        job = self.with_user(self.requested_by).with_delay(
            channel="root.classification", identity_key=f"classification:{self.id}:{self.checkpoint}",
            description=_("Product Classification %s", self.id), max_retries=10,
        )._process_checkpoint()
        self._internal().write({"queue_uuid": job.uuid})

    def _lock(self):
        self.ensure_one()
        self.check_access("read")
        if not self.try_lock_for_update(allow_referencing=True):
            raise UserError(_("A batch is being committed. Try again shortly."))
        self.invalidate_recordset()

    def action_pause(self):
        check_manager(self.env)
        return self._request_control("paused")

    def action_open_progress(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.client", "tag": "ab_product_classification", "name": _("Product Classification"), "params": {"run_id": self.id, "scope": self.scope, "website_id": self.website_id.id}}

    def action_stop(self):
        check_manager(self.env)
        return self._request_control("stopped")

    def _request_control(self, state):
        self.ensure_one()
        self.check_access("read")
        if not self.try_lock_for_update(allow_referencing=True):
            self.with_delay(channel="root.classification", priority=0, identity_key=f"classification-control:{self.id}:{state}")._apply_control(state)
            return False
        self.invalidate_recordset()
        self._apply_control(state)
        return True

    def _apply_control(self, state):
        check_manager(self.env)
        self.ensure_one()
        self.check_access("read")
        if not self.try_lock_for_update(allow_referencing=True):
            raise RetryableJobError(_("A batch is being committed. Try again shortly."), seconds=5, ignore_retry=True)
        self.invalidate_recordset()
        if state == "paused" and self.state in ("queued", "running"):
            self._internal().write({"state": "paused", "paused_at": fields.Datetime.now()})
        elif state == "stopped" and self.state in ("queued", "running", "paused", "failed"):
            self._internal().write({"state": "stopped", "stopped_at": fields.Datetime.now(), "finished_at": fields.Datetime.now()})

    def action_resume(self):
        check_manager(self.env)
        if not self.env["ab_product"]._lock_website_sync(wait=False):
            raise UserError(_("A batch is being committed. Try again shortly."))
        self._lock()
        if self.state not in ("paused", "stopped", "failed"):
            return True
        if self.sudo().search_count(fields.Domain("id", "!=", self.id) & fields.Domain("state", "in", ["queued", "running", "paused", "stopping"]) | fields.Domain("force_state", "in", ["queued", "running"])):
            raise UserError(_("Another classification run is active."))
        self._internal().write({"state": "queued", "checkpoint": self.checkpoint + 1, "last_error": False, "finished_at": False})
        self._enqueue()
        return True

    def _process_checkpoint(self):
        self.ensure_one()
        if not self.env["ab_product"]._lock_website_sync(wait=False) or not self.try_lock_for_update(allow_referencing=True):
            raise RetryableJobError(_("A batch is being committed. Try again shortly."), seconds=5, ignore_retry=True)
        self.invalidate_recordset()
        if self.state not in ("queued", "running"):
            return
        run = self._internal()
        try:
            with self.env.cr.savepoint():
                check_manager(self.env)
                if not self.requested_by.active or self.company_id not in self.requested_by.company_ids:
                    raise AccessError(_("The requester no longer has access to this company."))
                if self.env.context.get("job_uuid") and self.env.context["job_uuid"] != self.queue_uuid:
                    return
                run.state = "running"
                if not self.snapshot_done:
                    run._prepare_membership()
                else:
                    run._process_batch()
                run.checkpoint += 1
                if run.state == "running":
                    run._enqueue()
        except (SerializationFailure, DeadlockDetected):
            raise
        except Exception as error:
            _logger.exception("Classification run %s failed", self.id)
            run.write({"state": "failed", "last_error": str(error)[:2000], "finished_at": fields.Datetime.now()})

    def _prepare_membership(self):
        Model, domain = self._scope_model_domain(self.scope, self.website_id.id)
        domain &= self._catalog_domains(self.scope)[1]
        records = Model.search(domain & fields.Domain("id", ">", self.last_snapshot_id) & fields.Domain("id", "<=", self.upper_id), order="id", limit=1000)
        values = []
        for record in records:
            product = record if self.scope == "all" else record.ab_product_id
            template = record if self.scope == "website" else record.website_product_tmpl_id
            values.append({
                "run_id": self.id, "ab_product_id": product.id, "product_id": template.id,
                "product_key": f"ab:{product.id}" if product else f"template:{template.id}",
                "product_code": product.code if product else template.default_code,
                "product_name": (product.name or product.product_card_name) if product else template.name,
            })
        self.env["ab_product_classification_result"]._internal().create(values)
        if records:
            self.last_snapshot_id = records[-1].id
        if len(records) < 1000:
            self.write({"snapshot_done": True, "total_products": self.env["ab_product_classification_result"].search_count([("run_id", "=", self.id)])})

    def _process_batch(self):
        Result = self.env["ab_product_classification_result"]
        rows = Result.search([("run_id", "=", self.id), ("status", "=", "pending")], order="id", limit=self.batch_size)
        nodes = self.env["ab_product_classification_taxonomy"]._category_map()
        if not nodes or not all(n.ready for n in nodes.values()):
            raise UserError(_("Approved taxonomy bindings have changed. Resolve them before resuming."))
        assignments = self.env["ab_product_classification_assignment"].search([("product_key", "in", rows.mapped("product_key"))])
        by_key = {a.product_key: a for a in assignments}
        historical = historical_index()
        started = time.monotonic()
        processed = 0
        for row in rows:
            try:
                with self.env.cr.savepoint():
                    row._internal()._classify(nodes, historical, by_key.get(row.product_key))
            except (SerializationFailure, DeadlockDetected):
                raise
            except Exception as error:
                _logger.exception("Classification failed for %s", row.product_key)
                row._internal().write({"status": "failed", "method": "failed", "error_message": str(error)[:2000], "processed_at": fields.Datetime.now()})
            processed += 1
            self.current_product = row.product_name
            if time.monotonic() - started >= 40:
                break
        self.current_batch = processed
        self._refresh_counts()
        if not Result.search_count([("run_id", "=", self.id), ("status", "=", "pending")]):
            self.write({"state": "completed", "finished_at": fields.Datetime.now()})

    def _refresh_counts(self):
        counts = dict(self.env["ab_product_classification_result"]._read_group([("run_id", "=", self.id)], ["status"], ["__count"]))
        self._internal().write({"processed_products": sum(counts.get(k, 0) for k in ("classified", "needs_review", "failed")), "classified_products": counts.get("classified", 0), "needs_review_count": counts.get("needs_review", 0), "failed_count": counts.get("failed", 0)})

    def get_status(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access("read")
        counts = self.env["ab_product_classification_result"]._read_group([("run_id", "=", self.id)], ["root_id", "status"], ["__count"])
        by_root = {}
        for root, status, count in counts:
            by_root.setdefault(root.id, {})[status] = count
        roots = self.env["ab_product_classification_taxonomy"].search([("parent_id", "=", False)])
        return {
            "id": self.id, "name": self.name, "state": self.state, "state_label": dict(self._fields["state"]._description_selection(self.env))[self.state],
            "total": self.total_products, "processed": self.processed_products,
            "remaining": max(0, self.total_products - self.processed_products), "classified": self.classified_products,
            "needs_review": self.needs_review_count, "failed": self.failed_count, "percent": self.progress_percent,
            "current_batch": self.current_batch, "last_product": self.current_product or "", "error": self.last_error or "",
            "preparing": not self.snapshot_done, "scope": self.scope,
            "category_counts": [{"id": root.id, "name": root.name, "classified": by_root.get(root.id, {}).get("classified", 0), "needs_review": by_root.get(root.id, {}).get("needs_review", 0)} for root in roots],
            "unassigned_review": by_root.get(False, {}).get("needs_review", 0),
        }

    @api.model
    def _recover_interrupted(self):
        interrupted_controls = self.env["queue.job"].sudo().search([
            ("model_name", "=", self._name), ("method_name", "=", "_apply_control"),
            ("state", "=", "started"), ("date_started", "<", fields.Datetime.now() - timedelta(minutes=10)),
        ])
        for job in interrupted_controls:
            records = job.records.exists().sudo()
            if records and records.try_lock_for_update(allow_referencing=True):
                job.requeue()
        runs = self.sudo().search([("state", "in", ["queued", "running"])])
        for run in runs:
            if not run.try_lock_for_update():
                continue
            job = self.env["queue.job"].sudo().search([("uuid", "=", run.queue_uuid)], limit=1)
            if job.state == "failed":
                run._internal().write({"state": "failed", "last_error": _("The queue job failed. Inspect the queue and resume this run."), "finished_at": fields.Datetime.now()})
            elif job.state == "started" and job.date_started and job.date_started < fields.Datetime.now() - timedelta(minutes=10):
                job.requeue()
            elif not job or job.state in ("done", "cancelled"):
                run._internal().write({"checkpoint": run.checkpoint + 1})
                run._enqueue()


class ClassificationAssignment(models.Model):
    _name = "ab_product_classification_assignment"
    _inherit = "ab_classification_audit"
    _description = "Current Product Classification"
    _key_unique = models.Constraint("UNIQUE(product_key)", "A product can have only one current classification.")

    product_key = fields.Char(required=True, index=True)
    ab_product_id = fields.Many2one("ab_product", ondelete="restrict", index=True)
    product_id = fields.Many2one("product.template", ondelete="restrict", index=True)
    node_id = fields.Many2one("ab_product_classification_taxonomy", ondelete="restrict")
    mode = fields.Selection([("manual", "Manual"), ("automatic", "Automatic"), ("ignored", "Ignored"), ("forced", "Force Categorized")], required=True)
    result_id = fields.Many2one("ab_product_classification_result", ondelete="restrict")
    fingerprint = fields.Char()


class ClassificationResult(models.Model):
    _name = "ab_product_classification_result"
    _inherit = "ab_classification_audit"
    _description = "Product Classification Result"
    _rec_name = "product_name"
    _order = "id desc"
    _run_product_unique = models.Constraint("UNIQUE(run_id, product_key)", "A product can occur only once per run.")
    _pending_index = models.Index("(run_id, id) WHERE status = 'pending'")

    run_id = fields.Many2one("ab_product_classification_run", required=True, ondelete="restrict", index=True)
    ab_product_id = fields.Many2one("ab_product", ondelete="restrict", index=True)
    product_id = fields.Many2one("product.template", ondelete="restrict", index=True)
    product_key = fields.Char(required=True)
    product_code = fields.Char(index=True)
    product_name = fields.Char()
    current_categories = fields.Char()
    node_id = fields.Many2one("ab_product_classification_taxonomy", string="Primary Category", ondelete="restrict", index=True)
    root_id = fields.Many2one("ab_product_classification_taxonomy", compute="_compute_root", store=True, index=True)
    proposed_node_id = fields.Many2one("ab_product_classification_taxonomy", string="Review Category", ondelete="restrict")
    method = fields.Selection(METHODS)
    status = fields.Selection(STATUSES, default="pending", required=True, index=True)
    matched_terms = fields.Json()
    matched_rule = fields.Char()
    classification_reason = fields.Text()
    evidence = fields.Json()
    historical_evidence = fields.Json()
    source_url = fields.Char()
    source_title = fields.Char()
    search_query = fields.Char()
    research_provider = fields.Char()
    researched_at = fields.Datetime()
    confidence = fields.Float()
    error_message = fields.Text()
    processed_at = fields.Datetime()
    fingerprint = fields.Char()
    reused_result_id = fields.Many2one("ab_product_classification_result", ondelete="restrict")
    review_ids = fields.One2many("ab_product_classification_review", "result_id")
    ignored = fields.Boolean()

    @api.depends("node_id", "node_id.parent_id")
    def _compute_root(self):
        for result in self:
            result.root_id = result.node_id.parent_id or result.node_id

    def write(self, vals):
        if set(vals) == {"proposed_node_id"} and self.env.context.get("classification_internal") is not _INTERNAL:
            check_manager(self.env)
            self.check_access("write")
            return super(ClassificationResult, self._internal()).write(vals)
        return super().write(vals)

    def _facts(self):
        self.ensure_one()
        return product_facts(self.ab_product_id, self.product_id)

    def _classify(self, nodes, historical, assignment):
        self.status = "processing"
        facts = self._facts()
        fingerprint = hashlib.sha256(json.dumps([ENGINE_VERSION, facts], sort_keys=True).encode()).hexdigest()
        previous = assignment.result_id if assignment else self.browse()
        old = historical.get(normalize_code(facts["code"]), {})
        research = {}
        reused = False
        if assignment and assignment.mode in ("manual", "ignored", "forced"):
            node = assignment.node_id
            outcome = {"method": "forced" if assignment.mode == "forced" else "manual", "path": (), "confidence": previous.confidence if assignment.mode == "forced" else 1, "reason": "Explicit force categorization" if assignment.mode == "forced" else "Permanent manual decision", "ignored": assignment.mode == "ignored"}
        elif assignment and assignment.fingerprint == fingerprint and previous and previous.status == "classified":
            node = assignment.node_id
            outcome = dict(previous.evidence.get("outcome", {}))
            research = previous.evidence.get("research", {})
            reused = previous.id
        else:
            outcome = old if old.get("path") or old.get("blocked") else classify_local(facts)
            if not outcome.get("path") and not old.get("blocked"):
                research = self.env["ab_product_classification_research"]._research(facts)
                candidates = [classify_local({"description": source["title"] + " " + source["evidence"]}) for source in research.get("sources", [])]
                paths = {tuple(c["path"]) for c in candidates if c.get("path")}
                if len(paths) == 1:
                    outcome = dict(next(c for c in candidates if c.get("path")))
                    outcome.update(method="web_research", reason="Trusted web evidence matched deterministic rule: " + outcome["rule"])
                elif len(paths) > 1:
                    outcome = {"method": "needs_review", "reason": "Conflicting web evidence", "confidence": 0, "path": ()}
            node = nodes.get(taxonomy_key(outcome["path"])) if outcome.get("path") else None
        source = next((s for s in research.get("sources", []) if classify_local({"description": s["title"] + " " + s["evidence"]}).get("path") == tuple(outcome.get("path", ()))), {})
        ignored = outcome.get("ignored", False)
        research_error = research.get("error")
        if research_error == "Web research is not configured":
            research_error = self.env._("Web research is not configured")
        elif research_error:
            research_error = self.env._("Research provider request failed: %s", research_error.rsplit(": ", 1)[-1])
        self.write({
            "status": "classified" if node and not ignored else "needs_review", "method": outcome["method"],
            "node_id": node.id if node else False, "proposed_node_id": node.id if node else False,
            "confidence": outcome.get("confidence", 0), "matched_terms": outcome.get("terms", []), "matched_rule": outcome.get("rule"),
            "classification_reason": outcome_reason(self.env, outcome), "historical_evidence": old.get("historical", []),
            "evidence": {"facts": facts, "outcome": outcome, "research": research, "engine_version": ENGINE_VERSION},
            "current_categories": " | ".join(self.product_id.public_categ_ids.mapped("display_name")),
            "source_url": source.get("url"), "source_title": source.get("title"), "search_query": research.get("query"),
            "research_provider": research.get("provider"), "researched_at": research.get("timestamp"),
            "error_message": research_error, "processed_at": fields.Datetime.now(), "fingerprint": fingerprint,
            "reused_result_id": reused, "ignored": ignored,
        })
        if node and not ignored:
            self._assign(node, outcome["method"] if outcome["method"] in ("manual", "forced") else "automatic", assignment or self.env["ab_product_classification_assignment"])

    def _assign(self, node, mode, assignment=None):
        if not node.ready:
            raise UserError(_("The chosen category is not correctly bound to the approved taxonomy."))
        Assignment = self.env["ab_product_classification_assignment"]
        if assignment is None:
            assignment = Assignment.search([("product_key", "=", self.product_key)], limit=1)
        values = {"product_key": self.product_key, "ab_product_id": self.ab_product_id.id, "product_id": self.product_id.id, "node_id": node.id,
                  "mode": mode, "result_id": self.id, "fingerprint": self.fingerprint}
        if assignment:
            assignment._internal().write(values)
        else:
            Assignment._internal().create(values)
        templates = self.product_id or self.ab_product_id.website_product_tmpl_id
        if templates and templates.public_categ_ids != node.category_id:
            templates.sudo().write({"public_categ_ids": [fields.Command.set(node.category_id.ids)]})

    def action_accept(self):
        return self._review("accept")

    def action_ignore(self):
        return self._review("ignore")

    def action_reset_manual(self):
        return self._review("reset")

    def _review(self, decision):
        check_manager(self.env)
        self.ensure_one()
        self.check_access("write")
        self.env["ab_product"]._lock_website_sync()
        self.run_id._lock()
        if self.status not in ("classified", "needs_review", "failed"):
            raise UserError(_("Wait until this product has been processed."))
        Assignment = self.env["ab_product_classification_assignment"]
        assignment = Assignment.search([("product_key", "=", self.product_key)], limit=1)
        node = self.proposed_node_id or self.node_id
        if decision == "accept":
            if not node:
                raise UserError(_("Choose an approved category before accepting."))
            self._assign(node, "manual", assignment)
            self._internal().write({"node_id": node.id, "status": "classified", "method": "manual", "confidence": 1, "classification_reason": self.env._("Permanent manual decision"), "ignored": False})
        elif decision == "ignore":
            values = {"product_key": self.product_key, "ab_product_id": self.ab_product_id.id, "product_id": self.product_id.id, "node_id": False, "mode": "ignored", "result_id": self.id}
            if assignment:
                assignment._internal().write(values)
            else:
                Assignment._internal().create(values)
            self._internal().write({"node_id": False, "status": "needs_review", "method": "manual", "ignored": True})
        else:
            if assignment:
                assignment._internal().write({"mode": "automatic", "fingerprint": False})
            self._internal().write({"ignored": False})
        self.env["ab_product_classification_review"]._internal().create({"result_id": self.id, "decision": decision, "node_id": node.id if decision == "accept" else False, "reviewer_id": self.env.uid})
        self.run_id._refresh_counts()
        return True


class ClassificationReview(models.Model):
    _name = "ab_product_classification_review"
    _inherit = "ab_classification_audit"
    _description = "Product Classification Review Decision"
    _order = "id desc"

    result_id = fields.Many2one("ab_product_classification_result", required=True, ondelete="restrict", index=True)
    decision = fields.Selection([("accept", "Accepted"), ("ignore", "Ignored"), ("reset", "Manual Decision Reset"), ("force", "Force Categorized"), ("undo_force", "Force Categorization Undone")], required=True)
    node_id = fields.Many2one("ab_product_classification_taxonomy", ondelete="restrict")
    reviewer_id = fields.Many2one("res.users", required=True, ondelete="restrict")


class ClassificationResearch(models.Model):
    _name = "ab_product_classification_research"
    _inherit = "ab_classification_audit"
    _description = "Product Research Cache"
    _key_unique = models.Constraint("UNIQUE(cache_key)", "Research cache keys must be unique.")

    cache_key = fields.Char(required=True, index=True)
    payload = fields.Json()
    expires_at = fields.Datetime()

    @api.model
    def _provider(self):
        config = self.env["ir.config_parameter"].sudo()
        key = config.get_param("ab_classification.brave_api_key")
        domains = config.get_param("ab_classification.trusted_domains", "").split(",")
        return BraveResearchProvider(key, domains) if key and any(d.strip() for d in domains) else WebResearchProvider()

    @api.model
    def _research(self, facts):
        provider = self._provider()
        config = self.env["ir.config_parameter"].sudo()
        cache_key = hashlib.sha256(json.dumps([provider.name, provider.query(facts), config.get_param("ab_classification.trusted_domains", "")], sort_keys=True).encode()).hexdigest()
        cached = self.search([("cache_key", "=", cache_key)], limit=1)
        if cached and cached.expires_at > fields.Datetime.now():
            return cached.payload
        try:
            payload = provider.research(facts)
        except Exception as error:
            payload = {"provider": provider.name, "query": provider.query(facts), "sources": [], "error": "Research provider request failed: " + type(error).__name__}
        payload["timestamp"] = fields.Datetime.to_string(fields.Datetime.now())
        values = {"cache_key": cache_key, "payload": payload, "expires_at": fields.Datetime.now() + (timedelta(hours=1) if payload.get("error") else timedelta(days=30))}
        if cached:
            cached._internal().write(values)
        else:
            self._internal().create(values)
        return payload
