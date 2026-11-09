"""build-runtime.sh honours JOBS: a fake compiler records peak concurrency. No NDK, game or device."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Fake clang: register as running, hold long enough to overlap with siblings,
# record how many compilations are running at that moment, then produce the object.
FAKE_CC = r'''#!/bin/bash
out=''
src=''
while [ $# -gt 0 ]; do
    case "$1" in
        -o) out="$2"; shift ;;
        -c) src="$2"; shift ;;
    esac
    shift
done
mark="$PROBE/running.$$"
touch "$mark"
sleep 0.3
ls "$PROBE" | grep -c '^running\.' >> "$PROBE/peaks"
rm -f "$mark"
case "$src" in *"$FAIL_ON"*) [ -n "$FAIL_ON" ] && { echo 'error: synthetic' >&2; exit 1; } ;; esac
: > "$out"
'''


class BuildRuntimeJobs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='runtime-jobs-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copy2(ROOT / 'build-runtime.sh', self.root)
        src = self.root / 'src'
        for i in range(10):
            p = src / 'runtime' / f'unit{i}.c'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('/* synthetic */\n')
        (src / 'runtime/platform').mkdir()
        (src / 'runtime/platform/android.c').write_text('/* synthetic */\n')
        (src / 'third_party/smaa').mkdir(parents=True)
        (src / 'third_party/smaa/SMAA.hlsl').write_text('// synthetic\n')
        bindir = self.root / 'ndk/toolchains/llvm/prebuilt/linux-x86_64/bin'
        bindir.mkdir(parents=True)
        for name in ('aarch64-linux-android26-clang', 'aarch64-linux-android26-clang++'):
            (bindir / name).write_text(FAKE_CC)
            (bindir / name).chmod(0o755)
        self.probe = self.root / 'probe'
        self.probe.mkdir()

    def build(self, jobs, fail_on=''):
        env = {**os.environ, 'ANDROID_NDK_HOME': str(self.root / 'ndk'),
               'PROBE': str(self.probe), 'FAIL_ON': fail_on}
        if jobs is None:
            env.pop('JOBS', None)
        else:
            env['JOBS'] = jobs
        result = subprocess.run(['bash', str(self.root / 'build-runtime.sh')], env=env,
                                capture_output=True, text=True, timeout=120)
        self.output = result.stdout + result.stderr
        peaks = (self.probe / 'peaks').read_text().split() if (self.probe / 'peaks').exists() else []
        return result.returncode, max(map(int, peaks), default=0)

    def test_default_is_two(self):
        rc, peak = self.build(None)
        self.assertEqual(rc, 0, self.output)
        self.assertIn('SMOKE_OK', self.output)
        self.assertLessEqual(peak, 2, self.output)

    def test_peak_never_exceeds_jobs(self):
        for jobs in ('1', '3'):
            with self.subTest(jobs=jobs):
                (self.probe / 'peaks').unlink(missing_ok=True)
                rc, peak = self.build(jobs)
                self.assertEqual(rc, 0, self.output)
                self.assertGreaterEqual(peak, 1)
                self.assertLessEqual(peak, int(jobs), self.output)

    def test_invalid_jobs_refused(self):
        for jobs in ('0', 'x', '65'):
            with self.subTest(jobs=jobs):
                rc, _ = self.build(jobs)
                self.assertEqual(rc, 1)
                self.assertIn('JOBS_INVALID', self.output)

    def test_one_failure_fails_the_build(self):
        rc, _ = self.build('2', fail_on='unit3.c')
        self.assertEqual(rc, 1, self.output)
        self.assertIn('SMOKE_FAIL', self.output)


if __name__ == '__main__':
    unittest.main()
