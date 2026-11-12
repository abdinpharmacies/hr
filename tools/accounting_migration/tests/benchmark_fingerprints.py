"""Compare committed baseline and working code using generated disposable DBs.

Run with MIGRATION_PREPARED_TEST_CONFIG; no application database is opened.
The selected Git revision supplies only the two fingerprint/checkpoint modules.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulk import catalog
from prepared import read_checkpoint, write_checkpoint
from raw_importer import RawImporter
from table_checkpoints import TableMigration
from table_resume import ResumeState
from test_raw_relationships import RawRelationshipTests


def baseline(revision):
    modules = []
    for name in ('table_resume', 'table_checkpoints'):
        source = subprocess.check_output(
            ['git', 'show', revision + ':tools/accounting_migration/' + name + '.py'], text=True)
        module = types.ModuleType('benchmark_baseline_' + name)
        exec(compile(source, '<baseline ' + name + '>', 'exec'), module.__dict__)
        modules.append(module)
    modules[1].ResumeState = modules[0].ResumeState
    return modules[1].TableMigration, modules[0].ResumeState


def seed(case, rows):
    case.fixture()
    fields = dict(store_id='integer', customer_id='integer', invoice_date='char', net_amount='float')
    with case.con.cursor() as cr:
        for table in ('public.ab_group', 'prepared_migration_source.ab_group'):
            cr.execute('ALTER TABLE ' + table + ' ADD COLUMN store_id integer, '
                       'ADD COLUMN customer_id integer, ADD COLUMN invoice_date varchar, '
                       'ADD COLUMN net_amount double precision')
        cr.execute("INSERT INTO prepared_migration_source.ab_group "
                   "SELECT 13+g, repeat(md5(g::text),4), 1+(g%%20), g%%50000, "
                   "'2026-01-01', (g%%10000)/10.0 FROM generate_series(1,%s) g", [rows])
    manifest, target = case.arguments[2:4]
    for name, kind in fields.items():
        descriptor = dict(type=kind, ttype=kind, store=True, required=False)
        target['ab_group']['fields'][name] = descriptor
        manifest['models']['ab_group']['fields'][name] = descriptor
    manifest['tables']['ab_group'].update(rows=rows + 1, columns=catalog(case.con)['ab_group'])
    case.con.commit()


def exercise(case, runner_type, state_type):
    engine = RawImporter(*case.arguments)
    engine.validate_ids()
    engine.preflight(replacing=True)
    runner = runner_type(engine, write_checkpoint)
    scans = []
    digest = state_type.digest

    def observe(state, table, descriptor):
        scans.append(table)
        return digest(state, table, descriptor)

    phase_times = {}
    unit = runner.unit

    def timed(table, operation, *args, **kwargs):
        started = time.perf_counter()
        result = unit(table, operation, *args, **kwargs)
        if table == 'ab_group':
            phase_times[operation] = time.perf_counter() - started
        return result

    with patch.object(state_type, 'digest', observe), patch.object(runner, 'unit', timed):
        started = time.perf_counter()
        result = runner.run(case.source_files, case.target_files)
        elapsed = time.perf_counter() - started
    # Compare all public table values, including metadata and attachment links,
    # plus FK outcomes, findings, checkpoint coverage, and no-recopy resume.
    public = {table: runner.resume.digest(table, dict(columns=list(columns)))
              for table, columns in engine.physical.items()}
    issues = sorted((json.dumps(json.loads(line), sort_keys=True)
                     for line in (case.stage / 'relationship_issues.jsonl').read_text().splitlines()))
    checks = read_checkpoint(case.con, 'resume_state')['checks']
    markers = {key: value for key, value in runner.resume.records.items() if key.startswith('table:')}
    with patch.object(runner_type, 'copy_model', side_effect=AssertionError('unexpected recopy')):
        resumed = RawImporter(*case.arguments)
        resumed.validate_ids()
        resumed.preflight(replacing=False)
        again = runner_type(resumed, write_checkpoint).run(case.source_files, case.target_files)
    assert again['failed_tables'] == []
    evidence = dict(public=public, issues=issues, checks=checks, markers=markers,
                    status=result['status'], failures=result['failed_tables'], fks=result['failed_foreign_keys'])
    signature = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    return dict(seconds=round(elapsed, 3), large_table_scans=scans.count('ab_group'),
                phases={k: round(v, 3) for k, v in phase_times.items()}, signature=signature)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--rows', type=int, default=250000)
    parser.add_argument('--trials', type=int, default=3)
    args = parser.parse_args()
    if not os.environ.get('MIGRATION_PREPARED_TEST_CONFIG') or args.rows < 1 or args.trials < 1:
        parser.error('Set MIGRATION_PREPARED_TEST_CONFIG and use positive rows/trials')
    old_runner, old_state = baseline(args.baseline_ref)
    results = {'baseline': [], 'optimized': []}
    RawRelationshipTests.setUpClass()
    try:
        for trial in range(args.trials):
            order = ('baseline', 'optimized') if trial % 2 == 0 else ('optimized', 'baseline')
            for label in order:
                case = RawRelationshipTests()
                case.setUp()
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        seed(case, args.rows)
                        runner, state = (old_runner, old_state) if label == 'baseline' else (TableMigration, ResumeState)
                        measurement = exercise(case, runner, state)
                    results[label].append(measurement)
                    print(json.dumps(dict(trial=trial + 1, variant=label, **measurement)), flush=True)
                finally:
                    case.tearDown()
    finally:
        RawRelationshipTests.tearDownClass()
    assert len({row['signature'] for values in results.values() for row in values}) == 1, 'Results differ'
    medians = {label: statistics.median(row['seconds'] for row in values) for label, values in results.items()}
    print(json.dumps(dict(rows=args.rows + 1, medians=medians,
                          reduction_percent=round(100 * (1 - medians['optimized'] / medians['baseline']), 1),
                          equivalent_results=True)), flush=True)


if __name__ == '__main__':
    main()
