MODEL_RENAMES = {
    "ab.sales.dashboard.collection.line": "ab_sales_dashboard_collection_line",
    "ab.sales.dashboard.config.mixin": "ab_sales_dashboard_config_mixin",
    "ab.sales.dashboard.daily.collection.fact": "ab_sales_dashboard_daily_collection_fact",
    "ab.sales.dashboard.daily.item.fact": "ab_sales_dashboard_daily_item_fact",
    "ab.sales.dashboard.daily.store.fact": "ab_sales_dashboard_daily_store_fact",
    "ab.sales.dashboard.daily.user.fact": "ab_sales_dashboard_daily_user_fact",
    "ab.sales.dashboard.fact.coverage": "ab_sales_dashboard_fact_coverage",
    "ab.sales.dashboard.fact.decision": "ab_sales_dashboard_fact_decision",
    "ab.sales.dashboard.invoice.line": "ab_sales_dashboard_invoice_line",
    "ab.sales.dashboard.item.line": "ab_sales_dashboard_item_line",
    "ab.sales.dashboard.product.sales.report": "ab_sales_dashboard_product_sales_report",
    "ab.sales.dashboard.reconciliation.chunk": "ab_sales_dashboard_reconciliation_chunk",
    "ab.sales.dashboard.reconciliation.job": "ab_sales_dashboard_reconciliation_job",
    "ab.sales.dashboard.report.archive": "ab_sales_dashboard_report_archive",
    "ab.sales.dashboard.report.telemetry": "ab_sales_dashboard_report_telemetry",
    "ab.sales.dashboard.service": "ab_sales_dashboard_service",
    "ab.sales.dashboard.snapshot": "ab_sales_dashboard_snapshot",
    "ab.sales.dashboard.sync.coverage": "ab_sales_dashboard_sync_coverage",
    "ab.sales.dashboard.user.line": "ab_sales_dashboard_user_line",
}

SEQUENCE_RENAMES = {
    "ab.sales.dashboard.report.archive": "ab_sales_dashboard_report_archive",
}


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
         LIMIT 1
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _update_string_column(cr, table, column, old, new):
    if not _column_exists(cr, table, column):
        return
    cr.execute(
        f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
        (new, old),
    )


def _update_model_fk(cr, table, column, old_id, new_id):
    if not _column_exists(cr, table, column):
        return
    cr.execute(
        f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
        (new_id, old_id),
    )


def migrate(cr, version):
    for old, new in MODEL_RENAMES.items():
        _update_string_column(cr, "ir_model_fields", "relation", old, new)
        _update_string_column(cr, "ir_act_window", "res_model", old, new)
        _update_string_column(cr, "ir_act_server", "model_name", old, new)
        _update_string_column(cr, "ir_ui_view", "model", old, new)
        _update_string_column(cr, "ir_filters", "model_id", old, new)

    for old, new in SEQUENCE_RENAMES.items():
        _update_string_column(cr, "ir_sequence", "code", old, new)

    for old, new in MODEL_RENAMES.items():
        cr.execute("SELECT id FROM ir_model WHERE model = %s", (old,))
        old_row = cr.fetchone()
        cr.execute("SELECT id FROM ir_model WHERE model = %s", (new,))
        new_row = cr.fetchone()
        if not old_row or not new_row:
            continue
        old_id, new_id = old_row[0], new_row[0]
        _update_model_fk(cr, "ir_act_server", "model_id", old_id, new_id)
        _update_model_fk(cr, "ir_act_server", "binding_model_id", old_id, new_id)
        _update_model_fk(cr, "ir_act_server", "crud_model_id", old_id, new_id)
        _update_model_fk(cr, "ir_cron", "model_id", old_id, new_id)
        _update_model_fk(cr, "ir_model_access", "model_id", old_id, new_id)
        _update_model_fk(cr, "ir_rule", "model_id", old_id, new_id)

    old_models = tuple(MODEL_RENAMES)
    cr.execute("SELECT id FROM ir_model WHERE model IN %s", (old_models,))
    old_model_ids = [row[0] for row in cr.fetchall()]
    if not old_model_ids:
        return

    cr.execute(
        "DELETE FROM ir_model_fields WHERE model_id = ANY(%s)",
        (old_model_ids,),
    )
    cr.execute(
        """
        DELETE FROM ir_model
         WHERE id = ANY(%s)
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data
                 WHERE model = 'ir.model'
                   AND res_id = ir_model.id
           )
        """,
        (old_model_ids,),
    )
