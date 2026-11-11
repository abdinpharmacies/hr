"""Concurrency and SQL batching regressions; no real database connections."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batching import id_batches, bounds
from common import MigrationError
from progress import Reporter, Sink, database_sample, monitor_factory, PREFIX, format_event
from psycopg2 import sql
from test_bulk import render
import test_bulk


class ProgressTests(unittest.TestCase):
    def test_blocked_console_does_not_block_updates_or_file_writer(self):
        entered, release = threading.Event(), threading.Event()
        stream = MagicMock()
        def slow_write(text):
            entered.set()
            release.wait(3)
        stream.write.side_effect = slow_write
        with tempfile.TemporaryDirectory() as directory:
            reporter = Reporter(directory, stream, interval=60)
            try:
                reporter.begin('mapping', model='abdin_eplus.r_sales_trans_h', total=100)
                self.assertTrue(entered.wait(1))
                start = time.monotonic()
                reporter.advance(50, affected=40)
                self.assertLess(time.monotonic() - start, .5)
                reporter.sinks[1].close(1)
                latest = json.loads((Path(directory) / 'progress.json').read_text())
                self.assertEqual(latest['processed'], 50)
                self.assertEqual(latest['affected'], 40)
                self.assertNotIn('committed', latest)
            finally:
                release.set()
                reporter.close()

    def test_bounded_queue_coalesces_and_reports_drops(self):
        entered, release = threading.Event(), threading.Event()
        received = []
        def consume(event):
            entered.set()
            release.wait(2)
            received.append(event)
        sink = Sink(consume, capacity=3)
        try:
            sink.put({'kind': 'log', 'text': 'start'})
            self.assertTrue(entered.wait(1))
            for i in range(20):
                sink.put({'kind': 'progress', 'operation_id': 'x', 'processed': i})
            self.assertEqual(len(sink.queue), 1)
            for i in range(8):
                sink.put({'kind': 'log', 'text': str(i), 'important': True})
            self.assertLessEqual(len(sink.queue), 3)
            self.assertGreater(sink.dropped, 0)
        finally:
            release.set()
            sink.close()
        self.assertTrue(any('dropped' in e.get('text', '') for e in received))

    def test_stale_monitor_sample_rejected_and_eta_threshold(self):
        reporter = Reporter(stream=io.StringIO(), interval=60)
        try:
            token = reporter.begin('mapping', total=100)
            reporter.operation('next SQL')
            self.assertFalse(reporter.update(token=token, database={'state': 'stale'}))
            reporter.advance(20)
            self.assertIsNone(reporter.snapshot()['eta'])
            reporter.advance(20)
            reporter.advance(20)
            reporter.started -= 20
            self.assertGreater(reporter.snapshot()['eta'], 0)
            reporter.transaction('rolled back', 'business transaction')
            event = reporter.snapshot()
            self.assertIsNone(event['processed'])
            self.assertEqual(event['status'], 'rolled back')
        finally:
            reporter.close()

    def test_remote_events_keep_worker_log_and_latest_state(self):
        with tempfile.TemporaryDirectory() as directory:
            reporter = Reporter(directory, io.StringIO(), interval=60)
            reporter.accept(PREFIX + json.dumps(dict(kind='progress', phase='mapping', processed=10)), 'bulk-import')
            reporter.accept('plain diagnostic', 'bulk-import')
            reporter.close()
            self.assertIn('processed=10', (Path(directory) / 'bulk-import.log').read_text())
            self.assertIn('plain diagnostic', (Path(directory) / 'migration.log').read_text())
            self.assertEqual(json.loads((Path(directory) / 'progress.json').read_text())['processed'], 10)

    def test_monitor_only_queries_pid_scoped_statistics(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [('active', 'IO', 'DataFileRead', 12, []), (True,), (500, 4096)]
        sample = database_sample(connection, 123)
        self.assertEqual(sample['copy_rows'], 500)
        queries = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertTrue(all('pg_' in q for q in queries))
        self.assertNotIn('SELECT query', '\n'.join(queries))
        self.assertEqual(cursor.execute.call_args_list[0].args[1], [123])
        self.assertEqual(cursor.execute.call_args_list[-1].args[1], [123])

    def test_monitor_factory_readonly_timeout_separate_connection(self):
        with patch('common.settings', return_value={'db_user': 'odoo'}), patch('psycopg2.connect') as connect:
            factory = monitor_factory('unused.conf', 'target')
            connect.assert_not_called()
            connection = factory()
            connection.set_session.assert_called_once_with(readonly=True, autocommit=True)
            self.assertIn('statement_timeout=1000', connect.call_args.kwargs['options'])
            self.assertEqual(connect.call_args.kwargs['connect_timeout'], 1)

    def test_broken_sink_does_not_raise_in_producer(self):
        def broken(event):
            raise OSError('unavailable')
        sink = Sink(broken)
        sink.put({'kind': 'log', 'text': 'test'})
        sink.close()
        self.assertEqual(sink.failed, 'OSError')
        self.assertIn('logging_errors=OSError', format_event(dict(kind='progress', logging_errors=['OSError'])))

    def test_keyset_sparse_negative_ids_and_empty_end(self):
        queries = []
        rows = iter([(-5, 2), (9, 2), (100, 1), (None, 0)])
        batches = list(id_batches(lambda q: queries.append(render(q)), lambda: next(rows), sql.Identifier('source'), 2))
        self.assertEqual(batches, [(None, -5, 2), (-5, 9, 2), (9, 100, 1)])
        self.assertIn('WHERE id > -5', queries[1])
        self.assertFalse(any('OFFSET' in q or 'COMMIT' in q for q in queries))
        self.assertEqual(render(bounds('s', -5, 9)), '"s"."id" > -5 AND "s"."id" <= 9')

    def test_keyset_nonadvancing_batch_fails(self):
        rows = iter([(2, 1), (2, 1)])
        with self.assertRaises(MigrationError):
            list(id_batches(lambda q: None, lambda: next(rows), sql.Identifier('source')))

    def test_load_batches_do_not_commit_and_preserve_explicit_columns(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.batches = lambda table: iter([(None, 3, 2), (3, 9, 2)])
        engine.load_model('ab_test', engine.prepare('ab_test'))
        engine.cr.commit.assert_not_called()
        statements = [q for q, _ in engine.queries]
        inserts = [q for q in statements if 'ON CONFLICT (id)' in q]
        self.assertEqual(len(inserts), 2)
        self.assertIn('"p"."id" > 3', inserts[1])
        self.assertIn('WITH NO DATA', statements[0])
