def migrate(cr, version):
    cr.execute(
        """
            DELETE FROM ir_model_data AS legacy
                  USING ir_model_data AS current
             WHERE legacy.module = 'ab_hr'
               AND legacy.name = 'group_ab_hr_manpower_hour_need'
               AND current.module = 'ab_manpower_need'
               AND current.name = legacy.name
               AND current.model = legacy.model
               AND current.res_id = legacy.res_id
        """
    )
    cr.execute(
        """
            UPDATE ir_model_data AS legacy
               SET module = 'ab_manpower_need'
             WHERE legacy.module = 'ab_hr'
               AND legacy.name = 'group_ab_hr_manpower_hour_need'
               AND NOT EXISTS (
                    SELECT 1
                      FROM ir_model_data AS current
                     WHERE current.module = 'ab_manpower_need'
                       AND current.name = legacy.name
               )
        """
    )
