"""Host-only compiler discovery for synthetic unittest harnesses."""
import os
import shlex
import shutil
import subprocess
import unittest


def host_compiler(cpu_builtins=False):
    """Honor HOST_CC, then CC; otherwise search PATH, never the Android NDK.

    Return an argv prefix, allowing overrides such as ``ccache clang``.
    cpu.h requires bitreverse builtins which older GCC versions do not provide.
    """
    override = os.environ.get('HOST_CC') or os.environ.get('CC')
    candidates = [shlex.split(override)] if override else [['cc'], ['clang']]
    for command in candidates:
        if not command:
            continue
        executable = shutil.which(command[0])
        if not executable:
            continue
        command = [executable, *command[1:]]
        if cpu_builtins:
            probe = subprocess.run(
                [*command, '-Werror', '-x', 'c', '-fsyntax-only', '-'],
                input='unsigned long long f(unsigned long long x) { return __builtin_bitreverse64(x); }\n'
                      'unsigned g(unsigned x) { return __builtin_bitreverse32(x); }\n',
                capture_output=True, text=True)
            if probe.returncode:
                continue
        return command
    requirement = ' with cpu.h bitreverse builtins' if cpu_builtins else ''
    raise unittest.SkipTest(
        'No available host C compiler' + requirement +
        '; set HOST_CC (preferred) or CC, or install cc/clang on PATH'
        + (f' (configured override: {override!r})' if override else ''))
