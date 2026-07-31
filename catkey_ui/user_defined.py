"""
CatKey - User Defined Input Method customizer.

Saves configuration to settings.toml:
  [settings]
  # User-defined method name loaded from a known preset, or empty
  loaded_preset = ""

  [user_defined_method_input]
  # key = what the new key should do (tone mark, diacritic rule, combined char)
  # string keys, string values
"""

import sys
import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python >= 3.11
except ImportError:
    tomllib = None  # type: ignore


def _data_root() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "CatKey" / "settings.toml"


_SETTINGS_PATH = _settings_path()

# Preset input methods users can load as a starting point.
PRESETS = [
    "Telex",
    "VNI",
    "VIQR",
    "Microsoft VI Layout",
    "Telex đơn giản (Simple Telex)",
    "Telex đơn giản 2 (Simple Telex 2)",
    "Telex + VNI",
]

# Vietnamese tone-mark / diacritic / combined-character options
# for the "Dùng cho" (Used for) drop-down.
TONE_MARKS = [
    # Tone marks
    "Xoá dấu (Remove tone)",
    "Dấu Sắc (Acute)",
    "Dấu Huyền (Grave)",
    "Dấu Hỏi (Hook)",
    "Dấu Ngã (Tilde)",
    "Dấu Nặng (Dot below)",
]

DIACRITIC_RULES = [
    # Diacritic rules
    "Dấu mũ chung cho a, e, o thành â, ê, ô (Circumflex rule for a, e, o)",
    "Dấu mũ cho a thành â (Circumflex for a)",
    "Dấu mũ cho e thành ê (Circumflex for e)",
    "Dấu mũ cho o thành ô (Circumflex for o)",
    "Dấu trăng cho a thành ă (Breve for a)",
    "Dấu sừng cho o thành ơ (Horn for o)",
    "Dấu sừng cho u thành ư (Horn for u)",
    "Dấu móc cho o thành ơ (Horn for o)",
    "Dấu móc cho u thành ư (Horn for u)",
]

COMBINED_CHARS = [
    # Combined characters (precomposed / specific mappings)
    "Chữ ă (a with breve)",
    "Chữ Ă (A with breve)",
    "Chữ â (a with circumflex)",
    "Chữ Â (A with circumflex)",
    "Chữ đ (d with stroke)",
    "Chữ Đ (D with stroke)",
    "Chữ ê (e with circumflex)",
    "Chữ Ê (E with circumflex)",
    "Chữ ô (o with circumflex)",
    "Chữ Ô (O with circumflex)",
    "Chữ ơ (o with horn)",
    "Chữ Ơ (O with horn)",
    "Chữ ư (u with horn)",
    "Chữ Ư (U with horn)",
    "Chữ á (a with acute)",
    "Chữ Á (A with acute)",
    "Chữ à (a with grave)",
    "Chữ À (A with grave)",
    "Chữ ả (a with hook)",
    "Chữ Ả (A with hook)",
    "Chữ ã (a with tilde)",
    "Chữ Ã (A with tilde)",
    "Chữ ạ (a with dot below)",
    "Chữ Ạ (A with dot below)",
]

# Combined list for the drop-down
ALL_USED_FOR = TONE_MARKS + DIACRITIC_RULES + COMBINED_CHARS


def load_settings() -> dict[str, Any]:
    """Load user-defined method settings from settings.toml.

    Returns a dict with:
      loaded_preset: str (from [settings])
      defined_keys: dict[str, str] (from [user_defined_method_input])
    """
    if not _SETTINGS_PATH.exists():
        return {"loaded_preset": "", "defined_keys": {}}

    if tomllib is not None:
        try:
            with open(_SETTINGS_PATH, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            data = {}
    else:
        # Minimal TOML parser for just the sections we need.
        data = _parse_toml_minimal()
    settings = data.get("settings", {})
    udm = data.get("user_defined_method_input", {})
    return {
        "loaded_preset": settings.get("loaded_preset", ""),
        "defined_keys": udm if isinstance(udm, dict) else {},
    }


def _parse_toml_minimal() -> dict[str, Any]:
    """Fallback TOML reader for when tomllib is not available."""
    result: dict[str, Any] = {}
    current_section = ""
    try:
        lines = _SETTINGS_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return result

    for line in lines:
        stripped = line.strip()
        # skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        # section header
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            if current_section not in result:
                result[current_section] = {}
            continue
        # key = value
        if "=" in stripped and current_section:
            k, v = stripped.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            result[current_section][k] = v
            continue
    return result


def save_settings(loaded_preset: str, defined_keys: dict[str, str]) -> None:
    """Write user-defined settings to settings.toml with English comments."""
    lines: list[str] = []
    lines.append("# CatKey User Defined Input Method settings")
    lines.append("# Edit manually or use the built-in customizer dialog.")
    lines.append("")
    lines.append("# General settings for the customizer")
    lines.append("[settings]")
    lines.append(f'loaded_preset = "{loaded_preset}"  # preset loaded via "Load this typing method"')
    lines.append("")
    lines.append("# User-defined key mappings")
    lines.append("# Each entry maps a key (letter or digit) to an action (tone/diacritic/character)")
    lines.append("[user_defined_method_input]")
    for key, action in defined_keys.items():
        # TOML basic string: double-quoted
        lines.append(f'{key} = "{action}"')
    if not defined_keys:
        lines.append("# Add entries like: a = \"Dấu Sắc (Acute)\"")
    lines.append("")

    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Dark-themed customizer dialog (matching EVKey's User defined input method)
# ---------------------------------------------------------------------------

def _dark_stylesheet() -> str:
    """Return a QSS stylesheet for a dark VS Code-like theme."""
    return """
        QDialog {
            background-color: #1e1e1e;
            color: #d4d4d4;
        }
        QLabel {
            color: #d4d4d4;
            font-size: 13px;
        }
        QGroupBox {
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            color: #cccccc;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            left: 8px;
            color: #9cdcfe;
        }
        QComboBox {
            background-color: #2d2d2d;
            border: 1px solid #3c3c3c;
            border-radius: 3px;
            padding: 4px 8px;
            color: #d4d4d4;
            min-width: 180px;
        }
        QComboBox:hover {
            border-color: #007acc;
        }
        QComboBox:focus {
            border-color: #007acc;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #3c3c3c;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #d4d4d4;
            width: 0; height: 0;
        }
        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            border: 1px solid #3c3c3c;
            selection-background-color: #007acc;
            color: #d4d4d4;
            outline: none;
        }
        QTableWidget {
            background-color: #252526;
            border: 1px solid #3c3c3c;
            gridline-color: #3c3c3c;
            color: #d4d4d4;
            alternate-background-color: #2d2d2d;
        }
        QTableWidget::item {
            padding: 4px 8px;
            border: none;
        }
        QTableWidget::item:selected {
            background-color: #007acc;
            color: white;
        }
        QHeaderView::section {
            background-color: #1e1e1e;
            border: 1px solid #3c3c3c;
            padding: 4px 8px;
            color: #9cdcfe;
            font-weight: bold;
        }
        QPushButton {
            background-color: #0e639c;
            border: none;
            border-radius: 3px;
            padding: 6px 14px;
            color: white;
            font-weight: 500;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:pressed {
            background-color: #0d5a8a;
        }
        QPushButton:disabled {
            background-color: #3c3c3c;
            color: #6a6a6a;
        }
        QLineEdit {
            background-color: #2d2d2d;
            border: 1px solid #3c3c3c;
            border-radius: 3px;
            padding: 4px 8px;
            color: #d4d4d4;
        }
        QLineEdit:focus {
            border-color: #007acc;
        }
        QScrollBar:vertical {
            background: #1e1e1e;
            width: 12px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: #424242;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #4e4e4e;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollArea {
            border: none;
            background: #1e1e1e;
        }
    """


def _get_preset_definition(name: str) -> dict[str, str]:
    """Return default key mappings for a built-in preset.

    These are illustrative starter mappings; the user can edit them.
    """
    if name == "Telex":
        return {
            "s": "Dấu Sắc (Acute)",
            "f": "Dấu Huyền (Grave)",
            "r": "Dấu Hỏi (Hook)",
            "x": "Dấu Ngã (Tilde)",
            "j": "Dấu Nặng (Dot below)",
            "z": "Xoá dấu (Remove tone)",
            "w": "Dấu sừng/móc cho u/o (Horn for u/o)",
            "a": "Dấu mũ/breve cho a (Circumflex/Breve for a)",
            "e": "Dấu mũ cho e (Circumflex for e)",
            "o": "Dấu mũ/breve cho o (Circumflex/Horn for o)",
            "d": "Chữ đ (d with stroke)",
        }
    if name == "VNI":
        return {
            "1": "Dấu Sắc (Acute)",
            "2": "Dấu Huyền (Grave)",
            "3": "Dấu Hỏi (Hook)",
            "4": "Dấu Ngã (Tilde)",
            "5": "Dấu Nặng (Dot below)",
            "0": "Xoá dấu (Remove tone)",
            "6": "Dấu mũ cho a/e/o (Circumflex for a/e/o)",
            "7": "Dấu móc cho o/u (Horn for o/u)",
            "8": "Dấu trăng cho a (Breve for a)",
            "9": "Chữ đ (d with stroke)",
        }
    if name == "VIQR":
        return {
            "'": "Dấu Sắc (Acute)",
            "`": "Dấu Huyền (Grave)",
            "?": "Dấu Hỏi (Hook)",
            "~": "Dấu Ngã (Tilde)",
            ".": "Dấu Nặng (Dot below)",
            "^": "Dấu mũ (Circumflex)",
            "(": "Dấu trăng (Breve)",
            "+": "Dấu móc (Horn)",
            "d": "Chữ đ (d with stroke)",
        }
    if name == "Telex + VNI":
        return {
            "s": "Dấu Sắc (Acute)",
            "f": "Dấu Huyền (Grave)",
            "r": "Dấu Hỏi (Hook)",
            "x": "Dấu Ngã (Tilde)",
            "j": "Dấu Nặng (Dot below)",
            "z": "Xoá dấu (Remove tone)",
            "w": "Dấu sừng/móc cho u/o (Horn for u/o)",
            "a": "Dấu mũ/breve cho a (Circumflex/Breve for a)",
            "e": "Dấu mũ cho e (Circumflex for e)",
            "o": "Dấu mũ/breve cho o (Circumflex/Horn for o)",
            "d": "Chữ đ (d with stroke)",
            "1": "Dấu Sắc (Acute)",
            "2": "Dấu Huyền (Grave)",
            "3": "Dấu Hỏi (Hook)",
            "4": "Dấu Ngã (Tilde)",
            "5": "Dấu Nặng (Dot below)",
            "6": "Dấu mũ cho a/e/o (Circumflex for a/e/o)",
            "7": "Dấu móc cho o/u (Horn for o/u)",
            "8": "Dấu trăng cho a (Breve for a)",
            "9": "Chữ đ (d with stroke)",
            "0": "Xoá dấu (Remove tone)",
        }
    return {}


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QLineEdit, QScrollArea, QWidget, QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPolygon
from PySide6.QtCore import QPoint


def _make_lv_icon() -> QIcon:
    """Create the L/V red/blue square icon for the title bar."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    # Red square (left) with "L"
    p.setBrush(QColor("#e74c3c"))
    p.drawRoundedRect(0, 0, 16, 32, 4, 4)
    # Blue square (right) with "V"
    p.setBrush(QColor("#3498db"))
    p.drawRoundedRect(16, 0, 16, 32, 4, 4)
    # Text
    p.setPen(QColor("white"))
    p.setFont(QFont("Arial", 11, QFont.Bold))
    p.drawText(0, 0, 16, 32, Qt.AlignCenter, "L")
    p.drawText(16, 0, 16, 32, Qt.AlignCenter, "V")
    p.end()
    return QIcon(pix)


class UserDefinedDialog(QDialog):
    """Dark-themed dialog for customizing the User Defined input method.

    Matches EVKey's "User defined input method" customizer.
    Configuration is saved to settings.toml alongside the executable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User defined input method")
        self.setWindowIcon(_make_lv_icon())
        self.setMinimumSize(700, 550)
        self.setStyleSheet(_dark_stylesheet())

        self._settings = load_settings()
        self._defined_keys = dict(self._settings.get("defined_keys", {}))
        self._loaded_preset = self._settings.get("loaded_preset", "")

        self._build_ui()
        self._populate_table_from_keys()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ============================================================
        # GROUP 1: "Kiểu gõ sẵn có" (Existing Typing Methods)
        # ============================================================
        group1 = QGroupBox("Kiểu gõ sẵn có")
        g1_layout = QHBoxLayout(group1)
        g1_layout.setSpacing(8)

        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(PRESETS)
        # Default to first preset if nothing loaded
        if self._loaded_preset and self._loaded_preset in PRESETS:
            self.cmb_preset.setCurrentText(self._loaded_preset)
        else:
            self.cmb_preset.setCurrentIndex(0)

        self.cmb_preset.setMinimumWidth(300)
        g1_layout.addWidget(self.cmb_preset, 1)

        btn_load = QPushButton("Nạp kiểu gõ này")
        btn_load.clicked.connect(self._on_load_preset)
        btn_load.setMinimumWidth(140)
        g1_layout.addWidget(btn_load)

        root.addWidget(group1)

        # ============================================================
        # GROUP 2: "Định nghĩa phím" (Key Definitions)
        # ============================================================
        group2 = QGroupBox("Định nghĩa phím")
        g2_layout = QVBoxLayout(group2)
        g2_layout.setSpacing(8)

        # --- Input row: Phím + Dùng cho ---
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        lbl_key = QLabel("Phím:")
        lbl_key.setFixedWidth(40)
        input_row.addWidget(lbl_key)

        self.edit_key = QLineEdit()
        self.edit_key.setPlaceholderText("Nhập phím...")
        self.edit_key.setMaximumWidth(80)
        self.edit_key.setMinimumWidth(60)
        input_row.addWidget(self.edit_key)

        lbl_used = QLabel("Dùng cho:")
        lbl_used.setFixedWidth(60)
        input_row.addWidget(lbl_used)

        self.cmb_used_for = QComboBox()
        self.cmb_used_for.addItems(ALL_USED_FOR)
        self.cmb_used_for.setEditable(False)
        self.cmb_used_for.setMinimumWidth(300)
        input_row.addWidget(self.cmb_used_for, 1)

        g2_layout.addLayout(input_row)

        # --- Action buttons: Thêm / Thay thế ---
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        btn_add = QPushButton("Thêm")
        btn_add.clicked.connect(self._on_add)
        btn_add.setMinimumWidth(100)
        action_row.addWidget(btn_add)

        btn_replace = QPushButton("Thay thế")
        btn_replace.clicked.connect(self._on_replace)
        btn_replace.setMinimumWidth(100)
        action_row.addWidget(btn_replace)

        action_row.addStretch()
        g2_layout.addLayout(action_row)

        # --- Mapping table ---
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Phím", "Dùng cho"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(250)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)

        g2_layout.addWidget(self.table, 1)

        # --- Delete button (bottom-left of table area) ---
        del_row = QHBoxLayout()
        btn_delete = QPushButton("Xoá")
        btn_delete.clicked.connect(self._on_delete)
        btn_delete.setMinimumWidth(100)
        del_row.addWidget(btn_delete)
        del_row.addStretch()
        g2_layout.addLayout(del_row)

        root.addWidget(group2, 1)

        # ============================================================
        # MAIN BUTTONS: Lưu / Đóng (bottom-right)
        # ============================================================
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_save = QPushButton("Lưu")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save)
        btn_save.setMinimumWidth(100)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.reject)
        btn_close.setMinimumWidth(100)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

    def _populate_table_from_keys(self):
        """Fill the table from current _defined_keys dict."""
        self.table.setRowCount(0)
        for key, action in self._defined_keys.items():
            self._add_table_row(key, action)

    def _add_table_row(self, key: str, action: str):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Key column
        key_item = QTableWidgetItem(key)
        key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
        key_item.setTextAlignment(Qt.AlignCenter)
        key_item.setFont(QFont("Consolas", 11))
        self.table.setItem(row, 0, key_item)

        # Used for column
        action_item = QTableWidgetItem(action)
        action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, action_item)

    def _on_load_preset(self):
        """Load the selected preset into the table (replaces all current mappings)."""
        preset_name = self.cmb_preset.currentText()
        self._loaded_preset = preset_name
        preset_map = _get_preset_definition(preset_name)

        # Clear table and dict
        self._defined_keys.clear()
        self.table.setRowCount(0)

        # Add preset mappings
        for key, action in preset_map.items():
            self._defined_keys[key] = action
            self._add_table_row(key, action)

        QMessageBox.information(
            self,
            "Đã tải",
            f"Đã tải quy tắc cho phương pháp: {preset_name}\n"
            f"Bạn có thể chỉnh sửa thêm trước khi lưu."
        )

    def _on_table_selection_changed(self):
        """When user selects a row, fill the input fields for editing."""
        selected = self.table.selectedItems()
        if not selected:
            self.edit_key.clear()
            self.cmb_used_for.setCurrentIndex(0)
            return
        row = selected[0].row()
        key = self.table.item(row, 0).text()
        action = self.table.item(row, 1).text()
        self.edit_key.setText(key)
        idx = self.cmb_used_for.findText(action)
        if idx >= 0:
            self.cmb_used_for.setCurrentIndex(idx)
        else:
            self.cmb_used_for.setCurrentIndex(0)

    def _on_add(self):
        """Add a new key mapping from input fields."""
        key = self.edit_key.text().strip()
        action = self.cmb_used_for.currentText()

        if not key:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập phím (Key).")
            return
        if self.cmb_used_for.currentIndex() < 0:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn 'Dùng cho'.")
            return

        # Check if key already exists
        if key in self._defined_keys:
            QMessageBox.warning(
                self, "Đã tồn tại",
                f"Phím '{key}' đã có trong danh sách. Hãy chọn 'Thay thế' nếu muốn cập nhật."
            )
            return

        self._defined_keys[key] = action
        self._add_table_row(key, action)
        self.edit_key.clear()
        self.cmb_used_for.setCurrentIndex(0)
        self.table.clearSelection()

    def _on_replace(self):
        """Replace the selected row's mapping with input fields."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn một dòng trong bảng để thay thế.")
            return

        key = self.edit_key.text().strip()
        action = self.cmb_used_for.currentText()

        if not key:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập phím (Key).")
            return
        if self.cmb_used_for.currentIndex() < 0:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn 'Dùng cho'.")
            return

        row = selected[0].row()
        old_key = self.table.item(row, 0).text()

        # If key changed, remove old and add new
        if key != old_key:
            if key in self._defined_keys:
                QMessageBox.warning(
                    self, "Đã tồn tại",
                    f"Phím '{key}' đã có trong danh sách."
                )
                return
            self._defined_keys.pop(old_key, None)

        self._defined_keys[key] = action
        self.table.item(row, 0).setText(key)
        self.table.item(row, 1).setText(action)
        self.edit_key.clear()
        self.cmb_used_for.setCurrentIndex(0)
        self.table.clearSelection()

    def _on_delete(self):
        """Delete the selected row from table and dict."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn một dòng trong bảng để xoá.")
            return

        row = selected[0].row()
        key = self.table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Xác nhận xoá",
            f"Xoá quy tắc cho phím '{key}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._defined_keys.pop(key, None)
        self.table.removeRow(row)
        self.edit_key.clear()
        self.cmb_used_for.setCurrentIndex(0)

    def _on_save(self):
        save_settings(self._loaded_preset, self._defined_keys)
        self.accept()


def show_user_defined_dialog(parent=None) -> bool:
    """Show the User Defined customizer dialog.

    Returns True if user saved, False if cancelled.
    """
    dlg = UserDefinedDialog(parent)
    return dlg.exec() == QDialog.Accepted