"""Benchmark staging versus direct COPY, only in generated disposable databases."""
import argparse
import contextlib
import io
import json
import os
import statistics
import time

from psycopg2 import sql
from test_csv_postgres import CSVPostgresTests
from csv_copy import copy_table, table_fingerprint, restart_sequence, HashSink


def measure(rows, staged):
    case = CSVPostgresTests()
    case.setUp()
    try:
        for con in (case.source, case.con):
            with con.cursor() as cr:
                cr.execute('DROP TABLE a_b_rel')
            con.commit()
        with case.source.cursor() as cr:
            cr.execute("INSERT INTO ab_other SELECT 100+g,repeat(md5(g::text),4) FROM generate_series(1,%s) g", [rows])
        case.source.commit()
        runner = case.runner({'ab_other'})
        meta = runner.manifest['tables']['ab_other']
        columns = runner.plan['target']['columns']['ab_other']
        fields = meta['columns']
        started = time.perf_counter()
        with case.con.cursor() as cr:
            if staged:
                cr.execute('CREATE SCHEMA csv_benchmark_stage')
                cr.execute('CREATE TABLE csv_benchmark_stage.ab_other(id integer,name text)')
                with open(case.stage / 'tables' / meta['file'], 'rb') as file:
                    cr.copy_expert(sql.SQL('COPY csv_benchmark_stage.ab_other ({}) FROM STDIN').format(
                        sql.SQL(',').join(map(sql.Identifier, fields))).as_string(case.con), file)
                staged_rows = cr.rowcount
                cr.execute('ALTER TABLE csv_benchmark_stage.ab_other ADD PRIMARY KEY(id)')
                cr.execute('SELECT count(*) FROM csv_benchmark_stage.ab_other')
                assert cr.fetchone()[0] == meta['rows']
                sink = HashSink()
                cr.copy_expert('COPY (SELECT id,name FROM csv_benchmark_stage.ab_other ORDER BY id) TO STDOUT', sink)
                case.con.commit()
                cr.execute('DELETE FROM ab_other')
                cr.execute('INSERT INTO ab_other SELECT * FROM csv_benchmark_stage.ab_other')
            else:
                staged_rows = 0
                copied = copy_table(case.con, case.stage, 'ab_other', meta, columns, {})
                assert copied == meta['rows']
        restart_sequence(case.con, 'ab_other', columns)
        checksum = table_fingerprint(case.con, 'ab_other', columns)
        case.con.commit()
        seconds = time.perf_counter() - started
        return dict(seconds=round(seconds, 3), sha256=checksum, rows=meta['rows'],
                    retained_bytes=meta['bytes'], staging_rows_written=staged_rows,
                    total_data_rows_written=staged_rows + meta['rows'])
    finally:
        case.tearDown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=250000)
    parser.add_argument('--trials', type=int, default=3)
    args = parser.parse_args()
    if not os.environ.get('MIGRATION_PREPARED_TEST_CONFIG') or min(args.rows, args.trials) < 1:
        parser.error('Set MIGRATION_PREPARED_TEST_CONFIG and positive rows/trials')
    CSVPostgresTests.setUpClass()
    outcomes = {'staged': [], 'direct': []}
    try:
        for trial in range(args.trials):
            order = ('staged', 'direct') if trial % 2 == 0 else ('direct', 'staged')
            for variant in order:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = measure(args.rows, variant == 'staged')
                outcomes[variant].append(result)
                print(json.dumps(dict(trial=trial + 1, variant=variant, **result)), flush=True)
    finally:
        CSVPostgresTests.tearDownClass()
    assert len({row['sha256'] for values in outcomes.values() for row in values}) == 1
    medians = {name: statistics.median(row['seconds'] for row in values) for name, values in outcomes.items()}
    print(json.dumps(dict(medians=medians, reduction_percent=round(100 * (1 - medians['direct'] / medians['staged']), 1),
                          equivalent_contents=True, data_row_writes_reduction_percent=50)), flush=True)


if __name__ == '__main__':
    main()
