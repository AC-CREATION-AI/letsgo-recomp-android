"""Real filesystem/cache/exec tests, synthetic inputs only (no game)."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from host_compiler import host_compiler

ROOT = Path(__file__).resolve().parents[1]


class OnDevice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('ondevice', ROOT / 'apk/gamebuild/ondevice.py')
        assert spec is not None and spec.loader is not None
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def test_object_committed_only_on_success_and_reused_by_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            source = d / 'sample.c'
            source.write_text('int answer(void){return 42;}\n')
            obj = d / 'out.o'
            args = [*host_compiler(), '-c', str(source)]
            self.assertFalse(self.m.compile_unit(args, source, obj, 'recipe'))
            self.assertTrue(obj.read_bytes().startswith(b'\x7fELF'))
            self.assertTrue(self.m.compile_unit(args, source, obj, 'recipe'))
            source.write_text('bad C!')
            with self.assertRaises(RuntimeError):
                self.m.compile_unit(args, source, obj, 'recipe')
            self.assertFalse(self.m.object_valid(args, source, obj, 'recipe'))
            self.assertTrue(obj.read_bytes().startswith(b'\x7fELF'))

    def test_recipe_change_or_corrupt_object_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); s = d / 's.c'; o = d / 's.o'
            s.write_text('int x;')
            a = [*host_compiler(), '-c', str(s)]
            self.m.compile_unit(a, s, o, 'one')
            self.assertFalse(self.m.object_valid(a, s, o, 'two'))
            o.write_bytes(b'corrupted')
            self.assertFalse(self.m.object_valid(a, s, o, 'one'))

    def test_compiler_relocation_preserves_key_but_recipe_change_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Path(tmp) / 's.c'; s.write_text('int x;')
            a = self.m.unit_key(['/old/package/libzig.so', 'clang', '-c', str(s)], s, 'recipe')
            b = self.m.unit_key(['/new/package/libzig.so', 'clang', '-c', str(s)], s, 'recipe')
            self.assertEqual(a, b)
            self.assertNotEqual(a, self.m.unit_key(['/new/package/libzig.so', 'clang', '-c', str(s)], s, 'new recipe'))

    def test_unknown_nso_rejected_before_generating(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'main'; p.write_bytes(b'NSO0' + b'\0' * 252)
            with self.assertRaisesRegex(ValueError, 'version'):
                self.m.validate_main(p, ['0a3f0d21e67dad80'])
            b = bytearray(p.read_bytes()); b[0x40:0x48] = bytes.fromhex('0a3f0d21e67dad80'); p.write_bytes(b)
            self.m.validate_main(p, ['0a3f0d21e67dad80'])

    def test_synthetic_complete_pipeline_resume_and_invalidation(self):
        cc = host_compiler()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); root = d / 'game'; ex = root / 'extracted/exefs'
            ex.mkdir(parents=True)
            for m in self.m.MODULES:
                b = bytearray(b'NSO0' + b'\0' * 252); b[0x40:0x48] = bytes.fromhex('0a3f0d21e67dad80')
                (ex / m).write_bytes(b)
            work = d / 'private'; kit = work / 'kit'; tools = kit / 'tools'; tools.mkdir(parents=True)
            (tools / 'gen.py').write_text('''import pathlib,sys
m,n,b,o=sys.argv[1:5]
p=pathlib.Path(o);p.mkdir(exist_ok=True)
(p/(m+'_000.c')).write_text('int f_'+m+';')
(p/(m+'_table.c')).write_text('int table_'+m+';')
''')
            inc = kit / 'cckit/gamelib-src'; inc.mkdir(parents=True)
            (inc / 'gamelib_entry.c').write_text('int entry;')
            (kit / 'config.json').write_text(json.dumps(dict(main_ids=['0a3f0d21e67dad80'], recipe='synthetic', gamelib_id='0123456789abcdef')))
            native = d / 'native'; native.mkdir()
            (native / 'liblaspython.so').symlink_to(__import__('sys').executable)
            zig = native / 'libzig.so'
            zig.write_text('#!/usr/bin/env python3\nHOST_CC = ' + repr(cc) + '\n' + '''
import os,sys
a=sys.argv[1:]
if a[0]=='clang':
 out=a[a.index('-o')+1]; source=a[a.index('-c')+1]
 os.execv(HOST_CC[0],HOST_CC+['-fPIC','-c',source,'-o',out])
# Host-only adapter: the Android dependency contract is tested separately.
a=a[1:]; a=[x for x in a if x not in ['-l:liblasrecomp.so', '-l:libc.so', '-L/system/lib64'] and not x.endswith('/libclang_rt.builtins-aarch64-android.a')]
os.execv(HOST_CC[0],HOST_CC+['-shared','-nostdlib']+[v for arg in a for v in ['-Xlinker',arg]])
'''); zig.chmod(0o700)
            env = os.environ.copy()
            try:
                self.m.build(root, work, native)
                state = json.loads((work / 'state.json').read_text())
                self.assertEqual((state['done'], state['total'], state['reused']), (9,9,0))
                ready = json.loads((work / 'ready.json').read_text())
                self.assertTrue(Path(ready['lib']).read_bytes().startswith(b'\x7fELF'))
                self.m.build(root, work, native)
                self.assertEqual(json.loads((work / 'state.json').read_text())['reused'], 9)
                # Corrupt one cached object: precisely one rebuild, never a silent link.
                obj = next((Path(ready['lib']).parent / 'objects').glob('*.o')); obj.write_bytes(b'bad')
                self.m.build(root, work, native)
                self.assertEqual(json.loads((work / 'state.json').read_text())['reused'], 8)
                # Unknown version must leave previous ready pointer unchanged.
                (ex / 'main').write_bytes(b'unknown')
                with self.assertRaises(ValueError): self.m.build(root, work, native)
                self.assertEqual(json.loads((work / 'ready.json').read_text()), ready)
            finally:
                os.environ.clear(); os.environ.update(env)

    def test_link_command_resolves_outlined_atomics_from_pinned_kit(self):
        args = self.m.link_command(Path('/native'), Path('/kit/cckit'), Path('/work/out'), Path('/work/objects.rsp'))
        runtime = '/kit/cckit/clang/lib/libclang_rt.builtins-aarch64-android.a'
        self.assertIn(runtime, args)
        self.assertLess(args.index('@/work/objects.rsp'), args.index(runtime))
        self.assertIn('-l:libc.so', args)
        self.assertIn('-L/system/lib64', args)

    def test_atomic_json_and_no_symlink_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); out = d / 'state.json'
            self.m.atomic_json(out, {'state': 'complete'})
            self.assertEqual(json.loads(out.read_text()), {'state': 'complete'})
            (d / 'outside').write_text('data'); (d / 'link').symlink_to(d / 'outside')
            with self.assertRaises(ValueError):
                self.m.checked_file(d / 'link')


class HostCompilerSelection(unittest.TestCase):
    def test_priority_and_no_ndk_preference(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'HOST_CC': 'wrapper clang', 'CC': 'other',
                                     'ANDROID_NDK_HOME': '/android/ndk'}, clear=True):
            with patch('host_compiler.shutil.which', return_value='/host/wrapper') as which:
                self.assertEqual(host_compiler(), ['/host/wrapper', 'clang'])
                which.assert_called_once_with('wrapper')
        with patch.dict(os.environ, {'CC': 'custom'}, clear=True):
            with patch('host_compiler.shutil.which', return_value='/host/custom'):
                self.assertEqual(host_compiler(), ['/host/custom'])
        with patch.dict(os.environ, {'ANDROID_NDK_HOME': '/android/ndk'}, clear=True):
            with patch('host_compiler.shutil.which', side_effect=[None, '/host/clang']) as which:
                self.assertEqual(host_compiler(), ['/host/clang'])
                self.assertEqual([c.args[0] for c in which.call_args_list], ['cc', 'clang'])

    def test_missing_compiler_skips_with_reason(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            with patch('host_compiler.shutil.which', return_value=None):
                with self.assertRaisesRegex(unittest.SkipTest, 'No available host C compiler'):
                    host_compiler()


if __name__ == '__main__':
    unittest.main()
