# -*- coding: utf-8 -*-


_LEGACY_EXACT_XMLIDS = (
    "group_ab_hr_payroll_sheet_admin",
    "field_ab_hr_employee__telegram_chat_id",
    "field_ab_hr_employee__telegram_user_id",
    "field_ab_hr_employee__telegram_username",
    "field_ab_hr_employee__telegram_linked_at",
)

_LEGACY_XMLID_PREFIXES = (
    "model_ab_hr_payroll_sheet",
    "model_inherit__ab_hr_payroll_sheet",
    "field_ab_hr_payroll_sheet",
    "selection__ab_hr_payroll_sheet",
    "view_ab_hr_payroll_sheet",
    "action_ab_hr_payroll_sheet",
    "menu_ab_hr_payroll_sheet",
    "access_ab_hr_payroll_sheet",
    "ir_cron_ab_hr_payroll_sheet",
    "ir_cron_ab_hr_employee_telegram_import",
)


def transfer_legacy_metadata(cr):
    """Transfer payroll metadata without loading the referenced business rows."""
    prefix_clauses = " OR ".join("legacy.name LIKE %s" for _prefix in _LEGACY_XMLID_PREFIXES)
    selection_params = [list(_LEGACY_EXACT_XMLIDS)]
    selection_params.extend(f"{prefix}%" for prefix in _LEGACY_XMLID_PREFIXES)
    cr.execute(
        f"""
            DELETE FROM ir_model_data AS legacy
                  USING ir_model_data AS current
             WHERE legacy.module = %s
               AND current.module = %s
               AND current.name = legacy.name
               AND current.model = legacy.model
               AND current.res_id = legacy.res_id
               AND (
                    legacy.name = ANY(%s)
                    OR {prefix_clauses}
               )
        """,
        ["ab_hr", "ab_payroll", *selection_params],
    )
    cr.execute(
        f"""
            UPDATE ir_model_data AS legacy
               SET module = %s
             WHERE legacy.module = %s
               AND (
                    legacy.name = ANY(%s)
                    OR {prefix_clauses}
               )
               AND NOT EXISTS (
                    SELECT 1
                      FROM ir_model_data AS current
                     WHERE current.module = 'ab_payroll'
                       AND current.name = legacy.name
               )
        """,
        ["ab_payroll", "ab_hr", *selection_params],
    )


def pre_init_hook(env):
    """Transfer legacy metadata ownership before installing the split module."""
    transfer_legacy_metadata(env.cr)
