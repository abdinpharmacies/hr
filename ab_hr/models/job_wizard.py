from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import UserError as Warning


class JobWizard(models.TransientModel):
    _name = 'ab_hr_job_wizard'
    _description = 'JobWizard'

    action_type = fields.Many2one('ab_hr_history_action_type', required=True)
    action_date = fields.Date(required=True)

    invisible_job_title = fields.Boolean(related='action_type.invisible_job_title')
    invisible_workplace = fields.Boolean(related='action_type.invisible_workplace')
    invisible_job_id = fields.Boolean(related='action_type.invisible_job_id')
    action_type_type = fields.Selection(related='action_type.type')
    manpower_effect = fields.Boolean(related='action_type.manpower_effect')
    action_date_type = fields.Selection(related='action_type.action_date_type')
    type_of_action = fields.Char()

    employee_id = fields.Many2one('ab_hr_employee')
    accid = fields.Char(related='employee_id.accid')
    job_id = fields.Many2one('ab_hr_job_occupied')
    alt_job_id = fields.Many2one('ab_hr_emp_history')
    manpower_id = fields.Many2one('ab_hr_manpower')
    cur_job_title = fields.Many2one(related='job_id.job_id', string='Current Job Title')
    cur_workplace = fields.Many2one(related='job_id.workplace', string='Current Workplace')
    workplace = fields.Many2one('ab_hr_department')
    job_title = fields.Many2one('ab_hr_job')
    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')])
    attached_file = fields.Binary()
    notes = fields.Text()

    def action_save(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_hr_jobwizard(values)
        return records

    def _create_one_ab_hr_jobwizard(self, vals):
        # 1:new_job, 2:modify_job, 3:new,manpower, 4:modify_manpower
        # if not (self.env.user.has_group("ab_hr.group_ab_hr_co")
        #         or self.env.user.has_group("ab_hr.group_ab_hr_personnel_spec")):
        if not self.env.user.has_group("ab_hr.group_ab_hr_co"):
            raise UserError(_("YOU ARE NOT ALLOWED TO DO THIS ACTION"))
        res = super().create(vals)
        action_type = self.env['ab_hr_history_action_type'].browse(vals['action_type'])

        if action_type.type in ['1']:
            job_id = self.job_create(vals)
            vals['job_id'] = job_id.id
            self.history_new_job(vals)

        elif action_type.type in ['2']:
            self.job_write(vals)
            self.history_mod_job(vals)

        elif action_type.type in ['3']:
            self.manpower_create(vals)
            self.history_new_job(vals)

        elif action_type.type in ['4']:
            manpower = self.env['ab_hr_manpower'].sudo()
            manpower_id = manpower.browse(vals['manpower_id'])
            vals['manpower_op_manpower'] = manpower_id.op_manpower
            self.manpower_write(vals)
            self.history_new_job(vals)

        return res

    # JOB_CREATE #####################################################
    def job_create(self, vals):

        job_occupied = self.env['ab_hr_job_occupied'].sudo()
        job_id = {'employee_id': vals['employee_id'], 'workplace': vals['workplace'],
                  'job_id': vals['job_title'], 'territory': vals['territory'],
                  'hiring_date': vals['action_date']}

        self.check_manpower_permission(vals)

        return job_occupied.create(job_id)

    # JOB_WRITE #####################################################
    def job_write(self, vals):

        self.check_manpower_permission(vals)

        job_occupied = self.env['ab_hr_job_occupied'].sudo()
        job_id = job_occupied.browse(vals['job_id'])
        vals['history_old_workplace'] = job_id.workplace.id
        vals['history_old_job_title'] = job_id.job_id.id
        vals['history_old_territory'] = job_id.territory

        if vals.get('workplace', None):
            job_id.workplace = vals['workplace']
        if vals.get('job_title', None):
            job_id.job_id = vals['job_title']
        if vals.get('territory', None):
            job_id.territory = vals['territory']

        # # write job new data
        # job_id.workplace = vals['workplace']
        # job_id.job_id = vals['job_title']
        # job_id.territory = vals['territory']

        action_date_type = self.env['ab_hr_history_action_type'].browse(vals['action_type']).action_date_type
        if action_date_type == 'firing':
            manager = job_id.workplace.manager_id
            if manager.id == job_id.employee_id.id:
                job_id.workplace.manager_id = False
            job_id.termination_date = vals['action_date']
            job_id.workplace._compute_manager_id()

        elif action_date_type == 'hiring':
            job_id.hiring_date = vals['action_date']

        elif action_date_type == 'clear_firing':
            job_id.termination_date = False
            job_id.workplace._compute_manager_id()

    # MANPOWER_CREATE #####################################################
    def manpower_create(self, vals):

        self.env['ab_hr_manpower'].sudo().create({
            'workplace': vals.get('workplace', None),
            'job_title': vals.get('job_title', None),
            'territory': vals.get('territory', None),
            'op_manpower': 1,
        })

    # MANPOWER_WRITE #####################################################
    def manpower_write(self, vals):

        action_date_type = self.env['ab_hr_history_action_type'].browse(vals['action_type']).action_date_type
        if action_date_type == 'hiring':
            req_manpower = vals['manpower_op_manpower'] + 1
        elif action_date_type == 'firing':
            req_manpower = vals['manpower_op_manpower'] - 1
        else:
            req_manpower = vals['manpower_op_manpower']

        manpower = self.env['ab_hr_manpower'].sudo()
        manpower_id = manpower.browse(vals['manpower_id'])
        manpower_id.write({
            'op_manpower': req_manpower,
        })

    # HISTORY_CREATE #####################################################
    def history_new_job(self, vals):

        emp_history = self.env['ab_hr_emp_history'].sudo()
        history_id = {'employee_id': vals.get('employee_id', None),
                      'job_id': vals.get('job_id', None),
                      'action_date': vals.get('action_date', None),
                      'action_type': vals.get('action_type', None),
                      'notes': vals.get('notes', None),
                      'attached_file': vals.get('attached_file', None),
                      'old_workplace': vals.get('workplace', None),
                      'old_job_title': vals.get('job_title', None),
                      'territory': vals.get('territory', None),
                      'alt_job_id': vals.get('alt_job_id', None),
                      }

        res = emp_history.sudo().create(history_id)
        self.env['ab_hr_emp_history'].browse(vals.get('alt_job_id', None)).sudo().write({'alt_job_id': res.id})

    # HISTORY_CREATE #####################################################
    def history_mod_job(self, vals):

        emp_history = self.env['ab_hr_emp_history'].sudo()
        history_id = {'employee_id': vals.get('employee_id', None),
                      'job_id': vals.get('job_id', None),
                      'action_date': vals.get('action_date', None),
                      'action_type': vals.get('action_type', None),
                      'notes': vals.get('notes', None),
                      'attached_file': vals.get('attached_file', None),
                      'old_workplace': vals.get('history_old_workplace', None),
                      'old_job_title': vals.get('history_old_job_title', None),
                      'territory': vals.get('history_old_territory', None),
                      'new_workplace': vals.get('workplace', None),
                      'new_job_title': vals.get('job_title', None),
                      'new_territory': vals.get('territory', None),
                      }

        emp_history.sudo().create(history_id)

    def check_manpower_permission(self, vals):
        is_excluded = self.env.user.has_group("ab_hr.group_ab_hr_manager")

        job_id = self.env['ab_hr_job_occupied'].sudo().browse(vals['job_id'])
        workplace = vals.get('workplace', None) or job_id.workplace.id
        territory = vals.get('territory', None) or job_id.territory
        job_title = vals.get('job_title', None) or job_id.job_id.id
        need_manpower_model = self.env['ab_hr_manpower_need'].sudo().with_context(active_test=False).search([
            ('workplace', '=', workplace),
            ('job_title', '=', job_title),
            ('territory', '=', territory),
        ])

        need_manpower = need_manpower_model.need_manpower
        action_type = self.env['ab_hr_history_action_type'].browse(vals['action_type'])
        affect_manpower = not action_type.invisible_job_title or not action_type.invisible_workplace

        if need_manpower >= 0 and not is_excluded and affect_manpower:
            raise UserError(_("NO REQUIRED JOB FOR THIS WORKPLACE/TERRITORY"))
