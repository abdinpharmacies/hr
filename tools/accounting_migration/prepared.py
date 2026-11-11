"""Prepared-target migration controller. No source business writes, ever."""
import datetime
import os
from pathlib import Path
import signal
import select
import time
import subprocess
import sys
import uuid
from psycopg2 import sql
from psycopg2.extras import execute_values
from availability import DatabaseGate, recover_target, target_offline
from common import MigrationError, connect, loads, save_json, settings, ensure_backup, schema_digest
from resume import endpoint, fingerprint
import prepared_snapshot as snapshot
from prepared_importer import PreparedImporter, META, WORK, MIN_MATCHED_ID, missing_identity_query

HERE=Path(__file__).resolve().parent
FORMAT=1
CHECKPOINTS=('identities','custom_and_xmlids','external','attachments','validation')


def confirm(summary):
    print('\n'+summary,flush=True)
    try:
        return input('Continue? [y/N] ').strip().lower() in ('y','yes')
    except EOFError:
        return False


def read_checkpoint(connection, name):
    with connection.cursor() as cr:
        cr.execute('SELECT to_regclass(%s)',[META+'.checkpoint'])
        if cr.fetchone()[0] is None:
            return None
        cr.execute(sql.SQL('SELECT value FROM {} WHERE name=%s').format(sql.Identifier(META,'checkpoint')),[name])
        row=cr.fetchone()
        return loads(row[0]) if row else None


def initialize(connection, identity):
    with connection.cursor() as cr:
        cr.execute('SELECT to_regnamespace(%s)',[META])
        exists=cr.fetchone()[0] is not None
        if exists:
            cr.execute(sql.SQL('SELECT value FROM {} WHERE name=%s').format(sql.Identifier(META,'checkpoint')),['run'])
            row=cr.fetchone()
            if not row or loads(row[0])!=identity:
                raise MigrationError('Prepared-target run identity differs; refusing to adopt another run')
        else:
            cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(META)))
            cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(META)))
            cr.execute(sql.SQL('CREATE TABLE {} (name text PRIMARY KEY,value text NOT NULL)').format(sql.Identifier(META,'checkpoint')))
            write_checkpoint(connection,'run',identity)


def write_checkpoint(connection, name, value):
    from common import dumps
    with connection.cursor() as cr:
        cr.execute(sql.SQL('INSERT INTO {} VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value').format(
            sql.Identifier(META,'checkpoint')),[name,dumps(value)])


def metadata(args, stage, smoke=False):
    output=Path(stage)/('orm-validation.json' if smoke else 'target-schema.json')
    argv=[sys.executable,str(HERE/'prepared_metadata.py'),'--config',args.target_config,
          '--database',args.target_db,'--server',str(HERE.parents[2]/'server'),'--output',str(output)]
    if smoke:
        argv+=['--manifest',str(Path(stage)/'snapshot.json')]
    with open(Path(stage)/('orm-validation.log' if smoke else 'metadata.log'),'a') as log:
        result=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        raise MigrationError('Read-only Odoo worker failed; see '+str(Path(stage)/('orm-validation.log' if smoke else 'metadata.log')))
    return loads(output.read_text())


class SmokeWorker:
    """Open a read-only ORM cursor online, execute the probe only after gating."""
    def __init__(self,args,stage):
        self.output=Path(stage)/'orm-validation.json'
        self.log=open(Path(stage)/'orm-validation.log','a')
        self.proc=subprocess.Popen([sys.executable,str(HERE/'prepared_metadata.py'),
            '--config',args.target_config,'--database',args.target_db,'--server',str(HERE.parents[2]/'server'),
            '--output',str(self.output),'--manifest',str(Path(stage)/'snapshot.json'),'--wait'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
        deadline=time.monotonic()+120
        try:
            while time.monotonic()<deadline:
                if select.select([self.proc.stdout],[],[],.5)[0]:
                    line=self.proc.stdout.readline()
                    if line.startswith('@PREPARED_READY@'):
                        self.pid=loads(line[len('@PREPARED_READY@'):])['pid']
                        return
                    self.log.write(line)
                if self.proc.poll() is not None:
                    break
            raise MigrationError('Read-only ORM worker did not become ready; see orm-validation.log')
        except BaseException:
            self.close()
            raise

    def run(self):
        stdout,_=self.proc.communicate('GO\n')
        self.log.write(stdout)
        self.log.flush()
        if self.proc.returncode:
            raise MigrationError('Read-only ORM validation failed; see orm-validation.log')
        result=loads(self.output.read_text())
        if not result.get('passed'):
            raise MigrationError('ORM validation did not pass')
        return result

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for pipe in (self.proc.stdin,self.proc.stdout):
            if pipe and not pipe.closed:
                pipe.close()
        self.log.close()


def find_stage(root, identity):
    candidates=[]
    for path in Path(root).glob('*/prepared-run.json'):
        value=loads(path.read_text())
        if value.get('source_endpoint')==identity['source_endpoint'] and value.get('target_endpoint')==identity['target_endpoint'] \
                and value.get('source_db')==identity['source_db'] and value.get('target_db')==identity['target_db']:
            candidates.append((path.parent,value))
    if len(candidates)>1:
        raise MigrationError('Ambiguous prepared-target run directories')
    if candidates:
        path,old=candidates[0]
        if old!=identity:
            raise MigrationError('Database identity, schema or rules changed; incompatible prepared run')
        return path
    path=Path(root)/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_prepared_'+uuid.uuid4().hex[:12])
    path.mkdir(parents=True,mode=0o700)
    save_json(path/'prepared-run.json',identity)
    return path


def source_identity(connection):
    result={}
    with connection.cursor() as cr:
        for table in ('res_users','res_partner'):
            cr.execute(sql.SQL('SELECT id FROM public.{} ORDER BY id').format(sql.Identifier(table)))
            result[table]=[row[0] for row in cr]
    return result


def source_database_oid(config, database):
    """Read catalog identity without source ownership, locks, or session control."""
    connection=connect(config,'postgres',readonly=True)
    try:
        with connection.cursor() as cr:
            cr.execute('SELECT oid FROM pg_database WHERE datname=%s',[database])
            row=cr.fetchone()
            if row is None:
                raise MigrationError('Source database does not exist')
            return row[0]
    finally:
        connection.close()


def target_signature(target):
    # Evaluated Python defaults (e.g. today's date) are data, not schema identity.
    return schema_digest({m:{k:v for k,v in meta.items() if k!='defaults'} for m,meta in target.items()})


def identity_checkpoint(connection, ids, stage):
    report={}
    with connection.cursor() as cr:
        cr.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(snapshot.SCHEMA)))
        cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(snapshot.SCHEMA)))
        for table,values in ids.items():
            cr.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (id bigint PRIMARY KEY)').format(sql.Identifier(snapshot.SCHEMA,table)))
            cr.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(snapshot.SCHEMA,table)))
            if values:
                execute_values(cr,sql.SQL('INSERT INTO {} (id) VALUES %s').format(sql.Identifier(snapshot.SCHEMA,table)).as_string(connection),
                               [(v,) for v in values])
            cr.execute(missing_identity_query(sql.Identifier(snapshot.SCHEMA,table),sql.Identifier('public',table)))
            missing=[row[0] for row in cr]
            checked=sum(v>=MIN_MATCHED_ID for v in values)
            report[table]=dict(source_count=len(values),checked_count=checked,skipped_count=len(values)-checked,
                               missing_count=len(missing),missing_ids=missing)
    save_json(Path(stage)/'id-validation.json',report)
    if any(v['missing_ids'] for v in report.values()):
        raise MigrationError('Source user/partner IDs >= 7 missing from target; see id-validation.json. IDs below 7 are skipped; extra target IDs are allowed.')
    return dict(identity=fingerprint(ids),report=report)


def run(args, root):
    os.umask(0o077)
    if args.source_db==args.target_db:
        raise MigrationError('Source and target database names must differ')
    rules=loads((HERE/'prepared_rules.json').read_text())
    conversions=loads((HERE/'mappings.json').read_text())
    if rules.get('format')!=FORMAT:
        raise MigrationError('Unsupported prepared rules version')
    for model in rules.get('stable_keys',{}):
        if model in ('res.users','res.partner','res.groups','ir.attachment'):
            raise MigrationError(f'Stable-key override forbidden: {model}')
    for config in (args.source_config,args.target_config):
        if not settings(config).get('data_dir'):
            raise MigrationError('Both configs must specify data_dir for unambiguous filestore paths')
    source_root=(Path(settings(args.source_config)['data_dir']).expanduser()/'filestore'/args.source_db).resolve()
    target_root=(Path(settings(args.target_config)['data_dir']).expanduser()/'filestore'/args.target_db).resolve()
    if source_root.is_relative_to(target_root) or target_root.is_relative_to(source_root):
        raise MigrationError('Source and target filestore paths must not overlap')
    tg,source_con,target_con,stage=None,None,None,None
    previous_handler=signal.getsignal(signal.SIGTERM)
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupted)
    try:
        tg=DatabaseGate(args.target_config,args.target_db)
        identity=dict(format=FORMAT,source_db=args.source_db,target_db=args.target_db,
            source_endpoint=endpoint(args.source_config),target_endpoint=endpoint(args.target_config),
            source_oid=source_database_oid(args.source_config,args.source_db),target_oid=tg.oid,rules=fingerprint([rules,conversions]))
        stage=find_stage(root,identity)
        print(f'Prepared custom migration: {args.source_db} -> {args.target_db}\nRun: {stage}',flush=True)
        recover_target(tg,stage)
        tg.check_sessions([])
        path=stage/'snapshot.json'
        manifest=loads(path.read_text()) if path.exists() else None
        if manifest and manifest.get('complete'):
            snapshot.verify(stage,manifest)
        print('Source access: read-only. Source availability and sessions are not managed.',flush=True)
        target=metadata(args,stage)
        target_con=connect(args.target_config,args.target_db,readonly=False)
        existing_run=read_checkpoint(target_con,'run')
        if existing_run is not None and existing_run!=identity:
            raise MigrationError('Target database belongs to a different prepared migration run')
        if not str(target.get('res.users',{}).get('table','')).startswith('res_users'):
            raise MigrationError('Prepared target registry unavailable')
        with target_con.cursor() as cr:
            cr.execute("SELECT latest_version FROM ir_module_module WHERE name='base'")
            if not str(cr.fetchone()[0]).startswith('19.'):
                raise MigrationError('Prepared target must be Odoo 19')
        target_con.rollback()
        if (stage/'schema-identity.json').exists():
            if loads((stage/'schema-identity.json').read_text())!=dict(identity=target_signature(target)):
                raise MigrationError('Target registry schema changed since extraction')
        else:
            save_json(stage/'schema-identity.json',dict(identity=target_signature(target)))
        ids_path=stage/'source-ids.json'
        done=read_checkpoint(target_con,'identities')
        imported=read_checkpoint(target_con,'custom_and_xmlids')
        target_con.rollback()
        if not manifest or not manifest.get('complete'):
            if imported:
                raise MigrationError('Original complete extraction is required after custom data has committed')
            try:
                source_con=connect(args.source_config,args.source_db,readonly=True)
            except Exception as exc:
                raise MigrationError(f'Cannot read source ({type(exc).__name__}); check connection/access. '
                                     'Source availability is not managed by this script.') from None
            with source_con.cursor() as cr:
                cr.execute("SELECT latest_version FROM ir_module_module WHERE name='base'")
                version=cr.fetchone()
                if not version or not str(version[0]).startswith('15.'):
                    raise MigrationError('Source must be Odoo 15')
            ids=source_identity(source_con)
            if ids_path.exists() and loads(ids_path.read_text())!=ids:
                save_json(stage/('source-ids-before-refresh-'+uuid.uuid4().hex[:8]+'.json'),loads(ids_path.read_text()))
            save_json(ids_path,ids)
        else:
            if not ids_path.exists():
                raise MigrationError('Saved source ID lists are required for completed extraction')
            ids=loads(ids_path.read_text())
        refresh=done is not None and done['identity']!=fingerprint(ids)
        if refresh and imported:
            raise MigrationError('Saved source ID lists differ from the committed extraction')
        if not done or refresh:
            if refresh:
                print('Source IDs changed before extraction completed; revalidate checkpoint 1 using the new snapshot.',flush=True)
            if not confirm('Checkpoint 1: validate source user/partner IDs >= 7. IDs below 7 are skipped; extra target IDs are allowed.'):
                return dict(passed=False,status='cancelled',source_access='read_only')
            with target_offline(tg,target_con,stage):
                initialize(target_con,identity)
                report=identity_checkpoint(target_con,ids,stage)
                write_checkpoint(target_con,'identities',report)
                write_checkpoint(target_con,'status',dict(complete=False))
                target_con.commit()
        if not manifest or not manifest.get('complete'):
            if source_con is None:
                raise MigrationError('Read-only source connection required for extraction')
            # Interrupted extraction files are never appended to or mixed with new data.
            if (stage/'tables').exists():
                (stage/'tables').rename(stage/('incomplete-tables-'+uuid.uuid4().hex[:8]))
            if source_identity(source_con)!=ids:
                raise MigrationError('Source IDs changed since checkpoint 1; refusing to change the approved snapshot')
            manifest=snapshot.export(source_con,args.source_config,args.source_db,stage,target,rules,conversions)
            if source_identity(source_con)!=ids:
                raise MigrationError('Source IDs changed since checkpoint 1')
        if source_con is not None:
            source_con.close()
            source_con=None
        snapshot.verify(stage,manifest)
        print(f'Scope: {len(manifest["selected"])} shared custom models; {len(manifest["omitted"])} omitted. '
              f'Source custom activities: {manifest["activities"]}.',flush=True)
        print(f'Extracted custom rows: {sum(manifest["tables"][manifest["models"][m]["table"]]["rows"] for m in manifest["selected"]):,}; '
              f'total extraction bytes: {sum(t["bytes"] for t in manifest["tables"].values()):,}.',flush=True)
        print('Omitted models: '+', '.join(manifest['omitted']),flush=True)
        summaries={
            'custom_and_xmlids':'Checkpoint 2: back up target; replace selected custom rows and repair XML IDs in one transaction.',
            'external':'Checkpoint 3: populate custom fields referencing existing Odoo records.',
            'attachments':'Checkpoint 4: import attachment records/files and restore attachment links.',
            'validation':'Checkpoint 5: skip activity import and validate completed migration.'}
        completed=read_checkpoint(target_con,'validation')
        if completed:
            engine=PreparedImporter(target_con,stage,manifest,target,rules,conversions)
            engine.preflight(replacing=False)
            engine.validate_ids()
            engine.verify_fingerprints(completed['fingerprints'])
            if engine.mapping_fingerprint()!=completed['mapping_fingerprint']:
                raise MigrationError('Lookup identities changed after completed migration')
            engine.validate_values()
            target_con.rollback()
            print('All checkpoints already committed; verified imported table fingerprints.',flush=True)
        for phase in CHECKPOINTS[1:]:
            saved=read_checkpoint(target_con,phase)
            target_con.rollback()
            if saved:
                if saved['snapshot']!=fingerprint(manifest):
                    raise MigrationError('Committed snapshot identity differs')
                print(f'Skip committed checkpoint: {phase}',flush=True)
                continue
            if not confirm(summaries[phase]):
                return dict(passed=False,status='cancelled',source_access='read_only')
            if phase=='custom_and_xmlids':
                ensure_backup(args.target_config,args.target_db,stage)
                save_json(stage/'filestore-baseline.json',dict(path=str(target_root),exists=target_root.exists()))
            smoke=SmokeWorker(args,stage) if phase=='validation' else None
            try:
                process_checkpoint(args,stage,identity,manifest,target,rules,conversions,target_con,tg,
                                   phase,source_root,target_root,smoke)
            finally:
                if smoke:
                    smoke.close()
            report=read_checkpoint(target_con,phase)
            target_con.rollback()
            save_json(stage/(phase+'.json'),report)
        result=read_checkpoint(target_con,'validation')
        target_con.rollback()
        save_json(stage/'verification.json',dict(passed=True,source_access='read_only',report=result))
        print(f'Migration complete. Target online: {args.target_db}. Source availability was not changed.',flush=True)
        print(f'Omitted models: {len(manifest["omitted"])}; missing attachment files: '
              f'{len(result["report"].get("missing_files",[]))}; activities skipped: {manifest["activities"]}.',flush=True)
        return dict(passed=True,source_access='read_only',stage=str(stage))
    except BaseException as exc:
        if stage:
            diagnostics=dict(error_type=type(exc).__name__,complete=False,source_policy='read_only')
            if getattr(exc,'diag',None):
                diagnostics.update(sqlstate=exc.pgcode,table=exc.diag.table_name,column=exc.diag.column_name,
                                   constraint=exc.diag.constraint_name)
            save_json(stage/'failure.json',diagnostics)
        if isinstance(exc,(MigrationError,KeyboardInterrupt)):
            raise
        raise MigrationError(f'Prepared migration failed: {type(exc).__name__}; see private run diagnostics. '
                             'Source availability was not changed.') from None
    finally:
        signal.signal(signal.SIGTERM,previous_handler)
        if source_con is not None:
            source_con.close()
        if target_con is not None:
            target_con.close()
        if tg is not None:
            tg.close()


def process_checkpoint(args,stage,identity,manifest,target,rules,conversions,target_con,tg,
                       phase,source_root,target_root,smoke=None):
    with target_offline(tg,target_con,stage,workers=[smoke.pid] if smoke else []):
        initialize(target_con,identity)
        if phase=='custom_and_xmlids':
            snapshot.stage_tables(target_con,stage,manifest)
            with target_con.cursor() as cr:
                cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(WORK)))
                cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(WORK)))
        engine=PreparedImporter(target_con,stage,manifest,target,rules,conversions)
        engine.validate_ids()
        engine.preflight(replacing=phase=='custom_and_xmlids')
        previous=None
        for name in reversed(CHECKPOINTS[1:CHECKPOINTS.index(phase)]):
            previous=read_checkpoint(target_con,name)
            if previous:
                break
        if previous:
            engine.verify_fingerprints(previous['fingerprints'])
            if engine.mapping_fingerprint()!=previous['mapping_fingerprint']:
                raise MigrationError('Prepared target lookup identities changed between checkpoints')
        if phase=='custom_and_xmlids':
            engine.replace()
        elif phase=='external':
            engine.external()
        elif phase=='attachments':
            engine.attachments(source_root,target_root)
        else:
            attachment_result=read_checkpoint(target_con,'attachments')
            engine.report.update({k:v for k,v in attachment_result['report'].items() if k in ('missing_files','copied_files')})
            engine.validate_custom()
            engine.validate_values()
            engine.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s LEFT JOIN public.ir_model_data t USING(module,name) '
                'WHERE s.model=ANY(%s) AND s.module<>%s AND (t.id IS NULL OR t.model<>s.model OR t.res_id<>s.res_id))').format(
                    sql.Identifier(snapshot.SCHEMA,'ir_model_data')),'Final XML-ID validation failed',
                    [manifest['selected'],'__export__'])
        report=dict(snapshot=fingerprint(manifest),fingerprints=engine.fingerprints(),mapping_fingerprint=engine.mapping_fingerprint(),
                    report=engine.report,complete=phase=='validation')
        if phase=='validation':
            report['orm']=smoke.run()
            write_checkpoint(target_con,'status',dict(complete=True))
        write_checkpoint(target_con,phase,report)
        target_con.commit()
