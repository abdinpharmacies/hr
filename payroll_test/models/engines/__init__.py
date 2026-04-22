from .base_engine import BasePayrollEngine
from .daily_hours_engine import DailyHoursEngine
from .fixed_monthly_engine import FixedMonthlyEngine


ENGINE_TYPES = [
    ('daily_hours', 'Daily Hours System'),
    ('monthly', 'Fixed Monthly System'),
    ('daily_wage', 'Daily Wage System'),
    ('hybrid', 'Hybrid System'),
]

ENGINE_REGISTRY = {
    'daily_hours': DailyHoursEngine,
    'monthly': FixedMonthlyEngine,
}


def get_engine(record):
    """
    Central resolver for payroll engines.

    To add a new sheet/system type later:
    1. Create a new engine class in this package.
    2. Register it in ENGINE_REGISTRY with the new selection key.
    """
    employee = getattr(record, 'employee_id', False)
    system_code = getattr(employee, 'payroll_type', 'daily_hours') if employee else 'daily_hours'
    engine_class = ENGINE_REGISTRY.get(system_code)
    return engine_class(record) if engine_class else None
