import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
import release


class Release(unittest.TestCase):
    def fixture(self, home):
        base = home / '.local/share/family-wall'
        old = base / 'releases/original'
        old.mkdir(parents=True)
        (old / 'server.py').write_text('original')
        (base / 'current').symlink_to(old, target_is_directory=True)
        source = home / 'installer'
        (source / 'web').mkdir(parents=True)
        (source / 'web/index.html').write_text('new web')
        for name in release.FILES: (source / name).write_text('new file')
        data = home / '.config/family-wall'
        data.mkdir(parents=True)
        (data / 'config.json').write_text(json.dumps({'password': 'test-secret', 'windows': [['06:00', '08:30'], ['16:30', '19:00']]}))
        return base, old, source, data

    def test_upgrade_and_rollback_retain_original_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            base, old, source, data = self.fixture(home)
            before = (data / 'config.json').read_bytes()
            with patch('release.Path.home', return_value=home), patch('release.__file__', str(source / 'release.py')), patch('release.os.getuid', return_value=1000), patch('release.subprocess.run'), patch('release.services'), patch('release.healthy', return_value=True), patch('sys.argv', ['release.py', 'install']):
                release.main()
                self.assertEqual((base / 'before-highlights').resolve(), old)
                self.assertNotEqual((base / 'current').resolve(), old)
                self.assertTrue((base / 'current/highlights.py').is_file())
                self.assertEqual((data / 'config.json').read_bytes(), before)
                with patch('sys.argv', ['release.py', 'rollback']): release.main()
            self.assertEqual((base / 'current').resolve(), old)
            self.assertEqual((old / 'server.py').read_text(), 'original')

    def test_failed_health_check_restores_current_release(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            base, old, source, data = self.fixture(home)
            with patch('release.Path.home', return_value=home), patch('release.__file__', str(source / 'release.py')), patch('release.os.getuid', return_value=1000), patch('release.subprocess.run'), patch('release.services'), patch('release.healthy', return_value=False), patch('sys.argv', ['release.py', 'install']):
                with self.assertRaisesRegex(SystemExit, 'previous release has been restored'): release.main()
            self.assertEqual((base / 'current').resolve(), old)
            self.assertEqual((base / 'before-highlights').resolve(), old)


if __name__ == '__main__': unittest.main()
