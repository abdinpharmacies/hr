from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class BasePayrollEngine:
    def __init__(self, record):
        """
        :param record: Either a salary structure or a payslip record
        """
        self.record = record
        self.env = record.env
        self.employee = record.employee_id
        if hasattr(record, 'period_id'):
            self.period = record.period_id
        else:
            self.period = None

    def evaluate_rules(self, system_code=None, initial_localdict=None):
        """
        Evaluates dynamic rules.
        :param system_code: Optional policy type or name of the payroll rule system.
                           If None, uses employee.payroll_rule_system_id
        """
        system = None
        if system_code:
            system = self.env['payroll.rule.system'].search([
                '|',
                ('policy_type', '=', system_code),
                ('name', '=', system_code),
            ], limit=1)
        elif self.employee and self.employee.payroll_rule_system_id:
            system = self.employee.payroll_rule_system_id

        if not system:
            return {}

        localdict = initial_localdict or {}
        localdict.update({
            'employee': self.employee,
            'record': self.record,
            'period': self.period,
            'env': self.env,
            # Context Variables (Smart Mapping)
            'agreement_salary': getattr(self.record, 'agreement_salary', self.employee.agreement_salary),
            'contractual_hours': self.employee.working_hours_per_day,
            'worked_hours': getattr(self.record, 'working_hours', 0.0),
            'absence_days': getattr(self.record, 'absence_days', 0.0),
        })

        results = {}
        for rule in system.rule_ids:
            try:
                # Rule can access previous rules' results
                val = safe_eval(rule.equation, localdict)
                localdict[rule.code] = val
                results[rule.code] = val
            except Exception as e:
                # Log error or handle gracefully
                results[rule.code] = 0.0
        
        return results

    def calculate_salaries(self):
        """Logic to compute basic salary and allowances in structure"""
        pass

    def calculate_daily_hourly_values(self):
        """Logic to compute daily and hourly rates in structure"""
        pass

    def calculate_forget_penalty(self):
        """Logic to compute forget fingerprint penalty in structure"""
        pass

    def calculate_payslip(self):
        """Logic to compute final payslip values"""
        pass
