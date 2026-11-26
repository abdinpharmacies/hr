import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from stages import distribution, probe, read_private, write_result


class StageTests(unittest.TestCase):
    def test_nearest_rank_and_empty_distribution(self):
        self.assertEqual(distribution([]),{'samples':0})
        result=distribution(list(range(1,101)))
        self.assertEqual((result['p50_ms'],result['p95_ms'],result['p99_ms']),(50,95,99))

    def test_private_config_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json'
            write_result(path,{'status':'synthetic'})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(read_private(path),{'status':'synthetic'})
            with self.assertRaises(FileExistsError):
                write_result(path,{'replacement':True})
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                read_private(path)

    def test_probe_stops_at_server_failure_and_never_returns_body(self):
        calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(503,json={'secret':'must-not-appear'})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client,patch('stages.time.sleep'):
            result=probe(client,'GET','https://synthetic.invalid',20)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['statuses'],{'503':1})
        self.assertNotIn('must-not-appear',json.dumps(result))

    def test_probe_contract_failures_and_warm_sample_count(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'version':3}))) as client,patch('stages.time.sleep'):
            result=probe(client,'POST','https://synthetic.invalid',4,expected=lambda value:value=={'version':4})
        self.assertEqual(result['warm_total']['samples'],3)
        self.assertEqual(result['errors'],{'unexpected_response_contract':4})

    def test_transport_errors_are_sanitized(self):
        def handle(request):
            raise httpx.ConnectError('private-credential')
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            result=probe(client,'GET','https://synthetic.invalid',10)
        self.assertEqual(result['errors'],{'ConnectError':1})
        self.assertNotIn('private-credential',json.dumps(result))

    def test_live_send_helpers_refuse_existing_intent_before_connecting(self):
        import chatter
        import website_reply
        import whatsapp_reply
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'send.json'
            write_result(str(path)+'.prepared',{'state':'prepared'})
            for module in (chatter,website_reply,whatsapp_reply):
                with self.subTest(module=module.__name__),self.assertRaises(ValueError):
                    module.run('01000000000',path)

    def test_outcome_requires_a_committed_intent(self):
        import outcome
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'intent.json'
            write_result(path,{'state':'prepared'})
            with self.assertRaises(ValueError):
                outcome.measure(path)


if __name__=='__main__':
    unittest.main()
