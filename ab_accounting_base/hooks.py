"""Transfer shared accounting XML IDs without copying existing rows."""

from .legacy_ids import MOVED_XML_IDS


def pre_init_hook(env):
    cr = env.cr
    cr.execute(
        """SELECT id, name, model, res_id FROM ir_model_data
           WHERE module = 'ab_accounting' AND name = ANY(%s)""",
        (MOVED_XML_IDS,),
    )
    for old_id, name, model, res_id in cr.fetchall():
        cr.execute(
            """SELECT res_id FROM ir_model_data
               WHERE module = 'ab_accounting_base' AND name = %s""",
            (name,),
        )
        existing = cr.fetchone()
        if existing:
            if existing[0] != res_id:
                raise ValueError(
                    "Account catalog XML ID collision: %s" % name
                )
            continue
        cr.execute(
            """UPDATE ir_model_data SET module = 'ab_accounting_base'
               WHERE id = %s""",
            (old_id,),
        )
        cr.execute(
            """INSERT INTO ir_model_data
               (module, name, model, res_id, noupdate, create_date, write_date)
               VALUES ('ab_accounting', %s, %s, %s, true, now(), now())""",
            (name, model, res_id),
        )


def post_init_hook(env):
    """Provide legacy references even on a fresh base-only installation."""
    cr = env.cr
    cr.execute(
        """INSERT INTO ir_model_data
           (module, name, model, res_id, noupdate, create_date, write_date)
           SELECT 'ab_accounting', current.name, current.model,
                  current.res_id, true, now(), now()
           FROM ir_model_data AS current
           WHERE current.module = 'ab_accounting_base'
             AND current.name = ANY(%s)
             AND NOT EXISTS (
                 SELECT 1 FROM ir_model_data AS legacy
                 WHERE legacy.module = 'ab_accounting'
                   AND legacy.name = current.name
             )""",
        (MOVED_XML_IDS,),
    )
