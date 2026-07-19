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
    "Telex + VNI (no conv.)",
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
