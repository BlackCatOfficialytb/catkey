"""
CatKey - Vietnamese Input Method
PySide6 UI - a clone of the EVKey settings interface, with CatKey extras.

Architecture: all Vietnamese conversion happens in the C core (catkey_core
DLL/so) accessed via catkey_ui.core. This module is UI/UX only.
"""

import sys

from PySide6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
    QGroupBox,
    QLineEdit,
    QKeySequenceEdit,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSharedMemory, QObject
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QAction, QKeySequence, QActionGroup,
)

from .config import (
    APP_NAME,
    APP_VERSION,
    INPUT_METHODS,
    CHARSETS,
    METHODS,
    MODE_TEIP,
    MODE_VNI,
    MODE_VIQR,
    MODE_TEIP_VNI,
    load_config,
    save_config,
    get_platform,
    is_method_available,
)
from .core import (
    convert_word, core_available,
    hook_available, hook_start, hook_stop, hook_set_enabled, hook_set_method,
    hook_get_enabled,
)
from .i18n import _, set_language, current_language, LANG_EN, LANG_VI

# Win32 virtual-key codes used by the C hook hotkey ABI (vk, mods).
# mods mask: 1=Ctrl, 2=Shift, 4=Alt. vk=0 => modifiers-only combo.
_VK = {
    Qt.Key_A: 0x41, Qt.Key_B: 0x42, Qt.Key_C: 0x43, Qt.Key_D: 0x44,
    Qt.Key_E: 0x45, Qt.Key_F: 0x46, Qt.Key_G: 0x47, Qt.Key_H: 0x48,
    Qt.Key_I: 0x49, Qt.Key_J: 0x4A, Qt.Key_K: 0x4B, Qt.Key_L: 0x4C,
    Qt.Key_M: 0x4D, Qt.Key_N: 0x4E, Qt.Key_O: 0x4F, Qt.Key_P: 0x50,
    Qt.Key_Q: 0x51, Qt.Key_R: 0x52, Qt.Key_S: 0x53, Qt.Key_T: 0x54,
    Qt.Key_U: 0x55, Qt.Key_V: 0x56, Qt.Key_W: 0x57, Qt.Key_X: 0x58,
    Qt.Key_Y: 0x59, Qt.Key_Z: 0x5A,
    Qt.Key_F1: 0x70, Qt.Key_F2: 0x71, Qt.Key_F3: 0x72, Qt.Key_F4: 0x73,
    Qt.Key_F5: 0x74, Qt.Key_F6: 0x75, Qt.Key_F7: 0x76, Qt.Key_F8: 0x77,
    Qt.Key_F9: 0x78, Qt.Key_F10: 0x79, Qt.Key_F11: 0x7A, Qt.Key_F12: 0x7B,
    Qt.Key_Space: 0x20, Qt.Key_Tab: 0x09, Qt.Key_Backspace: 0x08,
    Qt.Key_Return: 0x0D, Qt.Key_Delete: 0x2E, Qt.Key_Insert: 0x2D,
}


def _seq_to_vk_mods(seq: str):
    """Convert a QKeySequence string (e.g. 'Ctrl+Shift+Z') to (vk, mods).

    mods mask: 1=Ctrl, 2=Shift, 4=Alt. Returns (0, 0) if empty/unparseable."""
    if not seq:
        return 0, 0
    mods = 0
    vk = 0
    for part in (seq or "").split("+"):
        p = part.strip().lower()
        if p == "ctrl" or p == "control":
            mods |= 1
        elif p == "shift":
            mods |= 2
        elif p == "alt" or p == "meta":
            mods |= 4
        elif len(p) == 1:
            key = getattr(Qt, "Key_" + p.upper(), None)
            vk = _VK.get(key, 0) if key is not None else 0
    return vk, mods


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

def _cat_icon(on: bool = True) -> QIcon:
    """Cat-face tray icon; green when VN mode on, grey when off (EVKey style)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPolygon

    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    face = QColor("#43A047") if on else QColor("#9E9E9E")
    p.setBrush(face)
    p.setPen(Qt.NoPen)
    p.drawEllipse(8, 12, 48, 44)
    p.drawPolygon(QPolygon([QPoint(12, 16), QPoint(20, 2), QPoint(28, 16)]))
    p.drawPolygon(QPolygon([QPoint(36, 16), QPoint(44, 2), QPoint(52, 16)]))

    p.setBrush(QColor("#212121"))
    p.drawEllipse(20, 26, 7, 8)
    p.drawEllipse(37, 26, 7, 8)
    p.setBrush(QColor("#E91E63"))
    p.drawEllipse(29, 38, 6, 4)
    p.setPen(QColor("#212121"))
    p.drawLine(6, 36, 24, 38)
    p.drawLine(6, 42, 24, 42)
    p.drawLine(40, 38, 58, 36)
    p.drawLine(40, 42, 58, 42)
    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# Main Window - EVKey settings clone
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    config_changed = Signal(dict)
    exit_requested = Signal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self._allow_close = False
        self.setWindowTitle(f"{APP_NAME} - Vietnamese Keyboard")
        self.setWindowIcon(_cat_icon())
        self.setMinimumWidth(560)
        self._checks = {}
        # List of (widget, english_msgid, setter) to re-translate on demand.
        self._tr_widgets = []
        set_language(config.get("ui_language", LANG_EN))
        self._build_ui()
        self._load_values()
        self._retranslate()

    # -- UI construction --------------------------------------------------

    def _track(self, widget, msgid: str, setter="setText"):
        """Register a widget whose text is the English source string `msgid`."""
        self._tr_widgets.append((widget, msgid, setter))
        getattr(widget, setter)(_(msgid))
        return widget

    def _chk(self, key: str, msgid: str) -> QCheckBox:
        cb = QCheckBox(_(msgid))
        self._checks[key] = cb
        self._tr_widgets.append((cb, msgid, "setText"))
        cb.toggled.connect(self._update_preview)
        # Apply checkbox changes immediately so no "Apply" click is needed.
        cb.toggled.connect(lambda checked, k=key: self._on_check_changed(k, checked))
        return cb

    def _on_check_changed(self, key: str, checked: bool):
        # Ignore while _load_values() is programmatically setting states.
        if getattr(self, "_loading", False):
            return
        self.config[key] = checked
        save_config(self.config)
        self.config_changed.emit(self.config)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self.tabs = QTabWidget()
        # (tab-widget, English tab title) for retranslation.
        self._tabs_meta = [
            (self._tab_general(), "General"),
            (self._tab_options(), "Options"),
            (self._tab_shortkeys(), "Shortkeys"),
            (self._tab_macro(), "Macro"),
            (self._tab_exceptions(), "Exceptions"),
            (self._tab_catkey(), "CatKey"),
            (self._tab_about(), "About"),
        ]
        for widget, title in self._tabs_meta:
            self.tabs.addTab(widget, _(title))
        root.addWidget(self.tabs)

        btns = QHBoxLayout()
        # Language toggle: switches the whole interface between EN and VI.
        # Its label shows the language you can switch TO.
        self.btn_lang = QPushButton()
        self.btn_lang.clicked.connect(self._toggle_language)
        btns.addWidget(self.btn_lang)
        btns.addStretch()
        self.btn_default = self._track(QPushButton(), "Defaults")
        self.btn_default.clicked.connect(self._restore_defaults)
        btns.addWidget(self.btn_default)
        self.btn_apply = self._track(QPushButton(), "Apply")
        self.btn_apply.clicked.connect(self._apply)
        btns.addWidget(self.btn_apply)
        self.btn_hide = self._track(QPushButton(), "Hide")
        self.btn_hide.clicked.connect(self.hide)
        btns.addWidget(self.btn_hide)
        self.btn_close = self._track(QPushButton(), "Close")
        self.btn_close.clicked.connect(self._request_exit)
        btns.addWidget(self.btn_close)
        root.addLayout(btns)

    def _tab_general(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        io_box = self._track(QGroupBox(), "Vietnamese Input", "setTitle")
        form = QFormLayout(io_box)
        self.cmb_method = QComboBox()
        self.cmb_method.addItems(INPUT_METHODS)
        self.cmb_method.currentTextChanged.connect(self._update_preview)
        lbl_m = self._track(QLabel(), "Input method:")
        form.addRow(lbl_m, self.cmb_method)

        self.cmb_charset = QComboBox()
        self.cmb_charset.addItems(CHARSETS)
        lbl_c = self._track(QLabel(), "Character set:")
        form.addRow(lbl_c, self.cmb_charset)
        lay.addWidget(io_box)

        spell_box = self._track(QGroupBox(), "Spelling", "setTitle")
        sb = QVBoxLayout(spell_box)
        lbl_sp = QLabel(_("Spelling checks are not wired yet (alpha)."))
        lbl_sp.setStyleSheet("color:#888; font-style:italic;")
        sb.addWidget(lbl_sp)
        sb.addWidget(self._chk("check_spelling", "Check basic spelling"))
        sb.addWidget(self._chk("auto_restore_wrong_spelling",
                               "Change back to original word on spelling mistake"))
        sb.addWidget(self._chk("allow_fwjz_consonants",
                               "Allow f, w, j, z as Vietnamese consonants in spelling check"))
        sb.addWidget(self._chk("free_marking",
                               "Free marking tone (behind the vowel or end of word)"))
        sb.addWidget(self._chk("auto_upper_after_punct",
                               'Auto Upper Case after "Enter . ! ?"'))
        lay.addWidget(spell_box)
        lay.addStretch()
        return w

    def _tab_options(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        compat = self._track(QGroupBox(), "Compatibility", "setTitle")
        cb = QVBoxLayout(compat)
        lbl_co = QLabel(_("Compatibility options are not wired yet (alpha)."))
        lbl_co.setStyleSheet("color:#888; font-style:italic;")
        cb.addWidget(lbl_co)
        cb.addWidget(self._chk("modern_style", "Modern style"))
        cb.addWidget(self._chk("standard_key_sending", "Use standard key sending"))
        cb.addWidget(self._chk("use_clipboard_send", "Use Clipboard for send key"))
        cb.addWidget(self._chk("support_metro",
                               "Support Metro apps (Mail, Facebook, Messenger)"))
        cb.addWidget(self._chk("fix_browser_excel",
                               "Correct Vietnamese on browser address bar / Excel"))
        lay.addWidget(compat)

        system = self._track(QGroupBox(), "System", "setTitle")
        yb = QVBoxLayout(system)
        yb.addWidget(self._chk("auto_run_boot", "Auto-run CatKey at boot time"))
        yb.addWidget(self._chk("run_as_admin", "Run as Administrator on startup"))
        yb.addWidget(self._chk("show_dialog_startup", "Show this dialog box at startup"))
        yb.addWidget(self._chk("notification_sounds", "Turn on/off notification sounds"))
        yb.addWidget(self._chk("notify_on_toggle",
                               "Notify when Vietnamese typing is turned on or off"))
        yb.addWidget(self._chk("auto_check_update", "Auto check for update at boot time"))
        yb.addWidget(self._chk("customize_tray_icon", "Customize Tray icon"))
        lay.addWidget(system)
        lay.addStretch()
        return w

    def _tab_shortkeys(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.key_switch = QKeySequenceEdit()
        self.key_restore = QKeySequenceEdit()
        self.key_reset = QKeySequenceEdit()
        form.addRow(self._track(QLabel(), "Switch English / Vietnamese:"), self.key_switch)
        form.addRow(self._track(QLabel(), "Restore original word:"), self.key_restore)
        form.addRow(self._track(QLabel(), "Reset keyboard state:"), self.key_reset)
        return w

    def _tab_macro(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl_ma = QLabel(_("Macros are not wired yet (alpha)."))
        lbl_ma.setStyleSheet("color:#888; font-style:italic;")
        lay.addWidget(lbl_ma)
        lay.addWidget(self._chk("macro_enabled", "Enable macros"))
        lay.addWidget(self._chk("macro_even_if_off",
                                "Allow macros even if Vietnamese is off"))
        row = QHBoxLayout()
        row.addWidget(self._track(QLabel(), "Macro file:"))
        self.macro_file = QLineEdit()
        row.addWidget(self.macro_file)
        btn = self._track(QPushButton(), "Select...")
        btn.clicked.connect(self._pick_macro_file)
        row.addWidget(btn)
        lay.addLayout(row)
        lay.addWidget(self._track(QPushButton(), "Macro Table..."))
        lay.addStretch()
        return w

    def _tab_exceptions(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = self._track(
            QLabel(),
            "Use exceptional applications list to prevent Vietnamese typing in those apps.",
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        self.exc_list = QListWidget()
        lay.addWidget(self.exc_list)
        row = QHBoxLayout()
        add = self._track(QPushButton(), "Add...")
        add.clicked.connect(self._add_exception)
        rem = self._track(QPushButton(), "Remove")
        rem.clicked.connect(self._remove_exception)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(self._chk("auto_prevent_vietnamese", "Auto prevent Vietnamese typing"))
        return w

    def _tab_catkey(self) -> QWidget:
        """CatKey-specific extras kept separate from EVKey parity."""
        w = QWidget()
        lay = QVBoxLayout(w)

        backend = QGroupBox("Platform Backend (CatKey)")
        bl = QVBoxLayout(backend)
        note = QLabel("Backends unavailable on your platform are greyed out.")
        note.setStyleSheet("color:#888;")
        bl.addWidget(note)
        self.backend_list = QListWidget()
        self.backend_list.setMaximumHeight(120)
        for m in METHODS:
            avail = get_platform() in m["platforms"]
            it = QListWidgetItem(m["name"] + ("" if avail else "  [unavailable]"))
            it.setData(Qt.UserRole, m["id"])
            if not avail:
                it.setForeground(QColor("#999999"))
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
            self.backend_list.addItem(it)
        bl.addWidget(self.backend_list)
        lay.addWidget(backend)

        prev = QGroupBox("Live Preview (converted by C core)")
        pv = QFormLayout(prev)
        self.preview_input = QLineEdit()
        self.preview_input.setPlaceholderText("Type e.g. dd aa xin ...")
        self.preview_input.textChanged.connect(self._update_preview)
        self.preview_output = QLabel("")
        f = QFont(); f.setPointSize(14)
        self.preview_output.setFont(f)
        self.preview_output.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pv.addRow("Input:", self.preview_input)
        pv.addRow("Output:", self.preview_output)
        if not core_available():
            warn = QLabel("Core library not built - preview disabled.")
            warn.setStyleSheet("color:#c0392b;")
            pv.addRow(warn)
        lay.addWidget(prev)
        lay.addStretch()
        return w

    def _tab_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            "<p>Vietnamese Keyboard - EVKey-compatible interface.</p>"
            f"<p>Platform: <b>{get_platform().title()}</b></p>"
            f"<p>Core: <b>{'loaded' if core_available() else 'not built'}</b> "
            "(C engine via ctypes)</p>"
            "<p>UI: PySide6 &nbsp;|&nbsp; Engine: C</p>"
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setAlignment(Qt.AlignTop)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    # -- Load / save ------------------------------------------------------

    def _load_values(self):
        c = self.config
        self._loading = True
        self.cmb_method.setCurrentText(c.get("input_method", "Telex"))
        self.cmb_charset.setCurrentText(c.get("charset", "Unicode"))
        for key, cb in self._checks.items():
            cb.setChecked(bool(c.get(key, False)))
        self._loading = False
        self.key_switch.setKeySequence(QKeySequence(c.get("shortkey_switch", "")))
        self.key_restore.setKeySequence(QKeySequence(c.get("shortkey_restore", "")))
        self.key_reset.setKeySequence(QKeySequence(c.get("shortkey_reset", "")))
        self.macro_file.setText(c.get("macro_file", ""))
        self.exc_list.clear()
        self.exc_list.addItems(c.get("exception_apps", []))

        ck = c.get("catkey", {})
        for i in range(self.backend_list.count()):
            if self.backend_list.item(i).data(Qt.UserRole) == ck.get("method"):
                self.backend_list.setCurrentRow(i)
                break
        self._update_preview()

    def _collect(self) -> dict:
        c = self.config
        c["input_method"] = self.cmb_method.currentText()
        c["charset"] = self.cmb_charset.currentText()
        for key, cb in self._checks.items():
            c[key] = cb.isChecked()
        c["shortkey_switch"] = self.key_switch.keySequence().toString()
        c["shortkey_restore"] = self.key_restore.keySequence().toString()
        c["shortkey_reset"] = self.key_reset.keySequence().toString()
        c["macro_file"] = self.macro_file.text()
        c["exception_apps"] = [self.exc_list.item(i).text()
                               for i in range(self.exc_list.count())]
        item = self.backend_list.currentItem()
        if item is not None and is_method_available(item.data(Qt.UserRole)):
            c.setdefault("catkey", {})["method"] = item.data(Qt.UserRole)
        return c

    def _apply(self):
        self._collect()
        save_config(self.config)
        self.config_changed.emit(self.config)

    def _restore_defaults(self):
        from .config import DEFAULT_CONFIG
        import json
        # Mutate in place so app + window keep sharing one config dict.
        self.config.clear()
        self.config.update(json.loads(json.dumps(DEFAULT_CONFIG)))
        self._load_values()

    # -- Preview (C core) -------------------------------------------------

    def _engine_mode(self) -> str:
        name = self.cmb_method.currentText()
        if "VIQR" in name:
            return MODE_VIQR
        if "VNI" in name:
            return MODE_VNI
        if "Telex + VNI" in name:
            return MODE_TEIP_VNI
        return MODE_TEIP

    def _update_preview(self, *args):
        if not hasattr(self, "preview_input"):
            return
        text = self.preview_input.text()
        if not text or not core_available():
            self.preview_output.setText("")
            return
        mode = self._engine_mode()
        out = " ".join(convert_word(w, mode) if w else "" for w in text.split(" "))
        self.preview_output.setText(out)

    # -- Language / retranslate ------------------------------------------

    def _toggle_language(self):
        new = LANG_EN if current_language() == LANG_VI else LANG_VI
        set_language(new)
        self.config["ui_language"] = new
        save_config(self.config)
        self._retranslate()
        self.config_changed.emit(self.config)

    def _retranslate(self):
        """Re-apply all UI text in the current language."""
        self.setWindowTitle(_("CatKey - Vietnamese Keyboard"))
        # Language button shows the language you can switch TO.
        self.btn_lang.setText("Tiếng Việt" if current_language() == LANG_EN
                              else "English")
        # Tabs
        for i, (_widget, title) in enumerate(self._tabs_meta):
            self.tabs.setTabText(i, _(title))
        # All tracked widgets
        for widget, msgid, setter in self._tr_widgets:
            getattr(widget, setter)(_(msgid))

    def _pick_macro_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select macro file", "",
                                              "Text files (*.txt);;All files (*)")
        if path:
            self.macro_file.setText(path)

    def _add_exception(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add exception", "Application executable:")
        if ok and name.strip():
            self.exc_list.addItem(name.strip())

    def _remove_exception(self):
        for it in self.exc_list.selectedItems():
            self.exc_list.takeItem(self.exc_list.row(it))

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def _request_exit(self):
        from PySide6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Exit CatKey",
            "Quit CatKey completely? Vietnamese typing will stop.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            self.exit_requested.emit()

    def force_close(self):
        self._allow_close = True
        self.close()


# ---------------------------------------------------------------------------
# System Tray Application (EVKey-style menu)
# ---------------------------------------------------------------------------

class _HotkeyBridge(QObject):
    """Marshals pynput's listener-thread callback onto the Qt GUI thread."""
    triggered = Signal()


class CatKeyApp:
    # Two left-clicks within this window (ms) open the UI; otherwise toggle.
    DBLCLICK_MS = 1000

    def __init__(self):
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName(APP_NAME)
        self.app.setApplicationVersion(APP_VERSION)

        # Single-instance guard: prevents a second process from installing a
        # second keyboard hook (which caused doubled/tripled keystrokes).
        self._single = QSharedMemory("CatKey_SingleInstance_v1")
        if self._single.attach():
            # Already running elsewhere.
            self._is_primary = False
            return
        self._is_primary = self._single.create(1)

        self.config = load_config()
        self.window = MainWindow(self.config)
        self.window.config_changed.connect(self._on_config_changed)
        self.window.exit_requested.connect(self._quit)

        self._build_tray()

        # Start the system-wide typing engine so CatKey works in other apps.
        if hook_available():
            hook_start()
            self._apply_hook_state()

        # Global toggle hotkey via pynput (marshalled to GUI thread by signal).
        self._hk_bridge = _HotkeyBridge()
        self._hk_bridge.triggered.connect(self._toggle_vietnamese)
        self._start_hotkey()

        # Warn about conflicting Vietnamese input tools running in background.
        QTimer.singleShot(800, self._check_conflicts)

    def _start_hotkey(self):
        from .hotkey import HotkeyListener
        combo = self.config.get("shortkey_switch", "Ctrl+Shift")
        if getattr(self, "_hotkey", None):
            self._hotkey.stop()
        self._hotkey = HotkeyListener(combo, self._hk_bridge.triggered.emit)
        self._hotkey.start()

    def _sync_from_engine(self):
        """(Unused) engine no longer self-toggles; kept for compatibility."""
        if not hook_available():
            return
        engine_on = hook_get_enabled()
        if engine_on != bool(self.config.get("vietnamese_on", True)):
            self.config["vietnamese_on"] = engine_on
            save_config(self.config)
            self.tray.setIcon(_cat_icon(engine_on))
            self.tray.setContextMenu(self._build_menu())
            self._update_tooltip()
            self.tray.showMessage(
                APP_NAME,
                _("Vietnamese typing ON") if engine_on else _("Vietnamese typing OFF"),
                QSystemTrayIcon.Information, 1200,
            )

    def _apply_hotkeys(self):
        """Push the toggle + restore shortkeys from config into the C hook."""
        if not hook_available():
            return
        from .core import hook_set_toggle_key, hook_set_restore_key

        vk, mods = _seq_to_vk_mods(self.config.get("shortkey_switch", "Ctrl+Shift"))
        hook_set_toggle_key(vk, mods)
        rvk, rmods = _seq_to_vk_mods(self.config.get("shortkey_restore", ""))
        hook_set_restore_key(rvk, rmods)

    def _apply_hook_state(self):
        """Sync the C hook engine with current config (enabled + method)."""
        if not hook_available():
            return
        self._apply_hotkeys()
        im = self.config.get("input_method", "")
        if "VIQR" in im:
            method = MODE_VIQR
        elif "VNI" in im:
            method = MODE_VNI
        elif "Telex + VNI" in im:
            method = MODE_TEIP_VNI
        else:
            method = MODE_TEIP
        hook_set_method(method)
        hook_set_enabled(bool(self.config.get("vietnamese_on", True)))

    def _toggle_vietnamese(self):
        """Toggle the Vietnamese typing engine on/off (tray + hotkey)."""
        self.config["vietnamese_on"] = not self.config.get("vietnamese_on", True)
        save_config(self.config)
        on = self.config["vietnamese_on"]
        self.tray.setIcon(_cat_icon(on))
        self.tray.setContextMenu(self._build_menu())
        self._update_tooltip()
        self._apply_hook_state()
        if self.config.get("notify_on_toggle", True):
            self.tray.showMessage(
                APP_NAME,
                _("Vietnamese typing ON") if on else _("Vietnamese typing OFF"),
                QSystemTrayIcon.Information, 1500,
            )

    def _build_tray(self):
        on = self.config.get("vietnamese_on", True)
        self.tray = QSystemTrayIcon(_cat_icon(on))
        self._update_tooltip()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setContextMenu(self._build_menu())

    def _build_menu(self) -> QMenu:
        menu = QMenu()

        # Vietnamese ON/OFF toggle (the actual typing engine switch).
        on = self.config.get("vietnamese_on", True)
        act_vn = QAction(_("Vietnamese (On)") if on else _("English (Off)"),
                         self.app, checkable=True)
        act_vn.setChecked(on)
        act_vn.triggered.connect(lambda ch: self._toggle_vietnamese())
        menu.addAction(act_vn)
        menu.addSeparator()

        # Input methods (radio group, EVKey-style)
        m_methods = menu.addMenu(_("Input method"))
        grp = QActionGroup(self.app)
        grp.setExclusive(True)
        for name in INPUT_METHODS:
            a = QAction(name, self.app, checkable=True)
            a.setChecked(name == self.config.get("input_method"))
            a.setActionGroup(grp)
            a.triggered.connect(lambda ch, n=name: self._set_method(n))
            m_methods.addAction(a)

        # Character sets
        m_cs = menu.addMenu(_("Character set"))
        grp2 = QActionGroup(self.app)
        grp2.setExclusive(True)
        for name in CHARSETS:
            a = QAction(name, self.app, checkable=True)
            a.setChecked(name == self.config.get("charset"))
            a.setActionGroup(grp2)
            a.triggered.connect(lambda ch, n=name: self._set_charset(n))
            m_cs.addAction(a)

        menu.addSeparator()
        act_convert = QAction(_("Convert Tool...  (F6)"), self.app)
        act_convert.setEnabled(False)
        menu.addAction(act_convert)
        act_macro = QAction(_("Macro Table...  (F8)"), self.app)
        act_macro.setEnabled(False)
        menu.addAction(act_macro)
        act_macro_toggle = QAction(_("On/Off Macro  (F9)"), self.app)
        act_macro_toggle.setEnabled(False)
        menu.addAction(act_macro_toggle)

        menu.addSeparator()
        act_show = QAction(_("Show CatKey dialog"), self.app)
        act_show.triggered.connect(self._show_window)
        menu.addAction(act_show)

        menu.addSeparator()
        act_quit = QAction(_("Exit"), self.app)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)
        return menu

    def _update_tooltip(self):
        on = self.config.get("vietnamese_on", True)
        state = "Vietnamese" if on else "English"
        self.tray.setToolTip(f"{APP_NAME} - {self.config.get('input_method')} "
                             f"({state})")

    def _set_method(self, name: str):
        self.config["input_method"] = name
        save_config(self.config)
        self.window._load_values()
        self._update_tooltip()
        self._apply_hook_state()

    def _set_charset(self, name: str):
        self.config["charset"] = name
        save_config(self.config)
        self.window._load_values()

    def _on_tray_activated(self, reason):
        # We implement our own click timing so behaviour is:
        #   - a single left click toggles Vietnamese/English
        #   - two left clicks within DBLCLICK_MS opens the UI
        #   - if the 2nd click is slower than the window, the timer resets and
        #     it just counts as a fresh single click (toggle)
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._handle_left_click()

    def _handle_left_click(self):
        import time
        now = time.monotonic()
        last = getattr(self, "_last_click_ts", 0.0)
        self._last_click_ts = now

        # Second click within the window -> open UI (cancel the pending toggle).
        if (now - last) <= self.DBLCLICK_MS / 1000.0:
            if getattr(self, "_click_timer", None):
                self._click_timer.stop()
            self._last_click_ts = 0.0   # reset so a 3rd click starts fresh
            self._show_window()
            return

        # First click: wait to see if a second one arrives; if not, toggle.
        if getattr(self, "_click_timer", None) is None:
            self._click_timer = QTimer()
            self._click_timer.setSingleShot(True)
            self._click_timer.timeout.connect(self._commit_single_click)
        self._click_timer.start(self.DBLCLICK_MS)

    def _commit_single_click(self):
        self._last_click_ts = 0.0
        self._toggle_vietnamese()

    def _on_config_changed(self, cfg: dict):
        # Mutate the shared dict in place so window/app never diverge.
        if cfg is not self.config:
            self.config.clear()
            self.config.update(cfg)
        on = self.config.get("vietnamese_on", True)
        self.tray.setIcon(_cat_icon(on))
        self.tray.setContextMenu(self._build_menu())
        self._update_tooltip()
        self._apply_hook_state()
        # Keep the OS auto-run entry in sync with the checkbox.
        from .config import set_autorun
        set_autorun(bool(self.config.get("auto_run_boot", False)))
        # Rebind the global hotkey in case the shortkey was changed.
        if getattr(self, "_hotkey", None):
            self._hotkey.set_combo(self.config.get("shortkey_switch", "Ctrl+Shift"))

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _check_conflicts(self):
        try:
            from .conflicts import detect_conflicts
            found = detect_conflicts()
        except Exception:
            return
        if not found:
            return
        names = ", ".join(found)
        self.tray.showMessage(
            f"{APP_NAME} - conflict detected",
            f"Another Vietnamese input tool is running: {names}. "
            "Please turn it off to avoid garbled typing.",
            QSystemTrayIcon.Warning, 6000,
        )
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self.window, "Conflicting Vietnamese input tool",
            f"CatKey detected another Vietnamese input tool running:\n\n"
            f"    {names}\n\n"
            "Running two Vietnamese IMEs at once will garble your typing. "
            "Please turn off the other tool, then use CatKey.",
        )

    def _quit(self):
        if getattr(self, "_hotkey", None):
            self._hotkey.stop()
        if hook_available():
            hook_stop()
        self.tray.hide()
        self.window.force_close()
        self.app.quit()

    def run(self) -> int:
        if not getattr(self, "_is_primary", False):
            # Another instance owns the hook; do not start a second one.
            return 0
        self.tray.show()
        if self.config.get("show_dialog_startup", True):
            self._show_window()
        return self.app.exec()
