"""Unit tests for catkey_ui.config"""
import unittest
import json
import tempfile
from pathlib import Path

from catkey_ui import config


class TestConfig(unittest.TestCase):
    def test_default_config_structure(self):
        cfg = config.DEFAULT_CONFIG
        self.assertIn("ui_language", cfg)
        self.assertIn("input_method", cfg)
        self.assertIn("charset", cfg)
        self.assertIn("vietnamese_on", cfg)
        self.assertIn("catkey", cfg)

    def test_deep_merge(self):
        base = {"a": 1, "b": {"x": 10, "y": 20}}
        override = {"b": {"y": 99, "z": 100}, "c": 3}
        merged = config._deep_merge(base, override)
        self.assertEqual(merged, {"a": 1, "b": {"x": 10, "y": 99, "z": 100}, "c": 3})

    def test_platform_check(self):
        p = config.get_platform()
        self.assertIn(p, ["windows", "linux"])

    def test_is_method_available(self):
        self.assertTrue(config.is_method_available(config.METHOD_BACKSPACE))
        self.assertTrue(config.is_method_available(config.METHOD_INLINE))
        if config.get_platform() == "windows":
            self.assertFalse(config.is_method_available(config.METHOD_IBUS))
            self.assertFalse(config.is_method_available(config.METHOD_FCITX))
        else:
            self.assertTrue(config.is_method_available(config.METHOD_IBUS))
            self.assertTrue(config.is_method_available(config.METHOD_FCITX))

    def test_save_and_load_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_dir = config._config_dir
            config._config_dir = lambda: Path(tmpdir)
            try:
                cfg = config.load_config()
                cfg["input_method"] = "VNI Windows"
                cfg["vietnamese_on"] = False
                config.save_config(cfg)

                loaded = config.load_config()
                self.assertEqual(loaded["input_method"], "VNI Windows")
                self.assertFalse(loaded["vietnamese_on"])
            finally:
                config._config_dir = orig_dir

    def test_autorun_path_escaping(self):
        # Backslashes and embedded double-quotes must be escaped.
        self.assertEqual(config._escape_win_arg(r'a\b"c'), 'a\\\\b\\"c')
        self.assertEqual(config._desktop_quote("a b"), '"a b"')
        self.assertEqual(config._desktop_quote('a"b'), '"a\\"b"')


if __name__ == "__main__":
    unittest.main()
