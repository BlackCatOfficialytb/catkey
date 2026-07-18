# CatKey v0.0.1.0a (Alpha) — Build 20260718 / commit 5dc54f7

> **⚠️ ALPHA — WORK IN PROGRESS.** This is an early, unstable preview. Features are incomplete, behavior may change, and there are known bugs. Do **not** use this version for real typing work yet. For a stable Vietnamese input method, please continue using UniKey/EVKey for now.

**Tag:** `v0.0.1.0a_build20260718_5dc54f7`
**Commit:** `5dc54f7` (2026-07-18)
**License:** GPL-3.0-or-later (with §7 additional terms — see `LICENSE`)

---

## What is CatKey?

CatKey is a free, open-source Vietnamese input method (bộ gõ tiếng Việt) with an EVKey-style interface. The UI/UX is Python + PySide6; the conversion engine and system-wide keyboard hook are C. It is derived (via reverse-engineering of EVKey) from UniKey, which is GPL — therefore CatKey is necessarily GPL too.

This first alpha is a **proof of concept**: Telex/VNI conversion and basic system-wide injection work, but many EVKey-parity features are stubbed or unfinished.

---

## What works in this build

- **Conversion engine (C core, `vietnamese_tep.c`)**
  - Telex word-level conversion with correct tone placement on the main vowel.
  - VNI (digits 1–9 for tones/marks, 9 for `đ`).
  - Full **uppercase support**: `Ê`, `Ô`, `Ơ`, `Ă`, `Â`, `Đ`, `À`, `Á`, `Ế`, `Ố`, `Ữ`, ... (Shift *and* CapsLock).
  - Precomposed UTF-8 output.
  - Verified: `tieengs`→`tiếng`, `vieejt`→`việt`, `ddaay`→`đây`, `chaof`→`chào`, `Ee`→`Ê`, `Ow`→`Ơ`, `DDaay`→`Đây`, `TIEENGS`→`TIẾNG`.
- **System-wide typing (Windows, `catkey_hook.c`)**
  - `WH_KEYBOARD_LL` hook, buffers the word, rewrites via Backspace + Unicode `SendInput`.
  - Works in Notepad, browsers, chat apps, etc.
  - Single-instance guard prevents doubled keystrokes from a second install.
- **UI (PySide6, EVKey-clone)**
  - 7 tabs: General / Options / Shortkeys / Macro / Exceptions / CatKey / About.
  - 7 input methods, 11 charsets (UI parity; conversion engine implements Telex + VNI).
  - EVKey-style system tray menu.
  - In-app **English ↔ Tiếng Việt** language switch (gettext, retranslates the whole UI).
  - **CatKey tab**: live preview of conversion (calls the C core directly).
- **Tray + hotkey behavior**
  - Left-click tray = toggle Vietnamese/English.
  - Double-click tray (within 1 s) = open settings.
  - Global VN/EN toggle hotkey via **pynput** (default `Ctrl+Shift`), marshalled to the GUI thread.
  - "Notify when Vietnamese typing is turned on or off" checkbox applies immediately (no Apply needed).
- **Conflict detection** for other running Vietnamese IMEs (UniKey/EVKey/OpenKey/GoTiengViet/...).
- **Packaging**
  - `build.ps1` (Windows) and `build.sh` (Linux): `-Tool pyinstaller|nuitka`, `-OneFile`, `-Clean`.
  - Windows: `-Arch {x64|x86|arm64}` × `-Compiler {msvc|mingw}`.
  - Linux: `--arch {x86|x64}` × `--compiler {gcc|clang}`.
  - Frozen builds bundle `catkey_core.*` + `locales/` and resolve paths correctly under `_MEIPASS`/`sys.frozen`.
  - Post-build export check verifies the bundled lib actually exports `catkey_convert_word` (fails fast on a bad MinGW build instead of at runtime).
  - Both PyInstaller and Nuitka produce a running exe locally (x64/MSVC verified).
- **CI (GitHub Actions, `.github/workflows/build.yml`)**
  - Matrix: Windows x64/x86/arm64 × msvc/mingw; Linux x64/x86 × gcc/clang.
  - `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to silence Node 20 deprecation warnings.
  - Linux x86 marked best-effort (default GitHub Linux runner is x86_64 only; needs an i386-capable runner).
- **Docs / licensing**
  - `README.md` (English) + `docs/README_vi.md` (Vietnamese).
  - Includes the UniKey `unikey.vn` vs official `unikey.org` safety note and "verify before you trust a build" guidance.
  - License: **GPL-3.0-or-later** + §7 additional terms (modified versions must be renamed/rebranded; no use of "CatKey"/"BlackCatOfficial" marks without permission).

---

## Known issues & limitations (alpha)

- **Conversion parity:** only Telex and VNI actually convert. Simple Telex / Simple Telex 2 / Telex+VNI / VIQR / Microsoft VI Layout are listed in the UI but not implemented in the engine.
- **Engine edge cases:** some diphthongs/triphthongs and rare spelling cases are not fully handled; spelling-check options in the UI have no effect yet.
- **Macro, Restore-word, Reset-state shortkeys:** UI present, not wired up (tray menu items disabled).
- **"Convert Tool..." / "Macro Table..." / "On/Off Macro"** tray actions are disabled.
- **Linux:** the system-wide hook is conversion-only in this build (the X11 daemon is a separate program and is **not** bundled/loaded by the app). On Linux CatKey currently does *not* inject into other apps.
- **Linux x86 / Windows arm64 builds:** not exercisable on standard GitHub runners; best-effort / likely to fail without a matching-capable runner.
- **Code-signing / reproducible-build automation:** not implemented. The README documents the community guideline; builds are **not** signed.
- No auto-update, no installer, no `--onefile` runtime test in CI.
- `APP_VERSION` in `config.py` still says `"1.0.0"`; treat the real version as the tag only.

---

## Safety / trust

An input method sees every keystroke. **Only run CatKey builds you can verify from source.** Download from the official repository, check the commit, and (if available) reproduce the build. See `README.md` → "Why verify before you trust a build."

## License

GPL-3.0-or-later. Derivative of UniKey (GPL) via EVKey. Modified versions must be renamed/rebranded and may not use the "CatKey" or "BlackCatOfficial" marks without written permission (GPLv3 §7 additional terms). See `LICENSE`.

---

*This is an alpha; expect breakage. Feedback and bug reports welcome via the issue tracker.*
