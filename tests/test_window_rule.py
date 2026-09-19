import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
from window_rule import install


class WindowRuleTests(unittest.TestCase):
    def test_preserves_settings_backup_and_repeat_install(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rc.xml'
            original = b'<labwc_config><!--keep--><keyboard><default/></keyboard><windowRules><windowRule identifier="terminal"/></windowRules></labwc_config>'
            path.write_bytes(original)
            self.assertTrue(install(path))
            self.assertEqual(path.with_name('rc.xml.before-family-wall').read_bytes(), original)
            root = ET.parse(path).getroot()
            self.assertIsNotNone(root.find('keyboard/default'))
            self.assertEqual(len(root.findall('windowRules/windowRule')), 2)
            saved = path.read_bytes()
            self.assertFalse(install(path))
            self.assertEqual(path.read_bytes(), saved)

    def test_invalid_xml_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rc.xml'
            path.write_text('<broken')
            with self.assertRaises(ET.ParseError):
                install(path)
            self.assertEqual(path.read_text(), '<broken')

    def test_new_config_scopes_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labwc/rc.xml'
            install(path)
            rule = ET.parse(path).find('windowRules/windowRule')
            self.assertEqual(rule.get('identifier'), 'family-wall')
            self.assertEqual(rule.find('action').get('name'), 'Maximize')


if __name__ == '__main__':
    unittest.main()
