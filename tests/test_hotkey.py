"""Unit tests for catkey_ui.hotkey"""
import unittest
from catkey_ui.hotkey import _parse, HotkeyListener


class DummyKey:
    def __init__(self, char=None):
        self.char = char


class TestHotkey(unittest.TestCase):
    def test_parse_combo(self):
        mods, letter = _parse("Ctrl+Shift")
        self.assertEqual(mods, {"ctrl", "shift"})
        self.assertIsNone(letter)

        mods, letter = _parse("Ctrl+Shift+Z")
        self.assertEqual(mods, {"ctrl", "shift"})
        self.assertEqual(letter, "z")

        mods, letter = _parse("Alt+x")
        self.assertEqual(mods, {"alt"})
        self.assertEqual(letter, "x")

        mods, letter = _parse("")
        self.assertEqual(mods, {"ctrl", "shift"})
        self.assertIsNone(letter)

    def test_hotkey_listener_state(self):
        triggered = []
        hl = HotkeyListener("Ctrl+Shift+Z", lambda: triggered.append(True))
        hl.set_combo("Ctrl+Shift+X")
        self.assertEqual(hl._required, {"ctrl", "shift"})
        self.assertEqual(hl._letter, "x")


if __name__ == "__main__":
    unittest.main()
