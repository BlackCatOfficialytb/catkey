"""Unit tests for catkey_ui.i18n"""
import unittest
from catkey_ui import i18n


class TestI18n(unittest.TestCase):
    def test_translation_fallback(self):
        i18n.set_language("en")
        self.assertEqual(i18n.current_language(), "en")
        self.assertEqual(i18n._("Apply"), "Apply")

    def test_switch_language(self):
        i18n.set_language("vi")
        self.assertEqual(i18n.current_language(), "vi")
        # Switch back to en
        i18n.set_language("en")
        self.assertEqual(i18n.current_language(), "en")


if __name__ == "__main__":
    unittest.main()
