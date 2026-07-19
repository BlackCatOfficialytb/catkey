#!/usr/bin/env bash
# Build CatKey into a standalone executable using PyInstaller or Nuitka.
#
# Usage:
#   ./build.sh                     # PyInstaller, onedir (default)
#   ./build.sh --tool nuitka       # Nuitka, standalone
#   ./build.sh -t nuitka           # same, short form (-t == --tool)
#   ./build.sh --onefile           # single-file exe
#   ./build.sh --tool nuitka --onefile
#   ./build.sh --arch x86 --compiler clang   # x86 Linux build via clang
#   ./build.sh -a x86 -c clang             # same, short form (-a/-c)
#   ./build.sh --arch x64 --compiler gcc     # x64 Linux build via gcc
#   ./build.sh --clean             # remove build artifacts and exit
#   ./build.sh --help              # show this help and exit
#
# Requires: Python 3.11+ and a C compiler (gcc or clang). See requirements.txt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="CatKey"
ENTRY="$ROOT/run_ui.py"
CORE_DIR="$ROOT/catkey_core"
LOCALES="$ROOT/locales"

show_help() {
    cat <<EOF
Usage: $0 [options]

Build CatKey into a standalone executable using PyInstaller or Nuitka.

Options:
  -t, --tool pyinstaller|nuitka  Packaging backend (default: pyinstaller)
  --onefile                   Build a single self-extracting executable
                              (PyInstaller onefile / Nuitka onefile)
  -a, --arch x86|x64           Target architecture (default: x64)
  -c, --compiler gcc|clang    Native-core compiler (default: gcc)
  -p, --python PATH           Python interpreter to use
                              (default: ../.venv/bin/python or python3)
  --global-install            Install build deps into the system Python
                              instead of an isolated .venv (less secure).
                              Default: create/use ./.venv (needs python3-venv)
  --clean                     Remove build artifacts (build/, dist/, *.spec)
                              and exit
  -h, --help                  Show this help and exit

Output:
  dist/CatKey-<arch>-<compiler>/   PyInstaller onedir
  dist/CatKey-<arch>-<compiler>.exe (Windows onefile)
  dist/<arch>-<compiler>/run_ui.dist/  Nuitka standalone

Requirements:
  Python 3.11+; gcc or clang; PySide6-Essentials, pynput, pyinstaller
  (and Nuitka for the Nuitka backend). See requirements.txt.
EOF
}

TOOL="pyinstaller"
ONEFILE=0
CLEAN=0
PYTHON=""
ARCH="x64"
COMPILER="gcc"
GLOBAL_INSTALL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) show_help; exit 0 ;;
        -t|--tool) TOOL="$2"; shift 2 ;;
        --onefile) ONEFILE=1; shift ;;
        --clean) CLEAN=1; shift ;;
        -p|--python) PYTHON="$2"; shift 2 ;;
        -a|--arch) ARCH="$2"; shift 2 ;;
        -c|--compiler) COMPILER="$2"; shift 2 ;;
        --global-install) GLOBAL_INSTALL=1; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Resolve the base Python interpreter (used to create the venv / install globally).
if [ -z "$PYTHON" ]; then
    if [ -x "$ROOT/../.venv/bin/python" ]; then PYTHON="$ROOT/../.venv/bin/python"
    else PYTHON="python3"; fi
fi

# Security: by default build inside an isolated virtualenv so build-time pip
# installs never touch the system Python. Pass --global-install to opt out.
if [ "$GLOBAL_INSTALL" -eq 0 ]; then
    BASE_PYTHON="$PYTHON"
    # If we were already pointed at a venv python, keep using it as-is.
    if [ -x "$ROOT/.venv/bin/python" ]; then
        PYTHON="$ROOT/.venv/bin/python"
    elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
        PYTHON="$VIRTUAL_ENV/bin/python"
    else
        # Verify python3-venv (the venv module) is available before relying on it.
        if ! "$BASE_PYTHON" -c "import venv, ensurepip" 2>/dev/null; then
            echo "Error: the Python 'venv' module (python3-venv) is not installed." >&2
            echo "Install it (e.g. 'sudo pacman -S python' / 'sudo apt install python3-venv')" >&2
            echo "or re-run with --global-install to build against the system Python." >&2
            exit 1
        fi
        echo "Creating build virtualenv at $ROOT/.venv ..."
        "$BASE_PYTHON" -m venv "$ROOT/.venv" || {
            echo "Error: failed to create the build virtualenv." >&2; exit 1; }
        PYTHON="$ROOT/.venv/bin/python"
        "$PYTHON" -m pip install --quiet --upgrade pip || true
        # Runtime deps must be importable so the packager can bundle them.
        if [ -f "$ROOT/requirements.txt" ]; then
            "$PYTHON" -m pip install --quiet -r "$ROOT/requirements.txt" || true
        else
            "$PYTHON" -m pip install --quiet PySide6-Essentials pynput || true
        fi
    fi
else
    echo "Warning: --global-install set; installing build deps into the system Python." >&2
fi

# pip_install <pkg...>: install into the active interpreter. Inside a venv this
# is isolated; for --global-install we allow --break-system-packages as a
# fallback for PEP 668 (externally-managed) environments.
pip_install() {
    if [ "$GLOBAL_INSTALL" -eq 1 ]; then
        "$PYTHON" -m pip install --quiet --upgrade --break-system-packages "$@" 2>/dev/null \
            || "$PYTHON" -m pip install --quiet --upgrade "$@" || true
    else
        "$PYTHON" -m pip install --quiet --upgrade "$@" || true
    fi
}

clean_artifacts() {
    rm -rf "$ROOT/build" "$ROOT/dist" "$ROOT/__pycache__" \
           "$ROOT/$NAME.build" "$ROOT/$NAME.dist" "$ROOT/$NAME.onefile-build" \
           "$ROOT/$NAME-"* \
           "$ROOT"/*.spec 2>/dev/null || true
}

if [ "$CLEAN" -eq 1 ]; then clean_artifacts; echo "Cleaned."; exit 0; fi

# The native core must exist so it can be bundled. Build it directly with
# the system compiler (no Python/PySide6 import needed).
if [ "$(uname)" = "Darwin" ]; then
    CORE_LIB="$CORE_DIR/libcatkey_core.dylib"
elif [ "$(uname)" = "Linux" ]; then
    CORE_LIB="$CORE_DIR/libcatkey_core.so"
else
    CORE_LIB="$CORE_DIR/catkey_core.dll"
fi

if [ ! -f "$CORE_LIB" ]; then
    echo "Native core not found - building it..."
    # Linux x86 needs -m32; x64 is native. Compiler chosen by --compiler.
    MFLAG=""
    if [ "$ARCH" = "x86" ]; then MFLAG="-m32"; fi
    if [ "$(uname)" = "Linux" ]; then
        # Match catkey_ui/core.py: the Linux .so is the conversion engine only
        # (the X11 daemon is a separate program, not loaded by the app).
        CC="$COMPILER"
        "$CC" -shared -fPIC -O2 $MFLAG -o "$CORE_LIB" \
            "$CORE_DIR/vietnamese_tep.c" 2>&1 || {
            echo "Failed to build the native core (need $CC)." >&2; exit 1; }
    elif [ "$(uname)" = "Darwin" ]; then
        cc -shared -fPIC -O2 -o "$CORE_LIB" \
            "$CORE_DIR/vietnamese_tep.c" 2>&1 || {
            echo "Failed to build the native core (need clang)." >&2; exit 1; }
    fi
    if [ ! -f "$CORE_LIB" ]; then
        echo "Failed to build the native core. Build it manually first." >&2; exit 1
    fi
    echo "core built: $CORE_LIB"
fi

SUFFIX="$ARCH-$COMPILER"

clean_artifacts

# Stage only the built native libraries (not C sources) for bundling.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
find "$CORE_DIR" -maxdepth 1 -type f \( -name '*.so' -o -name '*.dylib' -o -name '*.dll' \) \
    -exec cp {} "$STAGE/" \;

if [ "$TOOL" = "pyinstaller" ]; then
    if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
        pip_install pyinstaller
    fi
    ARGS=(-m PyInstaller --noconfirm --clean --name "$NAME-$SUFFIX" --windowed
          --add-data "$STAGE:catkey_core"
          --add-data "$LOCALES:locales")
    if [ "$ONEFILE" -eq 1 ]; then ARGS+=(--onefile); else ARGS+=(--onedir); fi
    ARGS+=("$ENTRY")
    "$PYTHON" "${ARGS[@]}"
    if [ "$ONEFILE" -eq 1 ]; then OUT="$ROOT/dist/$NAME-$SUFFIX"; else OUT="$ROOT/dist/$NAME-$SUFFIX/$NAME-$SUFFIX"; fi
elif [ "$TOOL" = "nuitka" ]; then
    if ! "$PYTHON" -c "import nuitka" 2>/dev/null; then
        pip_install nuitka
    fi
    if [ "$ONEFILE" -eq 1 ]; then MODE="--onefile"; else MODE="--standalone"; fi
    NARCH=""
    [ "$ARCH" != "x64" ] && NARCH="--target-arch=$ARCH"
    # Nuitka's --include-data-dir skips shared libraries, so include each
    # native lib explicitly as a data file (ctypes loads it at runtime).
    NUITKA_LIBS=()
    for f in "$STAGE"/*; do
        [ -e "$f" ] && NUITKA_LIBS+=("--include-data-files=$f=catkey_core/$(basename "$f")")
    done
    "$PYTHON" -m nuitka "$MODE" $NARCH \
        --enable-plugin=pyside6 \
        --static-libpython=no \
        --output-filename="$NAME" \
        --include-data-dir="$LOCALES=locales" \
        "${NUITKA_LIBS[@]}" \
        --assume-yes-for-downloads \
        --output-dir="$ROOT/dist/$NAME-$SUFFIX" \
        "$ENTRY"
    if [ "$ONEFILE" -eq 1 ]; then OUT="$ROOT/dist/$NAME-$SUFFIX/$NAME"; else OUT="$ROOT/dist/$NAME-$SUFFIX/run_ui.dist/$NAME"; fi
else
    echo "Unknown tool: $TOOL (use pyinstaller or nuitka)" >&2; exit 1
fi

if [ -f "$OUT" ]; then
    echo "Build OK -> $OUT"
else
    echo "Build finished but expected output not found: $OUT"
    echo "Check the dist/ folder."
fi
