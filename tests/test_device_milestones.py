"""Device-run milestones (docs/DEVICE-MILESTONES.md): each marker is still written where it should be, and the native
helper prints the expected line. Host only: no device, GPU, game or key.

Run: python3 -m unittest discover -s tests -p test_device_milestones.py -v
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from hostcc import require_cc

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/runtime"

# marker -> (file, text that must surround it there)
SITES = {
    "APP_OPEN": (ROOT / "apk/java/com/letsgorecomp/LetsGoLauncherActivity.java",
                 r'super\.onCreate\(b\);\s*\n(?:\s*//.*\n)?\s*android\.util\.Log\.i\("ACMilestone", "APP_OPEN "'),
    "MEM_RESERVE_OK": (RUNTIME / "main.c",
                       r'if \(plat_reserve_guest\(GUEST_LO, GUEST_HI\)\) \{\s*milestone\("MEM_RESERVE_OK\(%llu\)'),
    "MEM_RESERVE_FAIL": (RUNTIME / "main.c", r'milestone\("MEM_RESERVE_FAIL\(%llu\)[^;]*;\s*if \(n >= 20\)'),
    "VK_DEVICE": (RUNTIME / "nvn/vulkan/device.c",
                  r'vkCreateDevice_result = vkCreateDevice\([^;]*;\s*(?://.*\n)?\s*milestone\("VK_DEVICE_%s\(%s, driver 0x%x\)"'
                  r'[^;]*;\s*VK_CHECK\(vkCreateDevice_result\);'),
    "GAME_FIRST_FRAME": (RUNTIME / "nvn/objects.c",
                         r'rt_present\(HOST\(NvnTexture, w->textures\[i\]\)\);\s*static bool first_frame;[^\n]*\n'
                         r'\s*if \(!__atomic_exchange_n\(&first_frame, true, __ATOMIC_RELAXED\)\) milestone\("GAME_FIRST_FRAME"\);'),
}

HARNESS = r'''#include "milestone.h"
int main(void) {
    milestone("MEM_RESERVE_FAIL(%llu) [0x%llx,0x%llx) errno %d, attempt %d", 0x800000000ull, 0x7000000000ull,
              0x7800000000ull, 17, 1);
    milestone("VK_DEVICE_%s(%s, driver 0x%x)", "OK", "Synthetic GPU", 0x80000000u);
    milestone("GAME_FIRST_FRAME");
    return 0;
}
'''


class DeviceMilestones(unittest.TestCase):
    def test_markers_are_written_where_documented(self):
        for marker, (path, pattern) in SITES.items():
            with self.subTest(marker=marker):
                self.assertRegex(path.read_text(encoding="utf-8"), pattern, path.name)
        self.assertNotIn("VK_CHECK(vkCreateDevice(", (RUNTIME / "nvn/vulkan/device.c").read_text())

    def test_documented_markers_match_the_code(self):
        doc = (ROOT / "docs/DEVICE-MILESTONES.md").read_text(encoding="utf-8")
        for marker in ("APP_OPEN", "MEM_RESERVE_OK", "MEM_RESERVE_FAIL", "VK_DEVICE_OK", "VK_DEVICE_FAIL",
                       "GAME_FIRST_FRAME", "adb logcat -s ACMilestone"):
            self.assertIn(marker, doc)

    def test_host_lines(self):
        cc = require_cc()
        with tempfile.TemporaryDirectory() as td:
            src, exe = Path(td) / "harness.c", Path(td) / "harness"
            src.write_text(HARNESS)
            subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(RUNTIME), str(src), "-o", str(exe)],
                           check=True)
            lines = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stderr.splitlines()
        self.assertEqual(lines, [
            "ACMilestone: MEM_RESERVE_FAIL(34359738368) [0x7000000000,0x7800000000) errno 17, attempt 1",
            "ACMilestone: VK_DEVICE_OK(Synthetic GPU, driver 0x80000000)",
            "ACMilestone: GAME_FIRST_FRAME"])


if __name__ == "__main__":
    unittest.main()
