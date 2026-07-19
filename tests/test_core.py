"""Unit tests for catkey_ui.core"""
import unittest
import sys
import os

from catkey_ui import core


class TestCore(unittest.TestCase):
    def test_core_available(self):
        self.assertTrue(core.core_available(), "Core C library should be available")

    def test_convert_teip(self):
        cases = [
            ("dd", "đ"),
            ("DD", "Đ"),
            ("Dd", "Đ"),
            ("dD", "Đ"),
            ("aa", "â"),
            ("aw", "ă"),
            ("ee", "ê"),
            ("oo", "ô"),
            ("ow", "ơ"),
            ("uw", "ư"),
            ("uow", "ươ"),
            ("w", "ư"),
            ("W", "Ư"),
            ("wn", "ưn"),
            ("quas", "quá"),
            ("quys", "quý"),
            ("gias", "giá"),
            ("giof", "giò"),
            ("vieejt", "việt"),
            ("tieengs", "tiếng"),
            ("hoanf", "hoàn"),
            ("huyeenf", "huyền"),
            ("chaof", "chào"),
            ("nguyeexn", "nguyễn"),
            ("khoong", "không"),
        ]
        for word, expected in cases:
            res = core.convert_word(word, "teip")
            self.assertEqual(res, expected, f"Failed converting '{word}' (got '{res}', expected '{expected}')")

    def test_convert_vni(self):
        cases = [
            ("d9", "đ"),
            ("a6", "â"),
            ("a8", "ă"),
            ("e6", "ê"),
            ("o6", "ô"),
            ("o7", "ơ"),
            ("u7", "ư"),
            ("uo7", "ươ"),
            ("u7o7", "ươ"),
            ("vie65t", "việt"),
            ("tie61ng", "tiếng"),
            ("qua1", "quá"),
            ("gia1", "giá"),
        ]
        for word, expected in cases:
            res = core.convert_word(word, "vni")
            self.assertEqual(res, expected, f"Failed converting '{word}' via VNI (got '{res}', expected '{expected}')")

    def test_convert_viqr(self):
        cases = [
            ("dd", "đ"),
            ("DD", "Đ"),
            ("vie^'t", "viết"),
            ("nu+o+'c", "nước"),
            ("ngu+o+`i", "người"),
        ]
        for word, expected in cases:
            res = core.convert_word(word, "viqr")
            self.assertEqual(res, expected, f"Failed converting '{word}' via VIQR (got '{res}', expected '{expected}')")

    def test_convert_empty_or_raw(self):
        self.assertEqual(core.convert_word("", "teip"), "")
        self.assertEqual(core.convert_word("hello", "teip"), "hello")


if __name__ == "__main__":
    unittest.main()
