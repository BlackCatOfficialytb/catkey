"""
CatKey - Python binding to the C core (catkey_core.dll / libcatkey_core.so)

All Vietnamese conversion is done in the C/C++ core. This module only
loads the shared library and marshals strings across the ABI. If the
library cannot be found, core_available() returns False and the UI can
degrade gracefully (preview shows a "core not built" notice).
"""

import ctypes
import sys
from pathlib import Path

# Method constants must match vietnamese_tep.h
_METHOD_RAW = 0
_METHOD_TEIP = 1
_METHOD_VNI = 2
_METHOD_VIQR = 3
_METHOD_TEIP_VNI = 4
_MAX_OUTPUT = 128

def _data_root() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_CORE_DIR = _data_root() / "catkey_core"


def _lib_names():
    if sys.platform == "win32":
        return ["catkey_core.dll"]
    if sys.platform == "darwin":
        return ["libcatkey_core.dylib"]
    return ["libcatkey_core.so"]


_HAS_HOOK = False


def _bind(lib):
    global _HAS_HOOK
    lib.catkey_convert_word.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
    ]
    lib.catkey_convert_word.restype = ctypes.c_int
    # Optional system-wide hook engine (Windows only).
    try:
        lib.catkey_start.restype = ctypes.c_int
        lib.catkey_stop.restype = None
        lib.catkey_set_enabled.argtypes = [ctypes.c_int]
        lib.catkey_get_enabled.restype = ctypes.c_int
        lib.catkey_set_method.argtypes = [ctypes.c_int]
        lib.catkey_set_toggle_key.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.catkey_set_restore_key.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.catkey_is_running.restype = ctypes.c_int
        _HAS_HOOK = True
    except AttributeError:
        _HAS_HOOK = False
    return lib


def _try_build():
    """Best-effort build of the core lib so CatKey works out of the box."""
    import subprocess
    src = _CORE_DIR / "vietnamese_tep.c"
    hook = _CORE_DIR / "windows" / "catkey_hook.c"
    if not src.exists():
        return
    if sys.platform == "win32":
        out = _CORE_DIR / "catkey_core.dll"
        deff = _CORE_DIR / "catkey_core.def"
        srcs = [str(src)]
        if hook.exists():
            srcs.append(str(hook))
        # 1) try gcc/clang if on PATH (no vcvars needed)
        # The .def MUST come before the sources so MinGW exports the symbols
        # (functions are not __declspec(dllexport)); otherwise the DLL exposes
        # nothing and conversion silently fails on first run.
        for cc in ("gcc", "clang"):
            try:
                subprocess.run(
                    [cc, "-shared", "-O2", "-municode", "-o", str(out),
                     str(deff), *srcs, "-luser32", "-Wl,--kill-at,--out-implib,NUL"],
                    cwd=str(_CORE_DIR), capture_output=True, timeout=90, check=True,
                )
                if out.exists():
                    return
            except (OSError, subprocess.SubprocessError):
                pass
        # 2) try MSVC via any discoverable vcvars64.bat
        import glob
        roots = [
            r"C:\Program Files\Microsoft Visual Studio",
            r"C:\Program Files (x86)\Microsoft Visual Studio",
            r"E:\Visual Studio",
        ]
        vcvars = []
        for r in roots:
            vcvars += glob.glob(r + r"\**\vcvars64.bat", recursive=True)
        srcs_q = " ".join(f'"{s}"' for s in srcs)
        for vc in vcvars:
            try:
                cmd = (f'"{vc}" && cl /nologo /w /std:c17 /utf-8 /LD '
                       f'/Fe:"{out}" {srcs_q} /link /DEF:"{deff}" user32.lib')
                subprocess.run(["cmd", "/c", cmd], cwd=str(_CORE_DIR),
                               capture_output=True, timeout=180)
                if out.exists():
                    return
            except (OSError, subprocess.SubprocessError):
                pass
    else:
        out = _CORE_DIR / "libcatkey_core.so"
        for cc in ("cc", "gcc", "clang"):
            try:
                subprocess.run(
                    [cc, "-shared", "-fPIC", "-O2", "-o", str(out), str(src)],
                    cwd=str(_CORE_DIR), capture_output=True, timeout=60, check=True,
                )
                if out.exists():
                    return
            except (OSError, subprocess.SubprocessError):
                pass


def _load():
    # Only load a prebuilt library at import time. Building (which spawns a
    # compiler) is deferred to _ensure_core() so merely importing catkey_ui
    # does not trigger a toolchain invocation.
    for name in _lib_names():
        p = _CORE_DIR / name
        if p.exists():
            try:
                return _bind(ctypes.CDLL(str(p)))
            except OSError:
                pass
    return None


_LIB = _load()
_BUILT = False


def _ensure_core():
    """Lazily build the core library on first use if none was prebuilt."""
    global _LIB, _BUILT
    if _LIB is not None or _BUILT:
        return
    _BUILT = True
    _try_build()
    for name in _lib_names():
        p = _CORE_DIR / name
        if p.exists():
            try:
                _LIB = _bind(ctypes.CDLL(str(p)))
                return
            except OSError:
                pass


def core_available() -> bool:
    _ensure_core()
    return _LIB is not None


def convert_word(word: str, method: str) -> str:
    """Convert a word via the C core. method is 'teip', 'vni', 'viqr', 'teip_vni'."""
    if _LIB is None:
        _ensure_core()
    if _LIB is None:
        return word
    m = {'vni': _METHOD_VNI, 'viqr': _METHOD_VIQR,
         'teip_vni': _METHOD_TEIP_VNI}.get(method, _METHOD_TEIP)
    buf = ctypes.create_string_buffer(_MAX_OUTPUT)
    n = _LIB.catkey_convert_word(word.encode("utf-8"), buf, _MAX_OUTPUT, m)
    if n <= 0:
        return word
    return buf.raw[:n].decode("utf-8", errors="replace")


# --- System-wide hook engine (types into other apps) --------------------

def hook_available() -> bool:
    """True if the C core exposes the system-wide keyboard hook."""
    _ensure_core()
    return _LIB is not None and _HAS_HOOK


def hook_start() -> bool:
    if not hook_available():
        return False
    return bool(_LIB.catkey_start())


def hook_stop() -> None:
    if hook_available():
        _LIB.catkey_stop()


def hook_set_enabled(on: bool) -> None:
    if hook_available():
        _LIB.catkey_set_enabled(1 if on else 0)


def hook_set_method(method: str) -> None:
    if hook_available():
        m = {'vni': _METHOD_VNI, 'viqr': _METHOD_VIQR,
             'teip_vni': _METHOD_TEIP_VNI}.get(method, _METHOD_TEIP)
        _LIB.catkey_set_method(m)


def hook_is_running() -> bool:
    return hook_available() and bool(_LIB.catkey_is_running())


def hook_get_enabled() -> bool:
    return hook_available() and bool(_LIB.catkey_get_enabled())


# Modifier mask bits for the toggle hotkey
MOD_CTRL = 1
MOD_SHIFT = 2
MOD_ALT = 4


def hook_set_toggle_key(vk: int, mods: int) -> None:
    """Set the global VN/EN toggle hotkey. vk=0 => modifiers-only combo."""
    if hook_available():
        _LIB.catkey_set_toggle_key(int(vk), int(mods))


def hook_set_restore_key(vk: int, mods: int) -> None:
    """Set the restore-original-word hotkey. vk=0 => disabled."""
    if hook_available():
        _LIB.catkey_set_restore_key(int(vk), int(mods))
