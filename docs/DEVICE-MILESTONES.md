# Device-run milestones

A device test report must tell apart four states that the logs used to blur: the app opened, the guest memory
was reserved, a Vulkan device was created, the game drew its first frame. Each one writes a single logcat line
with the tag `ACMilestone` (same markers as AC-NativeNX):

```sh
adb logcat -c                # before launching
adb logcat -s ACMilestone    # while the app runs
```

| Marker | Written by | Meaning |
|---|---|---|
| `APP_OPEN <package>` | `apk/java/com/letsgorecomp/LetsGoLauncherActivity.java` `onCreate` | the launcher is up; `<package>` tells `com.letsgorecomp` from `com.letsgorecomp.ci`. `(recreated)` is appended when Android recreates it (rotation, fold) |
| `MEM_RESERVE_OK(<bytes>) [lo,hi)` | `src/runtime/main.c` `reserve_guest_space` | the fixed guest window is reserved; `<bytes>` is its size |
| `MEM_RESERVE_FAIL(<bytes>) [lo,hi) errno <n>, attempt <k>` | same | one attempt failed (errno 17 = EEXIST: another mapping holds the window); the runtime re-executes, up to 20 attempts, then stops with "guest address range ... is not free" |
| `VK_DEVICE_OK(<GPU>, driver 0x<version>)` | `src/runtime/nvn/vulkan/device.c` | `vkCreateDevice` succeeded on that GPU and driver |
| `VK_DEVICE_FAIL(<GPU>, driver 0x<version>)` | same | `vkCreateDevice` failed; the existing fatal message follows |
| `GAME_FIRST_FRAME` | `src/runtime/nvn/objects.c` `nvnQueuePresentTexture` | the game itself presented its first frame |

Reading a report: the last marker reached is the state. `APP_OPEN` alone means the game never got to its memory
reservation; `MEM_RESERVE_OK` without a `VK_DEVICE_*` line means it stopped before the GPU (or before Vulkan was
initialised: "no Vulkan device" and friends are logged by the fatal path, not as a marker); `VK_DEVICE_OK` without
`GAME_FIRST_FRAME` means the game did not present. A missing line is "not reached", never "passed".

The markers carry no path, key, title or user data. `tests/test_device_milestones.py` checks on the host that each
marker is still written where this table says and that the native helper prints the expected line; it does not run
anything on a device.
