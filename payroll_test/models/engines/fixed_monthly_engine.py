from .base_engine import BasePayrollEngine

class FixedMonthlyEngine(BasePayrollEngine):
    
    def calculate_salaries(self):
        """Fixed Monthly System: Uses dynamic rules based on monthly agreement"""
        dynamic_results = self.evaluate_rules("fixed_monthly")
        if dynamic_results:
            return {
                'basic_salary': dynamic_results.get('basic_salary', 0.0),
                'allowance_nature_of_work': dynamic_results.get('allowance_nature_of_work', 0.0),
                'allowance_performance': dynamic_results.get('allowance_performance', 0.0),
                'allowance_cost_of_living': dynamic_results.get('allowance_cost_of_living', 0.0),
                'allowance_dedication': dynamic_results.get('allowance_dedication', 0.0),
                'total_basic_allowances': dynamic_results.get('total_basic_allowances', 0.0),
            }
        
        # Fallback: Monthly rate from employee
        emp = self.employee
        return {
            'basic_salary': emp.agreement_salary,
            'total_basic_allowances': 0.0,
        }

    def calculate_daily_hourly_values(self, basic_salary, total_basic_allowances, extra_allowances, working_days):
        """Fixed Monthly System: Based on 30 days or period days"""
        days = working_days or 30
        day_basic = basic_salary / days
        day_allowances = (total_basic_allowances + extra_allowances) / days
        
        hours = self.employee.working_hours_per_day or 8.0
        hour_basic = day_basic / hours
        hour_allowances_basic = (total_basic_allowances / days) / hours
        
        return {
            'day_basic': day_basic,
            'day_allowances': day_allowances,
            'day_total': day_basic + day_allowances,
            'hour_basic': hour_basic,
            'hour_allowances': hour_allowances_basic,
            'hour_total': hour_basic + hour_allowances_basic,
        }

    def calculate_payslip(self, structure, attendances):
        """Fixed Monthly System: Full salary unless absent"""
        required_days = structure.working_days_in_period or 30
        actual_days = len(attendances.filtered(lambda a: a.working_hours > 0))
        
        # In fixed system, we often pay full if attendance is good
        # But we can also use dynamic rules for the payslip too
        dynamic_results = self.evaluate_rules("fixed_monthly", initial_localdict={
            'structure': structure,
            'attendances': attendances,
            'actual_days': actual_days,
            'required_days': required_days,
        })
        
        if dynamic_results:
            return dynamic_results

        # Default fallback logic
        total_absence = sum(attendances.mapped('absence_days'))
        absence_deduction = total_absence * structure.day_basic
        
        salary_basic = structure.basic_salary - absence_deduction
        
        return {
            'salary_basic': salary_basic,
            'allowances_basic_four': structure.total_basic_allowances,
            'extra_allowances': structure.extra_allowances,
            'total_deductions': self.employee.social_insurance + self.employee.health_insurance,
        }
