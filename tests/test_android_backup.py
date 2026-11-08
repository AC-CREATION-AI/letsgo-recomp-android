"""Tests for tools/check_android_backup.py (synthetic manifests, plus the real one)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "check_android_backup.py"
DOMAINS = ("root", "file", "database", "sharedpref", "external",
           "device_root", "device_file", "device_database", "device_sharedpref")


def manifest(app_attrs, min_sdk=28, target_sdk=34):
    uses_sdk = f'<uses-sdk android:minSdkVersion="{min_sdk}" android:targetSdkVersion="{target_sdk}" />' if min_sdk else ""
    return f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example">
    {uses_sdk}
    <application android:label="x" {app_attrs} />
</manifest>
'''


def rules(sections=("cloud-backup", "device-transfer"), domains=DOMAINS, extra=""):
    body = "".join(f'<exclude domain="{d}" path="." />' for d in domains) + extra
    return "<data-extraction-rules>" + "".join(f"<{s}>{body}</{s}>" for s in sections) + "</data-extraction-rules>"


class AndroidBackupTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def run_guard(self, app_attrs, rules_xml=None, **sdk):
        (self.root / "AndroidManifest.xml").write_text(manifest(app_attrs, **sdk))
        if rules_xml is not None:
            (self.root / "res/xml").mkdir(parents=True, exist_ok=True)
            (self.root / "res/xml/rules.xml").write_text(rules_xml)
        return subprocess.run([sys.executable, str(GUARD), str(self.root / "AndroidManifest.xml")],
                              capture_output=True, text=True)

    def assert_refused(self, r, reason):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ANDROID_BACKUP_OPEN", r.stderr)
        self.assertIn(reason, r.stderr)

    def test_real_manifest_is_closed(self):
        r = subprocess.run([sys.executable, str(GUARD)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_allow_backup_true_without_rules_is_refused(self):
        self.assert_refused(self.run_guard('android:allowBackup="true"'), 'allowBackup="true"')

    def test_missing_allow_backup_means_true(self):
        self.assert_refused(self.run_guard(''), 'allowBackup="true"')

    def test_allow_backup_true_is_refused_below_android_12_even_with_rules(self):
        r = self.run_guard('android:allowBackup="true" android:dataExtractionRules="@xml/rules"', rules())
        self.assert_refused(r, "minSdk 28")

    def test_allow_backup_true_with_closed_rules_on_android_12_plus_passes(self):
        r = self.run_guard('android:allowBackup="true" android:dataExtractionRules="@xml/rules"', rules(),
                           min_sdk=31)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_allow_backup_false_alone_leaves_the_device_transfer_open(self):
        self.assert_refused(self.run_guard('android:allowBackup="false"'), "device-to-device")

    def test_sdk_levels_left_to_gradle_count_as_recent_target(self):
        # No <uses-sdk> (set by Gradle): the device transfer must still be closed.
        self.assert_refused(self.run_guard('android:allowBackup="false"', min_sdk=None), "device-to-device")

    def test_rules_missing_a_domain_are_refused(self):
        r = self.run_guard('android:allowBackup="false" android:dataExtractionRules="@xml/rules"',
                           rules(domains=[d for d in DOMAINS if d != "file"]))
        self.assert_refused(r, "<device-transfer>")

    def test_rules_with_an_include_are_refused(self):
        r = self.run_guard('android:allowBackup="false" android:dataExtractionRules="@xml/rules"',
                           rules(extra='<include domain="file" path="gamebuild" />'))
        self.assert_refused(r, "<device-transfer>")

    def test_rules_without_device_transfer_are_refused(self):
        r = self.run_guard('android:allowBackup="false" android:dataExtractionRules="@xml/rules"',
                           rules(sections=("cloud-backup",)))
        self.assert_refused(r, "<device-transfer>")

    def test_missing_rules_file_is_refused(self):
        r = self.run_guard('android:allowBackup="false" android:dataExtractionRules="@xml/rules"')
        self.assert_refused(r, "not found")

    def test_allow_backup_false_with_closed_rules_passes(self):
        r = self.run_guard('android:allowBackup="false" android:dataExtractionRules="@xml/rules"', rules())
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
