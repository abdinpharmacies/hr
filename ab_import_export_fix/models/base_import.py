# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools.translate import _


class BaseImportImport(models.TransientModel):
    _inherit = 'base_import.import'

    def get_fields_tree(self, model, depth=3):
        fields_tree = super().get_fields_tree(model, depth=depth)
        if not any(field.get('name') == '.id' for field in fields_tree):
            fields_tree.insert(1, {
                'id': '.id',
                'name': '.id',
                'string': _('Database ID'),
                'required': False,
                'fields': [],
                'type': 'id',
                'model_name': model,
            })
        return fields_tree
