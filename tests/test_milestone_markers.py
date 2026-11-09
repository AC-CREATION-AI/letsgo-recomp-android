"""Static placement of device milestones. This is not a device execution test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MilestoneMarkers(unittest.TestCase):
    def test_launcher_open(self):
        text = (ROOT / 'apk/java/com/letsgorecomp/LetsGoLauncherActivity.java').read_text()
        self.assertIn('"APP_OPEN"', text)

    def test_memory_results_include_size(self):
        text = (ROOT / 'src/runtime/platform/android.c').read_text()
        self.assertIn('MEM_RESERVE_OK(%llu)', text)
        self.assertEqual(text.count('MEM_RESERVE_FAIL(%llu)'), 2)

    def test_device_results_include_driver(self):
        text = (ROOT / 'src/runtime/nvn/vulkan/device.c').read_text()
        self.assertIn('VK_DEVICE_OK(%s)', text)
        self.assertIn('VK_DEVICE_FAIL(%s)', text)
        self.assertIn('g_vk.props.deviceName', text)

    def test_first_frame_is_game_present_not_launcher(self):
        text = (ROOT / 'src/runtime/nvn/vulkan/device.c').read_text()
        self.assertIn('if (total_frames == 1) LOG("GAME_FIRST_FRAME', text)


if __name__ == '__main__':
    unittest.main()
