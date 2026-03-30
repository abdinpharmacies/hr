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
        SELECT COALESCE(MAX((regexp_match(UPPER(code), '^APP/([0-9]+)$'))[1]::int), 0)
        FROM ab_hr_application
        WHERE UPPER(code) ~ '^APP/[0-9]+$'
        """
    )
    row = cr.fetchone()
    return int(row[0] or 0)


def migrate(cr, version):
    if not _table_exists(cr, "ab_hr_application"):
        return
    if not _column_exists(cr, "ab_hr_application", "code"):
        return

    # Convert safe lowercase app/<n> -> APP/<n> when target is not already used.
    cr.execute(
        """
        UPDATE ab_hr_application a
        SET code = 'APP/' || (regexp_match(a.code, '^app/([0-9]+)$'))[1]
        WHERE a.code ~ '^app/[0-9]+$'
          AND NOT EXISTS (
              SELECT 1
              FROM ab_hr_application x
              WHERE x.code = 'APP/' || (regexp_match(a.code, '^app/([0-9]+)$'))[1]
                AND x.id <> a.id
          )
        """
    )

    # Any remaining lowercase codes are conflicting rows; refill them with fresh APP numbers.
    cr.execute(
        """
        UPDATE ab_hr_application
        SET code = NULL
        WHERE code ~ '^app/[0-9]+$'
        """
    )

    # Prefer APP/<mssql_app_id> for rows still without code when unique.
    if _column_exists(cr, "ab_hr_application", "mssql_app_id"):
        cr.execute(
            """
            UPDATE ab_hr_application a
            SET code = 'APP/' || a.mssql_app_id::text
            WHERE (a.code IS NULL OR a.code = '')
              AND a.mssql_app_id IS NOT NULL
              AND a.mssql_app_id > 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM ab_hr_application x
                  WHERE UPPER(x.code) = 'APP/' || a.mssql_app_id::text
                    AND x.id <> a.id
              )
            """
        )

    # Fill remaining rows with incremental APP/<number> from current max.
    cr.execute(
        """
        WITH max_code AS (
            SELECT COALESCE(MAX((regexp_match(UPPER(code), '^APP/([0-9]+)$'))[1]::int), 0) AS mx
            FROM ab_hr_application
            WHERE UPPER(code) ~ '^APP/[0-9]+$'
        ), to_fill AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn
            FROM ab_hr_application
            WHERE code IS NULL OR code = ''
        )
        UPDATE ab_hr_application a
        SET code = 'APP/' || (m.mx + f.rn)::text
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

    seq_id = seq_row[0]
    next_number = _max_code_number(cr) + 1

    updates = []
    if _column_exists(cr, "ir_sequence", "prefix"):
        updates.append("prefix = 'APP/'")
    if _column_exists(cr, "ir_sequence", "number_next"):
        updates.append(f"number_next = {next_number}")
    if _column_exists(cr, "ir_sequence", "number_next_actual"):
        updates.append(f"number_next_actual = {next_number}")

    if updates:
        cr.execute(
            f"UPDATE ir_sequence SET {', '.join(updates)} WHERE id = %s",
            (seq_id,),
        )
