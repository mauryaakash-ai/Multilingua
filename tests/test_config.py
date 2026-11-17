import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from multilingua.config import ROOT, diagnose, load_config


class ConfigTests(unittest.TestCase):
    def test_expands_paths_in_commands_and_model_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'commands': {'tts': ['{python}', '{project}/adapters/tts_parler.py']},
                                        'tts': {'model': '${ML_TEST_MODEL}/weights'}}))
            with patch.dict('os.environ', ML_TEST_MODEL=directory):
                result = load_config(path)
            self.assertEqual(result['commands']['tts'], [sys.executable, str(ROOT / 'adapters/tts_parler.py')])
            self.assertEqual(result['tts']['model'], directory + '/weights')

    def test_invalid_limits_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for key, value in [('timeout_seconds', -1), ('max_speech_speed', 2),
                               ('max_speech_speed', float('nan'))]:
                path.write_text(json.dumps({'commands': {}, key: value}))
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_missing_config_is_actionable(self):
        report = diagnose('/nonexistent/multilingua.json')
        self.assertFalse(report['ready'])
        self.assertTrue(any('Copy configs/local.example.json' in c['detail'] for c in report['checks']))
