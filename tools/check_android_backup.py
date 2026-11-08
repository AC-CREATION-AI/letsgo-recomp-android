#!/usr/bin/env python3
"""Refuse an APK manifest that lets Android copy the app's data off the phone.

The app keeps the player's own data in its storage: the library built from their game (files/gamebuild), saves,
mods and the folder holding their keys. Android Auto Backup (cloud) and the device-to-device transfer must copy
none of it:

- android:allowBackup must be "false", unless android:dataExtractionRules excludes everything AND minSdk >= 31
  (Android 9-11 ignore dataExtractionRules and would back up the whole app);
- with targetSdk >= 31, allowBackup="false" does not stop the device transfer: dataExtractionRules must exclude
  every domain in <device-transfer> (and in <cloud-backup> when backup is allowed).

    python3 tools/check_android_backup.py [apk/AndroidManifest.xml]

Exit status 0 = closed, 1 = refused (with the reason).
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A = "{http://schemas.android.com/apk/res/android}"
DOMAINS = ("root", "file", "database", "sharedpref", "external",
           "device_root", "device_file", "device_database", "device_sharedpref")


def closed_sections(rules: Path):
    """Sections of a data-extraction-rules file that exclude every domain and include nothing."""
    tree = ET.parse(rules).getroot()
    closed = set()
    for section in ("cloud-backup", "device-transfer"):
        node = tree.find(section)
        if node is None or node.find("include") is not None:
            continue
        excluded = {e.get("domain") for e in node.findall("exclude") if e.get("path") == "."}
        if excluded >= set(DOMAINS):
            closed.add(section)
    return closed


def check(manifest: Path):
    root = ET.parse(manifest).getroot()
    app = root.find("application")
    sdk = root.find("uses-sdk")
    min_sdk = int(sdk.get(A + "minSdkVersion", "1")) if sdk is not None else 1
    target_sdk = int(sdk.get(A + "targetSdkVersion", str(min_sdk))) if sdk is not None else min_sdk
    allow = app.get(A + "allowBackup", "true") != "false"  # Android's default is true
    ref = app.get(A + "dataExtractionRules")
    closed = set()
    if ref:
        if not ref.startswith("@xml/"):
            return [f"dataExtractionRules={ref} is not an @xml/ resource"]
        rules = manifest.parent / "res" / "xml" / (ref[len("@xml/"):] + ".xml")
        if not rules.is_file():
            return [f"dataExtractionRules={ref}: {rules} not found"]
        closed = closed_sections(rules)
    errors = []
    if allow:
        if min_sdk < 31:
            errors.append(f'allowBackup="true" with minSdk {min_sdk}: Android 9-11 ignore dataExtractionRules '
                          'and back up the whole app; set android:allowBackup="false"')
        if "cloud-backup" not in closed:
            errors.append('allowBackup="true" without dataExtractionRules excluding every domain in <cloud-backup>')
    if target_sdk >= 31 and "device-transfer" not in closed:
        errors.append(f"targetSdk {target_sdk}: allowBackup does not stop the device-to-device transfer; "
                      "dataExtractionRules must exclude every domain in <device-transfer>")
    return errors


def main(argv):
    manifest = Path(argv[1]) if len(argv) > 1 else ROOT / "apk" / "AndroidManifest.xml"
    errors = check(manifest)
    for e in errors:
        print(f"ANDROID_BACKUP_OPEN: {manifest}: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {manifest} keeps the app data on the phone (no backup, no device transfer)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
