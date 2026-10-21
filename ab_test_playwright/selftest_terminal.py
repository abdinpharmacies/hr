import unittest

from terminal_setup import SetupCancelled, ask, pick, read_credentials


class TerminalSetupTests(unittest.TestCase):
    def reader(self, *answers):
        values = iter(answers)
        return lambda prompt: next(values)

    def test_required_question_accepts_input(self):
        self.assertEqual(ask('Database', read=self.reader('abdin_replica_callcenter')), 'abdin_replica_callcenter')

    def test_invalid_input_can_be_corrected(self):
        output = []
        def positive(text):
            if not str(text).isdigit() or int(text) < 1:
                raise ValueError('Enter a positive ID')
            return int(text)
        self.assertEqual(ask('ID', validate=positive, read=self.reader('', 'bad', '4'), write=output.append), 4)
        self.assertTrue(any('positive ID' in line for line in output))

    def test_defaults_and_no_unattended_guessing(self):
        self.assertEqual(ask('Mode', '2', read=self.reader('')), '2')
        self.assertEqual(ask('Database', 'qa', interactive=False), 'qa')
        with self.assertRaisesRegex(ValueError, 'required when unattended'):
            ask('Database', interactive=False)

    def test_selection_resolves_id_from_search(self):
        rows = [{'id': 4, 'label': 'QA branch'}]
        find = lambda text: rows if text in ('', 'QA', '4') else []
        selected = pick('Branch', find, read=self.reader('missing', 'QA', '4'), write=lambda text: None)
        self.assertEqual(selected['id'], 4)

    def test_single_match_is_offered_as_default(self):
        rows = [{'id': 8, 'label': 'QA profile'}]
        selected = pick('Employee', lambda text: rows, read=self.reader(''), write=lambda text: None)
        self.assertEqual(selected['id'], 8)
        with self.assertRaisesRegex(ValueError, 'run interactively'):
            pick('Employee', lambda text: rows, interactive=False)

    def test_unattended_explicit_selection(self):
        rows = [{'id': 8, 'label': 'QA profile'}]
        self.assertEqual(pick('Employee', lambda text: rows, current=8, interactive=False)['id'], 8)

    def test_cancellation_and_eof(self):
        with self.assertRaises(SetupCancelled):
            ask('Database', read=self.reader('q'))
        def eof(prompt):
            raise EOFError
        with self.assertRaises(SetupCancelled):
            ask('Database', read=eof)

    def test_hidden_credentials_and_environment_inputs(self):
        suite = {'credentials': {'password_env': 'QA_PASSWORD', 'employee_pin_env': 'QA_PIN'}}
        prompts = []
        replies = iter(['example-password', 'example-pin'])
        def hidden(prompt):
            prompts.append(prompt)
            return next(replies)
        values = read_credentials(suite, read_secret=hidden, environ={})
        self.assertEqual(values, {'password': 'example-password', 'pin': 'example-pin'})
        self.assertNotIn('example-password', ''.join(prompts))
        self.assertNotIn('example-pin', ''.join(prompts))
        self.assertEqual(set(suite['credentials']), {'password_env', 'employee_pin_env'})
        self.assertEqual(read_credentials(suite, interactive=False, environ={
            'QA_PASSWORD': 'environment-password', 'QA_PIN': 'environment-pin',
        })['pin'], 'environment-pin')
        with self.assertRaises(ValueError):
            read_credentials(suite, interactive=False, environ={})


if __name__ == '__main__':
    unittest.main()
