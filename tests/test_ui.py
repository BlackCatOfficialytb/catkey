"""Unit tests for catkey_ui.app and MainWindow"""
import unittest
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from catkey_ui.app import MainWindow
from catkey_ui.config import DEFAULT_CONFIG


class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_main_window_creation(self):
        cfg = dict(DEFAULT_CONFIG)
        window = MainWindow(cfg)
        self.assertEqual(window.tabs.count(), 7)
        self.assertIsNotNone(window.cmb_method)
        self.assertIsNotNone(window.cmb_charset)

    def test_live_preview_updates(self):
        cfg = dict(DEFAULT_CONFIG)
        window = MainWindow(cfg)
        window.preview_input.setText("vieejt nam")
        self.assertEqual(window.preview_output.text(), "việt nam")

    def test_language_toggle(self):
        cfg = dict(DEFAULT_CONFIG)
        window = MainWindow(cfg)
        self.assertEqual(window.btn_lang.text(), "Tiếng Việt")
        window._toggle_language()
        self.assertEqual(window.btn_lang.text(), "English")
        window._toggle_language()
        self.assertEqual(window.btn_lang.text(), "Tiếng Việt")

    def test_catkey_app_initialization(self):
        from catkey_ui.app import CatKeyApp
        app_inst = CatKeyApp()
        self.assertTrue(hasattr(app_inst, "window"))
        self.assertTrue(hasattr(app_inst, "tray"))
        initial_state = app_inst.config.get("vietnamese_on", True)
        app_inst._toggle_vietnamese()
        self.assertEqual(app_inst.config["vietnamese_on"], not initial_state)
        app_inst._toggle_vietnamese()
        self.assertEqual(app_inst.config["vietnamese_on"], initial_state)
        app_inst._set_method("VNI Windows")
        self.assertEqual(app_inst.config["input_method"], "VNI Windows")
        app_inst._set_method("Telex")
        self.assertEqual(app_inst.config["input_method"], "Telex")


if __name__ == "__main__":
    unittest.main()
