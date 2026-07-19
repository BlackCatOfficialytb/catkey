"""
CatKey - global hotkey listener using pynput.

Runs a background keyboard listener and fires a callback when the configured
toggle combo is pressed (default Ctrl+Shift). Works system-wide, independent
of the C typing hook. The callback is invoked from the listener thread, so the
consumer must marshal to the GUI thread (we use a Qt signal for that).
"""

try:
    from pynput import keyboard
    _PYNPUT_AVAILABLE = True
except Exception:
    keyboard = None
    _PYNPUT_AVAILABLE = False


# map config modifier names -> pynput keys (both left/right variants)
if _PYNPUT_AVAILABLE and keyboard is not None:
    _MOD_KEYS = {
        "ctrl": {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
        "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
        "alt": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
                keyboard.Key.alt_gr},
    }
else:
    _MOD_KEYS = {}


def _parse(combo: str):
    """Return (set_of_required_mod_names, optional_letter_or_None)."""
    mods = set()
    letter = None
    for part in (combo or "").split("+"):
        p = part.strip().lower()
        if p in ("ctrl", "control"):
            mods.add("ctrl")
        elif p == "shift":
            mods.add("shift")
        elif p in ("alt", "meta"):
            mods.add("alt")
        elif len(p) == 1:
            letter = p
    if not mods:
        mods = {"ctrl", "shift"}
    return mods, letter


class HotkeyListener:
    def __init__(self, combo: str, on_trigger):
        self._required, self._letter = _parse(combo)
        self._on_trigger = on_trigger
        self._pressed_mods = set()   # names currently held
        self._letter_ok = self._letter is None
        self._fired = False
        self._listener = None

    def set_combo(self, combo: str):
        self._required, self._letter = _parse(combo)
        self._letter_ok = self._letter is None
        self._pressed_mods.clear()
        self._fired = False

    def start(self):
        if self._listener or not _PYNPUT_AVAILABLE or keyboard is None:
            return
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            self._listener = None

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _mod_name(self, key):
        for name, keys in _MOD_KEYS.items():
            if key in keys:
                return name
        return None

    def _on_press(self, key):
        name = self._mod_name(key)
        if name:
            self._pressed_mods.add(name)
        elif self._letter is not None:
            try:
                if hasattr(key, "char") and key.char and key.char.lower() == self._letter:
                    self._letter_ok = True
            except Exception:
                pass

        # Fire when all required mods are held and the letter (if any) matched.
        if (self._required.issubset(self._pressed_mods)
                and self._letter_ok and not self._fired):
            self._fired = True
            try:
                self._on_trigger()
            except Exception:
                pass

    def _on_release(self, key):
        name = self._mod_name(key)
        if name and name in self._pressed_mods:
            self._pressed_mods.discard(name)
        elif self._letter is not None:
            try:
                if hasattr(key, "char") and key.char and key.char.lower() == self._letter:
                    self._letter_ok = False
                    self._fired = False
            except Exception:
                pass
        # reset latch once the combo is broken
        if not self._required.issubset(self._pressed_mods):
            self._fired = False
            if self._letter is not None:
                self._letter_ok = False
