"""tools/check_denied_assets.py and its use by build-apk.sh (synthetic files only, no SDK needed).

The denied files themselves are third-party artwork and are never stored here: the tests use synthetic bytes and
put their hash in a copy of the deny-list.

Run: python3 -m unittest tests.test_denied_assets -v
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/check_denied_assets.py'
sys.path.insert(0, str(ROOT / 'tools'))
import check_denied_assets  # noqa: E402

OLD_ICON = '58435d521ddedb55c5ad00539d7680ec92670b28aaf82189e511d34a101afcd4'
SYNTHETIC = b'synthetic stand-in for a denied asset\n'


class DeniedAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_the_former_letsgo_icon_is_denied(self):
        self.assertIn(OLD_ICON, check_denied_assets.DENIED)

    def test_the_committed_icon_is_not_denied_and_is_reproducible(self):
        icon = ROOT / 'apk/res/drawable/icon.png'
        self.assertNotIn(hashlib.sha256(icon.read_bytes()).hexdigest(), check_denied_assets.DENIED)
        r = subprocess.run([sys.executable, str(ROOT / 'tools/make_apk_icon.py'), '--check'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_repository_is_clean(self):
        r = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_denied_hash_is_found_under_any_name_and_depth(self):
        self.put('a/b/renamed.bin', SYNTHETIC)
        self.put('a/ok.png', b'fine')
        denied = {hashlib.sha256(SYNTHETIC).hexdigest(): 'test'}
        found = check_denied_assets.scan([self.root], denied)
        self.assertEqual([p.name for p, _ in found], ['renamed.bin'])

    def test_a_missing_path_is_an_error_not_a_pass(self):
        r = subprocess.run([sys.executable, str(TOOL), str(self.root / 'absent')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn('DENIED_ASSET_CHECK_PATH_MISSING', r.stderr)

    def test_build_apk_refuses_a_denied_resource_before_packaging(self):
        """The real build-apk.sh, with a deny-list copy that also lists the synthetic file."""
        shutil.copy2(ROOT / 'build-apk.sh', self.root)
        (self.root / 'tools').mkdir()
        tool = self.root / 'tools/check_denied_assets.py'
        text = TOOL.read_text(encoding='utf-8').replace(
            'DENIED = {', f'DENIED = {{\n    "{hashlib.sha256(SYNTHETIC).hexdigest()}": "synthetic test entry",', 1)
        tool.write_text(text, encoding='utf-8')
        self.put('apk/res/drawable/icon.png', SYNTHETIC)
        (self.root / 'apk/assets').mkdir(parents=True)
        r = subprocess.run(['bash', str(self.root / 'build-apk.sh')], cwd=self.root, capture_output=True,
                           text=True, env={'PATH': os.environ['PATH'], 'GAME': 'none'})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('APK_DENIED_ASSET', r.stdout + r.stderr)
        self.assertIn('apk/res/drawable/icon.png', r.stderr)
        self.assertFalse((self.root / 'build/apk').exists(), 'packaging started despite a denied asset')


if __name__ == '__main__':
    unittest.main()
