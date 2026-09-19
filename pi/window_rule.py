"""Install a scoped labwc size fallback without replacing desktop settings."""
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET


def install(path):
    path = Path(path)
    original = path.read_bytes() if path.exists() else None
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(original, parser=parser) if original else ET.Element('labwc_config')
    if root.tag != 'labwc_config':
        raise ValueError('Unrecognized labwc configuration; left unchanged')
    rules = root.find('windowRules')
    if rules is None:
        rules = ET.SubElement(root, 'windowRules')
    for rule in rules.findall('windowRule'):
        if rule.get('identifier') == 'family-wall':
            if rule.find("action[@name='Maximize']") is not None:
                return False
            raise ValueError('Existing family-wall rule needs review; left unchanged')
    rule = ET.SubElement(rules, 'windowRule', identifier='family-wall')
    ET.SubElement(rule, 'action', name='Maximize')
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name('rc.xml.before-family-wall')
    if original is not None and not backup.exists():
        shutil.copy2(path, backup)
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    fd, temporary = tempfile.mkstemp(prefix='.family-wall-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


if __name__ == '__main__':
    path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'labwc/rc.xml'
    install(path)
    print('Family Wall desktop size rule ready.', flush=True)
