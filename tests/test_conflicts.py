"""Unit tests for catkey_ui.conflicts"""
import unittest
from catkey_ui import conflicts


class TestConflicts(unittest.TestCase):
    def test_known_tools_dict(self):
        self.assertIn("unikey.exe", conflicts.KNOWN_TOOLS)
        self.assertIn("evkey.exe", conflicts.KNOWN_TOOLS)
        self.assertIn("ibus-bamboo", conflicts.KNOWN_TOOLS)

    def test_detect_conflicts_returns_list(self):
        res = conflicts.detect_conflicts()
        self.assertIsInstance(res, list)


if __name__ == "__main__":
    unittest.main()
