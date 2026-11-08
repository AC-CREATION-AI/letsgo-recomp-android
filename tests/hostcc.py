"""Host compilers for the synthetic tests (not a test module).

Lookup order, each name resolved on PATH:
  C        HOST_CC, then CC, then cc
  C++      HOST_CXX, then CXX, then c++
  clang    HOST_CC if it is a clang, then clang (runtime/cpu.h uses clang builtins)
  linker   HOST_LD, then ld, then ld.lld
  JDK      JAVA_HOME, then the javac on PATH

Never a hard-coded /usr/bin path, and never the Android NDK clang: it has no host
libc, so on a host without /usr/include it fails instead of compiling. When no
compiler is found the test is skipped with the reason; a skip is not a pass. CI sets
LETSGO_REQUIRE_HOST_TOOLS=1 so that a missing compiler fails there instead.
"""
import os
import shutil
import unittest
from pathlib import Path


def _find(*names):
    for name in names:
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def host_cc():
    return _find(os.environ.get("HOST_CC"), os.environ.get("CC"), "cc")


def host_cxx():
    return _find(os.environ.get("HOST_CXX"), os.environ.get("CXX"), "c++")


def host_clang():
    cc = os.environ.get("HOST_CC")
    return _find(cc if cc and "clang" in Path(cc).name else None, "clang")


def host_ld():
    return _find(os.environ.get("HOST_LD"), "ld", "ld.lld")


def host_jdk_bin():
    """The bin/ directory of a JDK, or None."""
    home = os.environ.get("JAVA_HOME")
    javac = _find(home and str(Path(home) / "bin" / "javac"), "javac")
    return Path(javac).resolve().parent if javac else None


def require(tool, reason):
    """Return the tool, or skip with the reason (fail under LETSGO_REQUIRE_HOST_TOOLS=1)."""
    if tool:
        return tool
    if os.environ.get("LETSGO_REQUIRE_HOST_TOOLS") == "1":
        raise AssertionError(reason + " (LETSGO_REQUIRE_HOST_TOOLS=1)")
    raise unittest.SkipTest(reason)


def require_cc():
    return require(host_cc(), "no host C compiler: set HOST_CC or put cc on PATH")


def require_cxx():
    return require(host_cxx(), "no host C++ compiler: set HOST_CXX or put c++ on PATH")


def require_clang():
    return require(host_clang(), "no host clang: set HOST_CC to a clang or put clang on PATH")


def require_ld():
    return require(host_ld(), "no host linker: set HOST_LD or put ld or ld.lld on PATH")


def require_jdk_bin():
    return require(host_jdk_bin(), "no JDK: set JAVA_HOME or put javac on PATH")


def require_env(*names):
    """Return the variables' values, or skip like a missing compiler."""
    missing = [n for n in names if not os.environ.get(n)]
    require(not missing, f"{', '.join(missing)} not set: source tools/env.sh")
    return [os.environ[n] for n in names]
