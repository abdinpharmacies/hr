def run_snapshot_concurrency(env):
    import threading
    from contextlib import ExitStack
    from unittest.mock import patch

    from psycopg2.errors import SerializationFailure
    from odoo import api, SUPERUSER_ID

    registry = env.registry
    with registry.cursor() as cr:
        setup = api.Environment(cr, SUPERUSER_ID, {})
        stores = setup['ab_store'].create([
            {'name': 'Concurrency Source', 'code': 'CONCSRC', 'eplus_serial': 97001},
            {'name': 'Concurrency Destination', 'code': 'CONCDST', 'eplus_serial': 97002},
        ])
        employee = setup['ab_costcenter'].create({'name': 'Concurrency Operator', 'code': 'CONCUSER'})
        product = setup['ab_product'].create({'product_card_name': 'Concurrency Product', 'code': 'CONCPROD', 'eplus_serial': 97003})
        product_id = product.id
        source_id, destination_id = stores.ids
        header = setup['ab_transfer_header'].create({
            'from_store_id': source_id, 'to_store_id': destination_id, 'user_id': employee.id,
            'fair_store_ids': [(6, 0, [source_id])], 'smart_product_domain': "[('code', '!=', False)]",
        })
        header_id = header.id
        Stock = setup['ab_transfer_smart_stock_cache']
        State = setup['ab_transfer_smart_cache_state']
        Stock._replace_store_stock_snapshot(stores[1], [{'store_id': destination_id, 'product_eplus_serial': 97003,
            'stock_qty': 10, 'stock_pending_qty': 0, 'cache_date': State._business_date()}], origin='excel', actor_id=SUPERUSER_ID)
        State._publish(stores[1], {'sales_date': State._business_date()})
        header._publish_smart_snapshot_dependencies(header._capture_smart_snapshot_dependencies())
        cr.commit()


    def import_stock(work_env, quantity):
        store = work_env['ab_store'].browse(destination_id)
        work_env['ab_transfer_smart_stock_cache']._replace_store_stock_snapshot(store, [{
            'store_id': destination_id, 'product_eplus_serial': 97003, 'stock_qty': quantity,
            'stock_pending_qty': 0, 'cache_date': work_env['ab_transfer_smart_cache_state']._business_date(),
        }], origin='excel', actor_id=SUPERUSER_ID)


    def competing_transaction(operation, started, finished, outcomes):
        try:
            for attempt in range(3):
                try:
                    with registry.cursor() as cr:
                        work_env = api.Environment(cr, SUPERUSER_ID, {})
                        cr.execute("SET LOCAL lock_timeout = '5s'")
                        started.set()
                        result = operation(work_env)
                        cr.commit()
                        outcomes.append(result)
                        return
                except SerializationFailure:
                    if attempt == 2:
                        raise
        except Exception as error:
            outcomes.append(error)
        finally:
            finished.set()


    def run_blocked_operation(cr, operation):
        started, finished, outcomes = threading.Event(), threading.Event(), []
        worker = threading.Thread(target=competing_transaction, args=(operation, started, finished, outcomes))
        worker.start()
        assert started.wait(5), 'Worker did not start'
        assert not finished.wait(0.3), 'Branch lock did not hold the competing operation'
        cr.commit()
        worker.join(10)
        assert not worker.is_alive(), 'Competing operation did not finish'
        assert outcomes and not isinstance(outcomes[0], Exception), repr(outcomes)
        return outcomes[0]


    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {})
        import_stock(work_env, 20)
        def refresh(other):
            Stock = other['ab_transfer_smart_stock_cache']
            with patch.object(type(Stock), '_fetch_store_stock_rows', side_effect=AssertionError('Import overwritten')):
                result = Stock.refresh_stores_cache(other['ab_store'].browse(destination_id), force=True)
            assert result['preserved_imports'] == 1
            return Stock.read_store_stock_context(other['ab_store'].browse(destination_id))['stock_by_serial']
        assert run_blocked_operation(cr, refresh) == {97003: 20}
    print('PASS: concurrent import versus forced refresh preserves the imported snapshot')

    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {'skip_smart_zero_source_stock_warning': True})
        header = work_env['ab_transfer_header'].browse(header_id)
        Header = type(header)
        with ExitStack() as stack:
            stack.enter_context(patch.object(Header, '_validate_smart_source_connection'))
            stack.enter_context(patch.object(Header, '_ensure_smart_source_cache'))
            stack.enter_context(patch.object(Header, '_get_smart_candidate_source_stock_context', return_value={}))
            stack.enter_context(patch.object(Header, '_get_smart_target_product_serials_with_source_stock', return_value=[97003]))
            apply_rows = stack.enter_context(patch.object(Header, '_apply_smart_transfer_rows', return_value={
                'created': 1, 'updated': 0, 'dropout_excluded': 0, 'missing': 0, 'no_stock': 0}))
            result = header.action_smart_transfer_calculation()
            assert result['params']['type'] == 'success', result
            assert apply_rows.call_args.args[0][0][4] == 20
            revision = header.smart_snapshot_dependencies['branches'][str(destination_id)]['revision']
            run_blocked_operation(cr, lambda other: import_stock(other, 30))
    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {})
        header = work_env['ab_transfer_header'].browse(header_id)
        assert header.smart_snapshot_dependencies['branches'][str(destination_id)]['revision'] == revision
        assert work_env['ab_transfer_smart_cache_state']._state(work_env['ab_store'].browse(destination_id)).stock_revision == revision + 1
        from odoo.exceptions import UserError
        try:
            header._validate_smart_snapshot_dependencies()
        except UserError:
            pass
        else:
            raise AssertionError('Replacement did not invalidate completed calculation')
        cr.rollback()
    print('PASS: concurrent import waits for calculation; replacement invalidates its recorded revision')

    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {})
        header = work_env['ab_transfer_header'].browse(header_id)
        header._publish_smart_snapshot_dependencies(header._capture_smart_snapshot_dependencies())
        cr.commit()
    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {})
        header = work_env['ab_transfer_header'].browse(header_id)
        header.action_smart_to_store_preparation()
        assert header.smart_stage == 'store_preparation'
        run_blocked_operation(cr, lambda other: import_stock(other, 40))
    with registry.cursor() as cr:
        work_env = api.Environment(cr, SUPERUSER_ID, {})
        header = work_env['ab_transfer_header'].browse(header_id)
        try:
            header.action_smart_to_store_revision()
        except UserError:
            pass
        else:
            raise AssertionError('Stale progression was accepted')
        cr.rollback()
    print('PASS: concurrent import waits for progression; next forward action rejects the replaced snapshot')
    with registry.cursor() as cr:
        cleanup = api.Environment(cr, SUPERUSER_ID, {})
        cleanup['ab_transfer_header'].browse(header_id).write({'active': False})
        cleanup['ab_store'].browse([source_id, destination_id]).write({'active': False})
        cleanup['ab_costcenter'].browse(employee.id).write({'active': False})
        cleanup['ab_product'].browse(product_id).write({'active': False})
        cr.commit()
