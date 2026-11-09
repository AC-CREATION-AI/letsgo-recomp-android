#!/usr/bin/env python3
"""Refuse files whose bytes are known third-party artwork that must never come back.

A deny-list by SHA-256, not a legal audit: it stops a revert, a cherry-pick or an upstream merge from
silently bringing back a file that was removed for rights reasons. Run by build-apk.sh on the APK inputs
(before aapt2) and by guard.yml on the whole tree.

    python3 tools/check_denied_assets.py [PATH ...]   # default: the repository root

Exit status 0 = clean, 1 = refused (with the offending paths listed).
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", "node_modules", "build", "deps", "__pycache__", ".gradle"}

# sha256 -> why it is refused. Add, never remove.
DENIED = {
    "58435d521ddedb55c5ad00539d7680ec92670b28aaf82189e511d34a101afcd4":
        "former apk/res/drawable/icon.png: official 'Pokémon Let's Go, Eevee!' artwork (franchise logo + "
        "character), byte-identical to CowKillers/letsgo-recomp-android@660aba09; replaced by an original icon",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files_under(path: Path):
    if path.is_file():
        yield path
        return
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_file() and not p.is_symlink():
                yield p


def scan(paths, denied=DENIED):
    """Return [(path, reason)] for every file under `paths` whose sha256 is denied."""
    return [(p, denied[h]) for root in paths for p in files_under(Path(root)) if (h := sha256(p)) in denied]


def main(argv) -> int:
    paths = argv or [str(ROOT)]
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        print("DENIED_ASSET_CHECK_PATH_MISSING: " + " ".join(missing), file=sys.stderr)
        return 1
    findings = scan(paths)
    if findings:
        print("REFUSED: denied third-party asset found:", file=sys.stderr)
        for path, reason in findings:
            print(f"  DENIED_ASSET: {path} — {reason}", file=sys.stderr)
        return 1
    print(f"OK: no denied asset in {' '.join(paths)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
