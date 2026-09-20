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

    def test_missing_heartbeat_restarts_process_group(self):
        with tempfile.TemporaryDirectory() as folder:
            process = Mock(pid=1234)
            process.poll.return_value = None
            response = Mock(status=200)
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            with patch.object(watchdog.Path, 'home', return_value=Path(folder)), patch.object(watchdog.signal, 'signal'), patch.object(watchdog.subprocess, 'Popen', return_value=process), patch.object(watchdog.time, 'monotonic', side_effect=[0, 181]), patch.object(watchdog.time, 'sleep', side_effect=[None, SystemExit]), patch.object(watchdog, 'urlopen', return_value=response), patch.object(watchdog.os, 'killpg') as kill:
                with self.assertRaises(SystemExit):
                    watchdog.main()
                kill.assert_any_call(1234, watchdog.signal.SIGTERM)

    def test_server_outage_does_not_trigger_browser_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            process = Mock(pid=1234)
            process.poll.return_value = None
            def offline(*args, **kwargs):
                kill.assert_not_called()
                raise OSError('offline')
            with patch.object(watchdog.Path, 'home', return_value=Path(folder)), patch.object(watchdog.signal, 'signal'), patch.object(watchdog.subprocess, 'Popen', return_value=process), patch.object(watchdog.time, 'monotonic', side_effect=[0, 181, 192]), patch.object(watchdog.time, 'sleep', side_effect=[None, None, SystemExit]), patch.object(watchdog, 'urlopen', side_effect=offline) as request, patch.object(watchdog.os, 'killpg') as kill:
                with self.assertRaises(SystemExit):
                    watchdog.main()
                self.assertEqual(request.call_count, 2)
