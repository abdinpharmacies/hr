def _table_exists(cr, table_name):
    cr.execute("SELECT to_regclass(%s)", (table_name,))
    return bool(cr.fetchone()[0])


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def _fallback_required_job_id(cr):
    cr.execute("SELECT id FROM ab_required_job WHERE name = %s ORDER BY id LIMIT 1", ("غير محدد",))
    row = cr.fetchone()
    if row:
        return row[0]
    cr.execute("SELECT id FROM ab_required_job ORDER BY id LIMIT 1")
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not _table_exists(cr, "ab_hr_application"):
        return
    if not _table_exists(cr, "ab_required_job"):
        return
    if not _column_exists(cr, "ab_hr_application", "required_job_id"):
        return

    # Legacy compatibility: backfill from old column if it still exists.
    if _column_exists(cr, "ab_hr_application", "job_id"):
        # Case A: legacy job_id already stored required_job_id values.
        cr.execute(
            """
            UPDATE ab_hr_application a
            SET required_job_id = a.job_id
            WHERE a.required_job_id IS NULL
              AND EXISTS (
                  SELECT 1 FROM ab_required_job r WHERE r.id = a.job_id
              )
            """
        )
        # Case B: legacy job_id stored ab_hr_job IDs.
        cr.execute(
            """
            UPDATE ab_hr_application a
            SET required_job_id = r.id
            FROM ab_required_job r
            WHERE a.required_job_id IS NULL
              AND a.job_id = r.job_id
            """
        )

    fallback_id = _fallback_required_job_id(cr)
    if fallback_id:
        cr.execute(
            """
            UPDATE ab_hr_application
            SET required_job_id = %s
            WHERE required_job_id IS NULL
            """,
            (fallback_id,),
        )
