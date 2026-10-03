"""Tests sans réseau ni génération facturée."""
import contextlib
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils.fd_claude import interroger_llm


class ClaudeTests(unittest.TestCase):
    def call(self, blocks, stop='end_turn'):
        client = MagicMock()
        stream = client.with_options.return_value.messages.stream
        stream.return_value.__enter__.return_value.get_final_message.return_value = SimpleNamespace(
            content=blocks, stop_reason=stop,
            usage=SimpleNamespace(input_tokens=100, output_tokens=200))
        module = SimpleNamespace(CLIENT=client, MODEL='claude-test', BlocTronqueError=RuntimeError)
        return client, stream, module

    def test_exact_payload_and_single_call(self):
        client, stream, module = self.call([SimpleNamespace(type='text', text='Rapport complet')])
        output = io.StringIO()
        with patch.dict(sys.modules, {'utils.claude_llm': module}), contextlib.redirect_stdout(output):
            result = interroger_llm('données du thème', system_prompt='ton validé')
        self.assertEqual(result, 'Rapport complet')
        client.with_options.assert_called_once_with(max_retries=0)
        stream.assert_called_once_with(model='claude-test', max_tokens=12000, temperature=0.7,
                                       system='ton validé', messages=[{'role': 'user', 'content': 'données du thème'}])
        self.assertIn('données du thème', output.getvalue())
        self.assertIn('ton validé', output.getvalue())

    def test_truncation_retries_once_and_delivers_complete_report(self):
        _, stream, module = self.call([SimpleNamespace(type='text', text='incomplet')], 'max_tokens')
        stream.return_value.__enter__.return_value.get_final_message.side_effect = [
            SimpleNamespace(
                content=[SimpleNamespace(type='text', text='incomplet')],
                stop_reason='max_tokens',
                usage=SimpleNamespace(input_tokens=100, output_tokens=12000),
            ),
            SimpleNamespace(
                content=[SimpleNamespace(type='text', text='rapport complet')],
                stop_reason='end_turn',
                usage=SimpleNamespace(input_tokens=100, output_tokens=15000),
            ),
        ]
        with patch.dict(sys.modules, {'utils.claude_llm': module}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(interroger_llm('test'), 'rapport complet')
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(stream.call_args_list[0].kwargs['max_tokens'], 12000)
        self.assertEqual(stream.call_args_list[1].kwargs['max_tokens'], 18000)

    def test_second_truncation_is_not_delivered(self):
        _, stream, module = self.call([SimpleNamespace(type='text', text='incomplet')], 'max_tokens')
        with patch.dict(sys.modules, {'utils.claude_llm': module}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                interroger_llm('test')
        self.assertEqual(stream.call_count, 2)

    def test_empty_response_is_not_delivered(self):
        _, stream, module = self.call([])
        with patch.dict(sys.modules, {'utils.claude_llm': module}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                interroger_llm('test')
        stream.assert_called_once()


if __name__ == '__main__':
    unittest.main()
