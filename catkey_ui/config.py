"""
CatKey - Vietnamese Input Method
Configuration management (JSON-backed)

Option set mirrors EVKey (input methods, character encodings, feature
toggles, shortkeys) so the UI can be a faithful clone. CatKey-specific
extras are grouped under the "catkey" section.
"""

import json
import os
import sys

from pathlib import Path

APP_NAME = "CatKey"
APP_VERSION = "0.0.1.0a"

# --- Input methods (EVKey parity) ---------------------------------------
# Only "Telex" and "VNI Windows" have a working conversion engine.
# The rest are UI-only; "(no conv.)" means the C core does not convert them yet.
INPUT_METHODS = [
    "Telex",
    "VNI Windows",
    "Simple Telex (no conv.)",
    "Simple Telex 2 (no conv.)",
    "Telex + VNI",
    "VIQR",
    "Microsoft VI Layout (no conv.)",
    "User defined (no conv.)",
]

# --- Character encodings (EVKey parity) ---------------------------------
CHARSETS = [
    "Unicode",
    "VNI Windows",
    "TCVN3 (ABC)",
    "Composite Unicode",
    "Unicode tổ hợp",
    "Vietnamese locale CP 1258",
    "Unicode C String",
    "UTF-8 Literal",
    "NCR Decimal",
    "Vietware X",
    "Vietware F",
]

# --- CatKey backend methods (platform-specific) -------------------------
# Kept from the original CatKey design; used for the platform daemon.
METHOD_BACKSPACE = "backspace"
METHOD_INLINE = "inline"
METHOD_IBUS = "ibus"
METHOD_FCITX = "fcitx"

METHODS = [
    {
        "id": METHOD_BACKSPACE,
        "name": "Backspace Method",
        "description": "Type to buffer, press Backspace to commit",
        "platforms": ["windows", "linux"],
    },
    {
        "id": METHOD_INLINE,
        "name": "Inline Method",
        "description": "Auto-convert while typing",
        "platforms": ["windows", "linux"],
    },
    {
        "id": METHOD_IBUS,
        "name": "IBus",
        "description": "Linux Input Bus framework",
        "platforms": ["linux"],
    },
    {
        "id": METHOD_FCITX,
        "name": "Fcitx",
        "description": "Flexible Input Method Framework (Linux)",
        "platforms": ["linux"],
    },
]

MODE_TEIP = "teip"
MODE_VNI = "vni"
MODE_VIQR = "viqr"
MODE_TEIP_VNI = "teip_vni"

DEFAULT_CONFIG = {
    # UI language: "en" or "vi" (interface language, not the typing engine)
    "ui_language": "en",

    # Core input (EVKey parity)
    "input_method": "Telex",       # index into INPUT_METHODS
    "charset": "Unicode",          # index into CHARSETS
    "vietnamese_on": True,

    # Spelling / typing behaviour
    "check_spelling": True,
    "free_marking": False,
    "auto_restore_wrong_spelling": True,
    "allow_fwjz_consonants": False,
    "auto_upper_after_punct": False,
    "allow_space_az": True,

    # Macro
    "macro_enabled": False,
    "macro_even_if_off": False,
    "macro_file": "",

    # Compatibility / advanced
    "modern_style": True,
    "standard_key_sending": False,
    "use_clipboard_send": False,
    "support_metro": False,
    "fix_browser_excel": False,

    # Shortkeys
    "shortkey_switch": "Ctrl+Shift",       # EN <-> VN
    "shortkey_restore": "Ctrl+Shift+Z",    # restore original word
    "shortkey_reset": "Ctrl+Shift+Alt+F12",

    # System
    "auto_run_boot": False,
    "run_as_admin": False,
    "show_dialog_startup": True,
    "notification_sounds": True,
    "notify_on_toggle": True,   # show a tray notification when VN typing on/off
    "auto_check_update": True,
    "customize_tray_icon": False,

    # Exceptions
    "exception_apps": [],
    "auto_prevent_vietnamese": False,

    # CatKey-specific extras (kept separate from EVKey parity)
    "catkey": {
        "method": METHOD_BACKSPACE,     # platform backend
        "input_mode": MODE_TEIP,        # engine mode for the C core
        "live_preview": True,
    },
}


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


def _config_path() -> Path:
    return _config_dir() / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return _deep_merge(DEFAULT_CONFIG, saved)
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy


def save_config(cfg: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_platform() -> str:
    return "windows" if sys.platform == "win32" else "linux"


def is_method_available(method_id: str) -> bool:
    platform = get_platform()
    for m in METHODS:
        if m["id"] == method_id:
            return platform in m["platforms"]
    return False


def set_autorun(enabled: bool) -> bool:
    """Enable/disable CatKey launching at user login.

    Windows: HKCU\\...\\Run registry value. Linux: XDG autostart .desktop.
    Returns True on success. Best-effort; failures are swallowed."""
    try:
        import sys
        if sys.platform == "win32":
            try:
                import winreg
            except Exception:
                return False
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            if enabled:
                cmd = '"{}" "{}"'.format(sys.executable, _entry_script())
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        else:
            autostart = Path.home() / ".config" / "autostart"
            dest = autostart / "catkey.desktop"
            if enabled:
                autostart.mkdir(parents=True, exist_ok=True)
                dest.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=CatKey\n"
                    "Comment=Vietnamese Input Method\n"
                    "Exec={} {}\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n".format(
                        sys.executable, _entry_script()),
                    encoding="utf-8")
            else:
                if dest.exists():
                    dest.unlink()
            return True
    except Exception:
        return False


def _entry_script() -> str:
    """Path to launch CatKey. In a frozen build this is the exe itself;
    from source it is run_ui.py next to the package."""
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable
    here = Path(__file__).resolve().parent.parent
    return str(here / "run_ui.py")
    return False
