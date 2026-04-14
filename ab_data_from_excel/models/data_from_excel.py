import enum

from odoo import api, fields, models
from odoo.tools.translate import _
from collections import namedtuple
from odoo.exceptions import ValidationError, UserError
import csv
from datetime import datetime


class DataFromExcel(models.AbstractModel):
    _name = 'ab_data_from_excel'
    _description = 'DataFromExcel'

    def data_from_excel(self, model_name, x2many_field, excel_data, update_only=False):
        def get_fld_strings(model_name, field_name):
            model = self.env[model_name]
            user_lang = model.fields_get([field_name])[field_name]['string'].lower()
            en_lang = model.with_context(lang='en_US').fields_get([field_name])[field_name]['string'].lower()
            FieldPossible = namedtuple('FieldPossible', 'field_name, user_lang, en_lang')
            return FieldPossible(field_name, user_lang, en_lang)

        def _check_has_ro_flds(flds):
            fields_mo = self.env['ir.model.fields'].sudo()
            for fld in flds:
                field_line = fields_mo.search([('model', '=', model_name), ('name', '=', fld)])
                if field_line.readonly:
                    raise ValidationError(_(f"Field {field_line.name} is readonly"))

        def _get_fld_val(fld, val):
            line_fields = self.env[model_name]._fields

            field = line_fields[fld]
            field_type = field.__class__.__name__
            try:
                val = val.strip() if isinstance(val, str) else val
                if field_type == 'Many2one' and val:
                    comodel = field.comodel_name
                    # search for whole value
                    ids = self.env[comodel]._name_search(name=val, operator='=', limit=2)
                    recs = self.env[comodel].browse(ids)
                    # return models.lazy_name_get(recs.with_user(name_get_uid))

                    many2one_val = models.lazy_name_get(recs)
                    if not many2one_val:
                        if isinstance(val, str):
                            val = val.strip()
                        ids = self.env[comodel]._name_search(name=val, operator='ilike', limit=2)
                        recs = self.env[comodel].browse(ids)
                        many2one_val = models.lazy_name_get(recs)

                    if many2one_val:
                        # if one unique value
                        if len(many2one_val) == 1:
                            new_val = many2one_val[0][0]
                        # if multiple values then Error (e.g. كهرباء, مولد كهرباء)
                        else:
                            raise ValidationError(f"value - {val} - may reference to more than one field")
                    else:
                        raise ValidationError(f"value - {val} not found")
                elif field_type == 'Date':
                    try:
                        new_val = datetime.strptime(val, '%d-%m-%Y')
                    except ValueError:
                        try:
                            new_val = datetime.strptime(val, '%Y-%m-%d')
                        except ValueError:
                            try:
                                new_val = datetime.strptime(val, '%d/%m/%Y')
                            except:
                                raise ValidationError("Date format must be d-m-yyyy")

                elif field_type == 'Selection':
                    try:
                        selection = getattr(field, 'selection', 'Not Found')
                        new_val = ""
                        for t in selection:
                            if t[0].lower() == val.lower() or t[1].lower() == val.lower():
                                new_val = t[0]
                                break
                    except Exception as ex:
                        raise ValidationError(f"{type(ex)}: {str(ex)}")

                elif field_type in {'Float', 'Integer'}:
                    new_val = val.replace(',', '')
                else:
                    new_val = val or None
                return new_val
            except Exception as ex:
                raise UserError(_("Data Type Error:"
                                  f"{str(ex)}"))

        def get_field_names_from_headers(headers):

            line_fields = self.env[model_name]._fields
            field_strings_possibility = [get_fld_strings(model_name, field_name) for field_name in line_fields]

            headers_to_fields = []

            for header in headers:
                field_name = [strings.field_name
                              for strings in field_strings_possibility if header.lower().strip() in strings]

                if field_name:
                    headers_to_fields.append(field_name[0])
                else:
                    raise ValidationError(f"header {header} not found.")
            return headers_to_fields

        try:
            dialect = csv.Sniffer().sniff(excel_data)
            deli = dialect.delimiter
            rows = ((row.strip().split(deli)) for row in excel_data.split('\n'))
            headers = next(rows)

            flds = get_field_names_from_headers(headers)
            _check_has_ro_flds(flds)
            if not update_only:
                self.write({x2many_field: [
                    (0, 0, {fld: _get_fld_val(fld, val) for fld, val in zip(flds, row)})
                    for row in rows]})
            else:
                self.write({x2many_field: [
                    (1, rec.id, {fld: _get_fld_val(fld, val) for fld, val in zip(flds, next(rows))})
                    for rec in getattr(self, x2many_field, [])
                ]})

        except csv.Error:
            raise ValidationError("Invalid Excel Data!")
        except TypeError as e:
            raise ValidationError(str(e))
        except Exception as ex:
            raise UserError(_("Data Type Error:"
                              f"{str(ex)}"))
