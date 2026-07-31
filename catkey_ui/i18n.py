"""
CatKey - interface translation via gettext.

Uses standard .po/.mo catalogs in locales/<lang>/LC_MESSAGES/catkey.mo
(editable with Poedit). English is the source language: msgid strings are the
English text, so English needs no catalog (msgid is returned as-is).

Usage:
    from .i18n import set_language, _
    set_language("vi")
    label.setText(_("Apply"))
"""

import gettext
import sys
from pathlib import Path

LANG_EN = "en"
LANG_VI = "vi"


def _data_root() -> Path:
    # Frozen (PyInstaller/Nuitka onefile) bundles data next to _MEIPASS/exe.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_LOCALE_DIR = _data_root() / "locales"
_DOMAIN = "catkey"

_current = LANG_EN
_translation = gettext.NullTranslations()


class _PoTranslations(gettext.NullTranslations):
    """A gettext catalog backed by an in-memory {msgid: msgstr} map.

    We parse .po files directly instead of requiring a compiled .mo, so
    translations work out of the box without a msgfmt build step (and in
    read-only frozen bundles). Empty msgstr entries fall back to the msgid.
    """

    def __init__(self, catalog: dict):
        super().__init__()
        self._catalog = catalog

    def gettext(self, message: str) -> str:
        return self._catalog.get(message) or message

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        msg = singular if n == 1 else plural
        return self._catalog.get(msg) or msg


def _unquote_po(line: str) -> str:
    """Decode a double-quoted .po string fragment (unescaping \\n, \\t, \\", \\\\)."""
    line = line.strip()
    if len(line) >= 2 and line[0] == '"' and line[-1] == '"':
        line = line[1:-1]
    return (line.replace('\\\\', '\\').replace('\\"', '"')
                .replace('\\n', '\n').replace('\\t', '\t'))


def _parse_po(path: Path) -> dict:
    """Minimal .po parser -> {msgid: msgstr}. Ignores plurals/contexts/fuzzy."""
    catalog = {}
    cur_id = []
    cur_str = []
    target = None  # 'id' or 'str'
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    lines.append("")  # sentinel to flush the final entry

    def flush():
        if cur_id or cur_str:
            key = "".join(cur_id)
            val = "".join(cur_str)
            if key:  # skip the header entry (empty msgid)
                catalog[key] = val

    for raw in lines:
        line = raw.strip()
        if line.startswith("#") or line == "":
            if line == "":
                flush()
                cur_id, cur_str, target = [], [], None
            continue
        if line.startswith("msgid "):
            flush()
            cur_id, cur_str, target = [], [], "id"
            cur_id.append(_unquote_po(line[len("msgid "):]))
        elif line.startswith("msgstr "):
            target = "str"
            cur_str.append(_unquote_po(line[len("msgstr "):]))
        elif line.startswith("msgid_plural ") or line.startswith("msgctxt "):
            # Not used by CatKey's catalog; ignore this entry cleanly.
            target = None
        elif line.startswith('"'):
            if target == "id":
                cur_id.append(_unquote_po(line))
            elif target == "str":
                cur_str.append(_unquote_po(line))
    flush()
    return catalog


def set_language(lang: str) -> None:
    """Load the catalog for `lang`. Falls back to source (English) msgids."""
    global _current, _translation
    _current = lang if lang in (LANG_EN, LANG_VI) else LANG_EN
    if _current == LANG_EN:
        _translation = gettext.NullTranslations()
        return
    # Prefer a compiled .mo if present; otherwise parse the .po directly.
    try:
        _translation = gettext.translation(
            _DOMAIN, localedir=str(_LOCALE_DIR), languages=[_current],
        )
        return
    except (OSError, FileNotFoundError):
        pass
    po = _LOCALE_DIR / _current / "LC_MESSAGES" / (_DOMAIN + ".po")
    try:
        _translation = _PoTranslations(_parse_po(po))
    except (OSError, FileNotFoundError):
        _translation = gettext.NullTranslations()


def current_language() -> str:
    return _current


def _(message: str) -> str:
    """Translate `message` (an English source string / msgid)."""
    return _translation.gettext(message)
