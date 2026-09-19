import os
import subprocess
import unittest
from unittest.mock import patch

import start
from scripts.check_environment import probe, report


class LocalEnvironmentTests(unittest.TestCase):
    def test_local_mode_rejects_remote_binding(self):
        for host in ('0.0.0.0', 'example.com', '192.168.1.10'):
            with self.assertRaises(SystemExit):
                start.configure_local_device(host)

    def test_local_mode_overrides_old_hosting_configuration(self):
        with patch.dict(os.environ, {'YTDLP_PROXY': 'https://old.invalid', 'PUBLIC_ORIGIN': 'https://old.invalid'}):
            start.configure_local_device('127.0.0.1')
            self.assertEqual(os.environ['YTDLP_PROXY'], '')
            self.assertEqual(os.environ['COOKIE_SECURE'], 'false')
            self.assertEqual(os.environ['DATA_DIR'], str(start.ROOT / 'data' / 'local-device'))

    def test_old_runtime_is_not_ready(self):
        with patch('shutil.which', return_value='node'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'v20.0.0', '')):
            self.assertFalse(probe('node', ['--version'], (22, 0))['ready'])

    def test_runtime_failure_and_timeout_are_reported(self):
        with patch('shutil.which', return_value='ffprobe'), patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ffprobe', 10)):
            self.assertFalse(probe('ffprobe', ['-version'])['ready'])

    def test_only_one_js_runtime_is_required(self):
        def available(name, *args):
            return {'name': name, 'ready': name != 'deno', 'detail': 'fixture'}
        with patch('app.environment.probe', side_effect=available):
            self.assertTrue(report()['ready'])


if __name__ == '__main__':
    unittest.main()
