"""Preserve Odoo 15 XML IDs while moving payroll data out of ab_hr."""

from .legacy_ids import MOVED_XML_IDS


def pre_init_hook(env):
    """Give existing records new owning IDs and retain old IDs as aliases.

    This runs only when ab_hr_payroll is first installed.  It precedes XML
    loading and Odoo's end-of-upgrade removal of obsolete ab_hr data.
    """
    cr = env.cr
    cr.execute(
        """SELECT id, name, model, res_id, noupdate
           FROM ir_model_data
           WHERE module = 'ab_hr' AND name = ANY(%s)""",
        (MOVED_XML_IDS,),
    )
    old_records = cr.fetchall()
    for old_id, name, model, res_id, _noupdate in old_records:
        cr.execute(
            """SELECT res_id FROM ir_model_data
               WHERE module = 'ab_hr_payroll' AND name = %s""",
            (name,),
        )
        existing = cr.fetchone()
        if existing:
            if existing[0] != res_id:
                raise ValueError(
                    "Payroll XML ID collision for %s: %s versus %s"
                    % (name, existing[0], res_id)
                )
            continue
        cr.execute(
            """UPDATE ir_model_data SET module = 'ab_hr_payroll'
               WHERE id = %s""",
            (old_id,),
        )
        cr.execute(
            """INSERT INTO ir_model_data
               (module, name, model, res_id, noupdate, create_date, write_date)
               VALUES ('ab_hr', %s, %s, %s, true, now(), now())""",
            (name, model, res_id),
        )


def post_init_hook(env):
    """Provide legacy XML ID aliases on new installations as well."""
    cr = env.cr
    cr.execute(
        """INSERT INTO ir_model_data
           (module, name, model, res_id, noupdate, create_date, write_date)
           SELECT 'ab_hr', current.name, current.model, current.res_id,
                  true, now(), now()
           FROM ir_model_data AS current
           WHERE current.module = 'ab_hr_payroll'
             AND current.name = ANY(%s)
             AND NOT EXISTS (
                 SELECT 1 FROM ir_model_data AS legacy
                 WHERE legacy.module = 'ab_hr' AND legacy.name = current.name
             )""",
        (MOVED_XML_IDS,),
    )
