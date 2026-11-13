"""Explicit repairs with a separate per-run backup choice."""
import datetime
from pathlib import Path
import signal
import uuid

from psycopg2.extras import Json
from availability import DatabaseGate, target_offline
from common import MigrationError, connect, dumps, ensure_backup, private_dir, save_json
from csv_plan import read_plan, database_identity
from repair_audit import audit, rows
from repair_fixes import LABELS, PLANNERS, plan_fixes, apply_data, restore_fk
from backup_policy import select_backup, perform_backup


def validate_binding(source, target, values):
    plan, _ = read_plan(values['csv_path'])
    identities = dict(source=database_identity(source, values['source_config']),
                      target=database_identity(target, values['target_config']))
    if identities != plan['identities']:
        raise MigrationError('Repair source/target identities differ from the reviewed CSV')
    left, right = identities['source'], identities['target']
    if left['database'] == right['database'] and all(left['endpoint'].get(k) == right['endpoint'].get(k)
                                                      for k in ('db_host', 'db_port')):
        raise MigrationError('Source and target must be different databases')
    return identities


def show(audit_result, fixes):
    print(f"\nRead-only audit: {audit_result['checked']} foreign keys checked; "
          f"{'complete' if audit_result['complete'] else 'INCOMPLETE'}.")
    roles = audit_result['user_roles']
    print('User-type conflicts:', roles.get('conflicting_users', 'not checked: ' + roles.get('reason', 'unknown')))
    for item in audit_result['constraints']:
        if item.get('missing') or item.get('orphan_rows') or item.get('error_type') or item.get('definition_changed') or not item['validated']:
            print(f"  {item['source_table']}.{item['name']}: missing={item['missing']}, "
                  f"orphans={item.get('orphan_rows', 'unknown')}, "
                  f"validated={item['validated']}, error={item.get('error_type', 'none')}")
    print('\nDatabase fixes (separate from import):')
    for number, (name, label) in enumerate(LABELS.items(), 1):
        item = fixes[name]
        print(f"{number}. {label}: " + (f"BLOCKED — {item['error']}" if 'error' in item else f"{len(item['changes'])} change(s)"))
        if name == 'identities' and 'error' not in item:
            print(f"   {item['installed_modules']} installed modules; {len(item['unresolved'])} unresolved aliases/findings.")
            for module, counts in item['modules'].items():
                if counts.get('repairs') or counts.get('unresolved'):
                    print(f"   {module}: {counts.get('repairs', 0)} repairs; {counts.get('unresolved', 0)} unresolved")
            for model, count in item['model_changes'].items():
                print(f'   {model}: {count} changes')
    print('a. All supported fixes\n0. Back to main menu')


def choose(fixes):
    names = list(LABELS)
    while True:
        answer = input('Select fixes (comma-separated numbers, a, or 0): ').strip().lower()
        if answer == '0':
            return []
        if answer == 'a':
            return [name for name in names if 'error' not in fixes[name] and fixes[name]['changes']]
        parts = answer.split(',')
        if parts and all(p.strip() in ('1', '2', '3', '4', '5') for p in parts):
            selected = {names[int(p.strip()) - 1] for p in parts}
            if any('error' in fixes[name] for name in selected):
                print('A selected fix is blocked. Resolve its findings first.')
                continue
            return [name for name in names if name in selected and fixes[name]['changes']]
        print('Choose numbers 1–5, a, or 0.')


def ledger(connection):
    with connection.cursor() as cr:
        cr.execute('CREATE SCHEMA IF NOT EXISTS database_repairs')
        cr.execute('REVOKE ALL ON SCHEMA database_repairs FROM PUBLIC')
        cr.execute('CREATE TABLE IF NOT EXISTS database_repairs.completed '
                   '(run_id text NOT NULL,operation text NOT NULL,record jsonb NOT NULL, '
                   'PRIMARY KEY(run_id,operation))')
    connection.commit()


def receipt(connection, run_id, operation, record):
    with connection.cursor() as cr:
        cr.execute('INSERT INTO database_repairs.completed(run_id,operation,record) VALUES(%s,%s,%s)',
                   [run_id, operation, Json(record, dumps=dumps)])


def perform(connection, source, stage, selected, fixes, identities, context=None):
    """One committed receipt per repair transaction, independent of file reports."""
    ledger(connection)
    results = []
    for name in selected:
        operations = [(name, fixes[name]['changes'])] if name != 'foreign_keys' else [
            ('foreign_key:' + c['after']['source_table'] + ':' + c['after']['name'], [c]) for c in fixes[name]['changes']]
        if name == 'identities':
            models = sorted({c['group_model'] for c in fixes[name]['changes']})
            operations = [('xmlids:' + model, [c for c in fixes[name]['changes'] if c['group_model'] == model])
                          for model in models]
        for operation, changes in operations:
            # Persist full before-images BEFORE writes, including deleted rows.
            save_json(stage / 'before-next-operation.json', dict(operation=operation, changes=changes))
            try:
                with connection.cursor() as cr:
                    cr.execute("SET LOCAL lock_timeout='5s'")
                    cr.execute("SET LOCAL statement_timeout='60s'")
                if name == 'foreign_keys':
                    restore_fk(connection, changes[0]['after'])
                else:
                    if name == 'identities':
                        current_plan = PLANNERS[name](source, connection, context)
                        current = [c for c in current_plan['changes'] if c['group_model'] == changes[0]['group_model']]
                    else:
                        current = PLANNERS[name](source, connection)
                    if dumps(current) != dumps(changes):
                        raise MigrationError('Repair prerequisites changed since preview; run a new audit')
                    apply_data(connection, changes)
                record = dict(operation=operation, changes=changes, identities=identities, status='committed')
                receipt(connection, stage.name, operation, record)
            except Exception as exc:
                connection.rollback()
                result = dict(operation=operation, status='failed', error_type=type(exc).__name__)
                if isinstance(exc, MigrationError):
                    result['reason'] = str(exc)
                results.append(result)
                print(f"{operation}: failed ({result.get('reason', result['error_type'])})", flush=True)
            else:
                # A commit transport error is uncertain: stop and inspect the
                # atomic DB receipt rather than falsely reporting a rollback.
                connection.commit()
                results.append(dict(operation=operation, status='committed', changes=len(changes)))
                print(f'{operation}: committed', flush=True)
            save_json(stage / 'results.json', results)
    return results


def run(values, root, backup=None):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
    stage = private_dir(Path(root) / ('fix_' + stamp + '_' + uuid.uuid4().hex[:12]))
    print(f'Repair reports: {stage}', flush=True)
    source = target = gate = None
    previous_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(*unused):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    try:
        source = connect(values['source_config'], values['source_db'])
        target = connect(values['target_config'], values['target_db'])
        identities = validate_binding(source, target, values)
        context = dict(source_config=values['source_config'], target_config=values['target_config'], identities=identities)
        with source.cursor() as cr:
            cr.execute('SELECT transaction_timestamp()::text,txid_current_snapshot()::text')
            time, snapshot = cr.fetchone()
        before = audit(target)
        fixes = plan_fixes(source, target, before, context)
        save_json(stage / 'preview.json', dict(identities=identities, source_time=time, source_snapshot=snapshot,
                                               audit=before, fixes=fixes))
        save_json(stage / 'xmlid-preview.json', fixes['identities'])
        show(before, fixes)
        selected = choose(fixes)
        if not selected:
            print('No repairs selected; no database changes made.')
            return dict(status='cancelled')
        print('Selected repairs:', ', '.join(LABELS[n] for n in selected))
        print('Affected changes:', sum(len(fixes[n]['changes']) for n in selected))
        backup_choice = select_backup(backup, values['target_db'], stage)
        if backup_choice is None:
            print('Cancelled; no database changes made.')
            return dict(status='cancelled')
        print('Exclusive target access will be required.')
        if input('Apply selected repairs? [y/N]: ').strip().lower() != 'y':
            print('Cancelled; no database changes made.')
            return dict(status='cancelled')
        target.close()
        target = None
        gate = DatabaseGate(values['target_config'], values['target_db'])
        if not gate.online():
            raise MigrationError('Target is offline; recover the owning migration before repairing')
        target = connect(values['target_config'], values['target_db'], readonly=False)
        if validate_binding(source, target, values) != identities:
            raise MigrationError('Database identities changed since preview')
        target.rollback()
        gate.check_sessions([target.get_backend_pid()])
        backup_result = perform_backup(values['target_config'], values['target_db'], stage, backup_choice,
                                       ensure=ensure_backup)
        with target_offline(gate, target, stage):
            if validate_binding(source, target, values) != identities:
                raise MigrationError('Database identities changed before repair')
            target.rollback()
            results = perform(target, source, stage, selected, fixes, identities, context)
            target.rollback()
            # Fresh read-only snapshot: do not leave an online preflight snapshot
            # open while auditing changes made by the repair transactions.
            target.set_session(readonly=True, isolation_level='REPEATABLE READ')
            after = audit(target)
            after_fixes = plan_fixes(source, target, after, context)
            save_json(stage / 'after.json', dict(audit=after, fixes=after_fixes))
            save_json(stage / 'xmlid-after.json', after_fixes['identities'])
            failures = any(r['status'] == 'failed' for r in results)
            findings = any(i.get('missing') or i.get('orphan_rows') or i.get('error_type') or
                           i.get('definition_changed') or not i['validated'] for i in after['constraints'])
            findings |= any('error' in v or v['changes'] for v in after_fixes.values())
            findings |= bool(after_fixes['identities'].get('unresolved'))
            findings |= not after['user_roles']['checked'] or bool(after['user_roles'].get('conflicting_users'))
            result = dict(status='finished_with_errors' if failures else 'complete_with_warnings' if findings else 'complete',
                          results=results, reports=str(stage), backup=backup_result)
            save_json(stage / 'result.json', result)
        print('Repair result:', result['status'])
        return result
    except BaseException as exc:
        failure = dict(status='interrupted' if isinstance(exc, (KeyboardInterrupt, EOFError)) else 'failed',
                       error_type=type(exc).__name__, reports=str(stage))
        if isinstance(exc, MigrationError):
            failure['reason'] = str(exc)
        try:
            save_json(stage / 'failure.json', failure)
        except OSError:
            print('Could not write failure report; inspect private database repair receipts.')
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        if target is not None:
            target.close()
        if source is not None:
            source.close()
        if gate is not None:
            gate.close()
