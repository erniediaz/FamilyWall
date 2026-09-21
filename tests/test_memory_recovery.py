import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
from photos import resize_photo
import browser_watchdog as watchdog

class MemoryRecovery(unittest.TestCase):
    def test_resize_preserves_orientation_and_replaces_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'photo.jpg'
            with Image.new('RGB', (2400, 1600), 'red') as image:
                exif = image.getexif()
                exif[274] = 6
                image.save(path, exif=exif)
            resize_photo(path, path)
            with Image.open(path) as image:
                self.assertLessEqual(max(image.size), 1280)
                self.assertGreater(image.height, image.width)
                self.assertEqual(image.mode, 'RGB')

    def test_sleep_wake_recovery_and_outage(self):
        with tempfile.TemporaryDirectory() as folder:
            heartbeat = Path(folder) / 'heartbeat'
            process = Mock(pid=1234)
            process.poll.return_value = None
            with patch.object(watchdog.subprocess, 'Popen', return_value=process) as launch, patch.object(watchdog, 'terminate') as stop:
                supervisor = watchdog.Supervisor(['chromium'], heartbeat)
                supervisor.tick(False, 0)
                supervisor.tick(False, 1000)
                launch.assert_not_called()
                supervisor.tick(True, 1001)
                launch.assert_not_called()
                supervisor.tick(True, 1006)
                self.assertEqual(launch.call_count, 1)
                supervisor.tick(None, 1400)
                stop.assert_not_called()
                heartbeat.touch()
                supervisor.tick(True, 1401)
                stop.assert_not_called()
                supervisor.tick(True, 1582)
                stop.assert_called_once_with(process)
                supervisor.tick(False, 1600)
                supervisor.tick(False, 2000)
                self.assertEqual(launch.call_count, 1)
                supervisor.tick(True, 2001)
                supervisor.tick(True, 2006)
                self.assertEqual(launch.call_count, 2)
                supervisor.tick(False, 2010)
                self.assertIsNone(supervisor.process)

    def test_display_must_be_observed_awake(self):
        import io
        def response(on, error=None):
            import json
            return io.BytesIO(json.dumps({'display': {'on': on, 'error': error}}).encode())
        with patch.object(watchdog, 'urlopen', side_effect=lambda *a, **k: response(True)), patch.object(watchdog.subprocess, 'run', return_value=Mock(stdout='HDMI-A-1 off')) as command:
            self.assertIsNone(watchdog.display_ready())
            command.return_value.stdout = 'HDMI-A-1 on'
            self.assertIs(watchdog.display_ready(), True)
        with patch.object(watchdog, 'urlopen', return_value=response(False)), patch.object(watchdog.subprocess, 'run') as command:
            self.assertIs(watchdog.display_ready(), False)
            command.assert_not_called()
        with patch.object(watchdog, 'urlopen', side_effect=OSError):
            self.assertIsNone(watchdog.display_ready())
