from odoo.addons.web.controllers.export import ExcelExport

from ..models.costcenter import HR_IDENTITY_FIELDS


class HRExcelExport(ExcelExport):
    def from_group_data(self, fields, columns_headers, groups):
        # Group labels are written separately from the exported record columns.
        for groupby in groups._groupby:
            *relations, name = groupby.partition(':')[0].split('.')
            if name not in HR_IDENTITY_FIELDS:
                continue
            model = groups._model
            for relation in relations:
                comodel = getattr(model._fields.get(relation), 'comodel_name', None)
                if not comodel:
                    break
                model = model.env[comodel]
            else:
                if model._name in ('ab_costcenter', 'ab_hr_employee'):
                    model.env['ab_costcenter']._check_hr_identity_export([name])
        return super().from_group_data(fields, columns_headers, groups)
