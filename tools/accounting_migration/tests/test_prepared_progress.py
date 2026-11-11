"""Observability tests: no database connections or business-data changes."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepared_progress as progress
from common import save_json
from watch_progress import observe


class PreparedProgressTests(unittest.TestCase):
    def test_copy_percentage_only_when_measured(self):
        event=dict(kind='progress',phase='copy',operation='COPY FROM',processed=50,total=100,elapsed=5)
        self.assertIn('progress=50.0%',progress.format_status(event))
        self.assertNotIn('progress=',progress.format_status({**event,'operation':'INSERT SELECT'}))
        self.assertNotIn('progress=',progress.format_status({**event,'total':None}))

    def test_byte_counters_preserve_exact_payload(self):
        original=b'1\tvalue\\with\\escapes\n2\t\xff\n'
        with patch('prepared_progress._active',MagicMock()):
            reader=progress.InputCounter(io.BytesIO(original))
            self.assertEqual(reader.read(3)+reader.read(),original)
            self.assertEqual(reader.bytes,len(original))
            output=io.BytesIO()
            writer=progress.OutputCounter(output)
            writer.write(original[:3])
            writer.write(original[3:])
            self.assertEqual(output.getvalue(),original)

    def test_blocked_console_does_not_block_progress_or_file_sink(self):
        entered,release=threading.Event(),threading.Event()
        stream=MagicMock()
        stream.write.side_effect=lambda value:(entered.set(),release.wait(2))
        with tempfile.TemporaryDirectory() as directory,patch('prepared_progress.monitor_factory'):
            reporter=progress.PreparedReporter(directory,'unused',stream=stream,interval=60)
            try:
                reporter.begin('copy',total=10)
                self.assertTrue(entered.wait(1))
                start=time.monotonic()
                reporter.update(processed=5)
                reporter.finish('pending commit')
                self.assertLess(time.monotonic()-start,.5)
                reporter.sinks[1].close(1)
                self.assertEqual(json.loads((Path(directory)/'progress.json').read_text())['processed'],5)
            finally:
                release.set()
                reporter.close()

    def test_logging_exceptions_never_escape(self):
        broken=MagicMock()
        for method in ('begin','update','finish','pause','bind_target','close'):
            getattr(broken,method).side_effect=OSError('sink unavailable')
        with patch('prepared_progress._active',broken):
            progress.begin('copy')
            progress.update(processed=1)
            progress.finish()
            progress.pause()
            progress.bind(None,None)
            progress.stop()

    def test_prompt_pause_and_finished_operation_invalidate_samples(self):
        stream=io.StringIO()
        with tempfile.TemporaryDirectory() as directory,patch('prepared_progress.monitor_factory'):
            reporter=progress.PreparedReporter(directory,'unused',stream=stream,interval=60)
            try:
                token=reporter.begin('copy',operation='COPY FROM',monitor=True)
                reporter.finish('copied; pending commit')
                self.assertFalse(reporter.update(token=token,processed=1))
                reporter.pause()
                stream.seek(0)
                stream.truncate()
                reporter._console(dict(kind='progress',phase='copy',elapsed=0))
                self.assertEqual(stream.getvalue(),'')
                self.assertFalse(reporter.state['monitor'])
            finally:
                reporter.close()

    def test_pid_identity_checked_and_no_query_values_sampled(self):
        connection=MagicMock()
        cr=connection.cursor.return_value.__enter__.return_value
        cr.fetchone.side_effect=[('active',None,None,5,[]),(True,),(50,500),(True,),('building index',1,10,2,20)]
        result=progress.sample(connection,12,123,'2026-01-01 00:00:00+00')
        self.assertEqual(result['copy_rows'],50)
        self.assertEqual(result['index_phase'],'building index')
        first=cr.execute.call_args_list[0]
        self.assertIn('backend_start=%s::timestamptz',first.args[0])
        self.assertEqual(first.args[1],[12,123,'2026-01-01 00:00:00+00'])
        self.assertFalse(any('SELECT query' in call.args[0] for call in cr.execute.call_args_list))
        cr.fetchone.side_effect=[None]
        self.assertEqual(progress.sample(connection,12,123,'wrong')['state'],'registered backend unavailable')

    def test_watcher_only_uses_maintenance_database_and_known_identifiers(self):
        connection=MagicMock()
        cr=connection.cursor.return_value.__enter__.return_value
        cr.fetchone.side_effect=[(12,),('ab_record',)]
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory)
            save_json(stage/'prepared-run.json',dict(target_endpoint={},target_db='target',target_oid=12))
            save_json(stage/'availability.json',dict(oid=12,database='target',sessions=[dict(pid=123,started='stamp')]))
            save_json(stage/'snapshot.json',dict(tables={'ab_record':dict(rows=100,bytes=1000)}))
            with patch('watch_progress.endpoint',return_value={}), \
                    patch('watch_progress.monitor_factory',return_value=lambda:connection) as factory, \
                    patch('watch_progress.sample',return_value=dict(state='active',copy_rows=50,copy_bytes=500)):
                messages=observe('target.conf',stage)
            factory.assert_called_once_with('target.conf','postgres')
            self.assertIn('progress=50.0%',messages[0])
            self.assertTrue(all(call.args[0].startswith('SELECT') for call in cr.execute.call_args_list))
            connection.close.assert_called_once()


if __name__=='__main__':
    unittest.main()
