import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from server import Wall, configure_display_log

class DisplayLog(unittest.TestCase):
    def tearDown(self):
        logger=logging.getLogger('family_wall.display')
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    def test_restart_and_rotation_preserve_private_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            logger=configure_display_log(folder)
            logger.info('before restart')
            logger=configure_display_log(folder)
            logger.info('after restart')
            path=Path(folder)/'display.log'
            self.assertIn('before restart\nafter restart',path.read_text())
            logger.handlers[0].doRollover()
            logger.info('after rotation')
            self.assertIn('before restart',(Path(folder)/'display.log.1').read_text())
            for file in Path(folder).glob('display.log*'):
                self.assertEqual(file.stat().st_mode & 0o777,0o600)

    def test_wake_request_then_observed_on_and_heartbeat(self):
        with tempfile.TemporaryDirectory() as folder:
            configure_display_log(folder)
            wall=Wall(folder,folder)
            with patch('server.in_schedule',return_value=True), patch('server.time.monotonic',return_value=1000), patch('server.subprocess.run',return_value=SimpleNamespace(stdout='HDMI-A-1 off\n')) as run:
                wall.check_power()
                self.assertEqual(run.call_args.args[0],['wlopm','--on','*'])
            with patch('server.in_schedule',return_value=True), patch('server.time.monotonic',return_value=1015), patch('server.subprocess.run',return_value=SimpleNamespace(stdout='HDMI-A-1 on\n')) as run:
                wall.check_power()
                self.assertEqual(run.call_count,1)
                text=(Path(folder)/'display.log').read_text()
                wall.check_power()
                self.assertEqual((Path(folder)/'display.log').read_text(),text)
                with patch('server.time.monotonic',return_value=1315):wall.check_power()
            text=(Path(folder)/'display.log').read_text()
            self.assertIn('action=request-on-accepted',text)
            self.assertIn('observed-before=on action=none',text)
            self.assertEqual(len(text.splitlines()),3)

    def test_errors_are_redacted_and_recovery_logged(self):
        with tempfile.TemporaryDirectory() as folder:
            configure_display_log(folder)
            wall=Wall(folder,folder)
            with patch('server.in_schedule',return_value=False), patch('server.subprocess.run',side_effect=subprocess.TimeoutExpired('private-value',8,output='private-output')):
                wall.check_power()
            self.assertIsNotNone(wall.display['error'])
            with patch('server.in_schedule',return_value=False), patch('server.subprocess.run',return_value=SimpleNamespace(stdout='HDMI-A-1 off\n')):
                wall.check_power()
            text=(Path(folder)/'display.log').read_text()
            self.assertIn('error=TimeoutExpired',text)
            self.assertIn('error=none',text)
            self.assertNotIn('private-',text)
            self.assertIsNone(wall.display['error'])
