from odoo import fields, models


class LegalDocumentNotes(models.Model):
    _name = "ab_visit_report_legal_document_notes"
    _description = "Legal Document Notes"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
