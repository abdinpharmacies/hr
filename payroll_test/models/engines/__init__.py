from .base_engine import BasePayrollEngine
from .daily_hours_engine import DailyHoursEngine
from .fixed_monthly_engine import FixedMonthlyEngine


ENGINE_TYPES = [
    ('daily_hours', 'نظام ساعات يومية'),
    ('monthly', 'نظام راتب شهري ثابت'),
    ('daily_wage', 'نظام أجر يومي'),
    ('hybrid', 'نظام هجين (شهري + ساعاتي)'),
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
    system_code = getattr(employee, 'payroll_system', False) if employee else False
    engine_class = ENGINE_REGISTRY.get(system_code)
    return engine_class(record) if engine_class else None
