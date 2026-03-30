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


def _max_code_number(cr):
    cr.execute(
        """
        SELECT COALESCE(MAX((regexp_match(code, '^app/([0-9]+)$'))[1]::int), 0)
        FROM ab_hr_application
        WHERE code ~ '^app/[0-9]+$'
        """
    )
    row = cr.fetchone()
    return int(row[0] or 0)


def migrate(cr, version):
    if not _table_exists(cr, "ab_hr_application"):
        return
    if not _column_exists(cr, "ab_hr_application", "code"):
        return

    # Prefer app/<mssql_app_id> for legacy imported rows when unique.
    if _column_exists(cr, "ab_hr_application", "mssql_app_id"):
        cr.execute(
            """
            UPDATE ab_hr_application a
            SET code = 'app/' || a.mssql_app_id::text
            WHERE (a.code IS NULL OR a.code = '')
              AND a.mssql_app_id IS NOT NULL
              AND a.mssql_app_id > 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM ab_hr_application x
                  WHERE x.code = 'app/' || a.mssql_app_id::text
                    AND x.id <> a.id
              )
            """
        )

    # Fill remaining rows with incremental app/<number> from current max.
    cr.execute(
        """
        WITH max_code AS (
            SELECT COALESCE(MAX((regexp_match(code, '^app/([0-9]+)$'))[1]::int), 0) AS mx
            FROM ab_hr_application
            WHERE code ~ '^app/[0-9]+$'
        ), to_fill AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn
            FROM ab_hr_application
            WHERE code IS NULL OR code = ''
        )
        UPDATE ab_hr_application a
        SET code = 'app/' || (m.mx + f.rn)::text
        FROM to_fill f
        CROSS JOIN max_code m
        WHERE a.id = f.id
        """
    )

    if not _table_exists(cr, "ir_sequence"):
        return

    cr.execute(
        "SELECT id FROM ir_sequence WHERE code = %s ORDER BY id LIMIT 1",
        ("ab_hr_application.code",),
    )
    seq_row = cr.fetchone()
    if not seq_row:
        return

    next_number = _max_code_number(cr) + 1
    seq_id = seq_row[0]

    if _column_exists(cr, "ir_sequence", "number_next"):
        cr.execute(
            "UPDATE ir_sequence SET number_next = %s WHERE id = %s",
            (next_number, seq_id),
        )

    if _column_exists(cr, "ir_sequence", "number_next_actual"):
        cr.execute(
            "UPDATE ir_sequence SET number_next_actual = %s WHERE id = %s",
            (next_number, seq_id),
        )
