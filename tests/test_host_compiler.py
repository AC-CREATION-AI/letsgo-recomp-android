"""Compiler selection must not silently turn host tests into Android builds."""
import os
import subprocess
import unittest
from unittest.mock import patch

from host_compiler import host_compiler


class HostCompilerTests(unittest.TestCase):
    def test_host_override_precedes_cc_and_ndk(self):
        with patch.dict(os.environ, {'HOST_CC': 'ccache clang', 'CC': 'gcc',
                                    'ANDROID_NDK_HOME': '/synthetic/ndk'}, clear=True), \
                patch('host_compiler.shutil.which', return_value='/synthetic/ccache'):
            self.assertEqual(host_compiler(), ['/synthetic/ccache', 'clang'])

    def test_cc_override(self):
        with patch.dict(os.environ, {'CC': 'clang -O0'}, clear=True), \
                patch('host_compiler.shutil.which', return_value='/synthetic/clang'):
            self.assertEqual(host_compiler(), ['/synthetic/clang', '-O0'])

    def test_missing_override_is_explicit_skip(self):
        with patch.dict(os.environ, {'HOST_CC': 'missing-compiler'}, clear=True), \
                patch('host_compiler.shutil.which', return_value=None):
            with self.assertRaisesRegex(unittest.SkipTest, 'set HOST_CC'):
                host_compiler()

    def test_ndk_does_not_select_host_compiler(self):
        with patch.dict(os.environ, {'ANDROID_NDK_HOME': '/synthetic/ndk'}, clear=True), \
                patch('host_compiler.shutil.which', side_effect=[None, '/synthetic/clang']) as which:
            self.assertEqual(host_compiler(), ['/synthetic/clang'])
            self.assertEqual([call.args[0] for call in which.call_args_list], ['cc', 'clang'])

    def test_missing_builtins_is_explicit_skip(self):
        with patch.dict(os.environ, {'HOST_CC': 'cc'}, clear=True), \
                patch('host_compiler.shutil.which', return_value='/synthetic/cc'), \
                patch('host_compiler.subprocess.run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(unittest.SkipTest, 'bitreverse builtins'):
                host_compiler(cpu_builtins=True)
