"""Round-trip XML, rejection boundaries, and content-preserving CLI imports."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.content import read_content
from editor.design_xml import from_xml, to_xml


class DesignXMLTests(unittest.TestCase):
    def setUp(self):
        self.design = read_content(ROOT)['design']
        self.xml = to_xml(self.design)

    def test_round_trip_for_supported_fonts(self):
        self.assertEqual(from_xml(self.xml), self.design)
        for font in ('palatino', 'optima', 'google-sans', 'system'):
            expected = copy.deepcopy(self.design)
            expected['typography'].update(body_font=font, heading_font=font)
            self.assertEqual(from_xml(to_xml(expected)), expected)

    def test_invalid_structure_and_values_are_rejected(self):
        invalid = [
            '<broken', self.xml.replace('version="1"', 'version="2"'),
            self.xml.replace('website-design', 'other'),
            self.xml.replace('  <spacing', '  <unknown'),
            self.xml.replace('  <spacing', '  <typography'),
            self.xml.replace('body-size="16"', 'body-size="15"'),
            self.xml.replace('body-size="16"', 'body-size="16px"'),
            self.xml.replace('line-height="1.6"', 'line-height="NaN"'),
            self.xml.replace('body-font="system"', 'body-font="arbitrary"'),
            self.xml.replace('<website-design version="1">', '<website-design version="1"><script/>'),
            self.xml.replace('  <layout', '  <layout extra="value"'),
            self.xml.replace('<website-design version="1">', '<website-design version="1">text'),
            self.xml.replace('accent="#005035"', 'accent="#FFFFFF"'),
            '<!DOCTYPE website-design [<!ENTITY external SYSTEM "file:///etc/passwd">]>' + self.xml,
            ' ' * 65537,
        ]
        for source in invalid:
            with self.subTest(source=source[:100]):
                with self.assertRaises(ValueError): from_xml(source)

    def test_cli_import_saves_only_design_and_builds_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'site'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '.openai', '__pycache__', '.editor-state', 'dist'))
            before = read_content(root)
            design = copy.deepcopy(before['design'])
            design['typography']['body_size'] = 18
            design['layout']['news_height'] = 440
            source = Path(temp) / 'design.xml'
            source.write_text(to_xml(design))
            command = [sys.executable, str(root / 'scripts/design_xml.py'), 'import', str(source)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = read_content(root)
            self.assertEqual(after['design'], design)
            self.assertEqual({k:v for k,v in before.items() if k != 'design'}, {k:v for k,v in after.items() if k != 'design'})
            self.assertEqual(from_xml((root / 'dist/assets/design.xml').read_text()), design)
            self.assertTrue(list((root / '.editor-state/backups').glob('*/design.json')))
            exported = Path(temp) / 'export.xml'
            result = subprocess.run([sys.executable, str(root / 'scripts/design_xml.py'), 'export', str(exported)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(from_xml(exported.read_text()), design)
            source.write_text('<website-design version="1"><script/></website-design>')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(read_content(root), after)


if __name__ == '__main__': unittest.main()
