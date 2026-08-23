# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbCharAutocompleteService(models.AbstractModel):
    _name = "ab.char.autocomplete.service"
    _description = "Char Autocomplete Suggestions"

    _MAX_LIMIT = 80
    _MAX_OFFSET = 10000
    _MAX_TERM_LENGTH = 200

    @api.model
    @api.readonly
    def get_suggestions(self, model_name, field_name, search_term="", current_id=False, limit=7, offset=0):
        Model, field = self._validate_request(model_name, field_name)
        limit = self._clamp_int(limit, 7, 1, self._MAX_LIMIT)
        offset = self._clamp_int(offset, 0, 0, self._MAX_OFFSET)
        search_term = str(search_term or "")[:self._MAX_TERM_LENGTH]
        current_id = self._clean_current_id(current_id)

        domain = fields.Domain(field_name, "!=", False) & fields.Domain(field_name, "!=", "")
        if search_term:
            domain &= fields.Domain(field_name, "ilike", search_term)
        if current_id:
            domain &= fields.Domain("id", "!=", current_id)

        rows = Model._read_group(
            domain,
            groupby=[field_name],
            aggregates=["id:max"],
            order="id:max DESC",
            limit=limit + 1,
            offset=offset,
        )
        values = [
            {"value": value, "latest_id": latest_id}
            for value, latest_id in rows[:limit]
            if value
        ]
        return {
            "values": values,
            "has_more": len(rows) > limit,
            "offset": offset,
            "limit": limit,
        }

    def _validate_request(self, model_name, field_name):
        model_name = str(model_name or "").strip()
        field_name = str(field_name or "").strip()
        if not model_name or model_name not in self.env.registry.models:
            raise UserError(_("Invalid model for char autocomplete suggestions."))

        Model = self.env[model_name]
        Model.browse().check_access("read")
        field = Model._fields.get(field_name)
        if not field or field.type != "char" or not field.store:
            raise UserError(_("Invalid field for char autocomplete suggestions."))

        Model._check_field_access(field, "read")
        return Model, field

    def _clamp_int(self, value, default, minimum, maximum):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(value, maximum))

    def _clean_current_id(self, current_id):
        try:
            current_id = int(current_id or 0)
        except (TypeError, ValueError):
            return False
        return current_id if current_id > 0 else False
