#!/usr/bin/env bash
# Build CatKey into a standalone executable using PyInstaller or Nuitka.
#
# Usage:
#   ./build.sh                     # PyInstaller, onedir (default)
#   ./build.sh --tool nuitka       # Nuitka, standalone
#   ./build.sh --onefile           # single-file exe
#   ./build.sh --tool nuitka --onefile
#   ./build.sh --clean             # remove build artifacts and exit
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="CatKey"
ENTRY="$ROOT/run_ui.py"
CORE_DIR="$ROOT/catkey_core"
LOCALES="$ROOT/locales"

TOOL="pyinstaller"
ONEFILE=0
CLEAN=0
PYTHON=""

while [ $# -gt 0 ]; do
    case "$1" in
        --tool) TOOL="$2"; shift 2 ;;
        --onefile) ONEFILE=1; shift ;;
        --clean) CLEAN=1; shift ;;
        --python) PYTHON="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$PYTHON" ]; then
    if [ -x "$ROOT/../.venv/bin/python" ]; then PYTHON="$ROOT/../.venv/bin/python"
    else PYTHON="python3"; fi
fi

clean_artifacts() {
    rm -rf "$ROOT/build" "$ROOT/dist" "$ROOT/__pycache__" \
           "$ROOT/$NAME.build" "$ROOT/$NAME.dist" "$ROOT/$NAME.onefile-build" \
           "$ROOT"/*.spec 2>/dev/null || true
}

if [ "$CLEAN" -eq 1 ]; then clean_artifacts; echo "Cleaned."; exit 0; fi

# The native core must exist so it can be bundled.
# Load core.py directly (not via the package) so we don't pull in PySide6 /
# Qt GUI libs just to trigger the C-core build.
if ! ls "$CORE_DIR"/libcatkey_core.* "$CORE_DIR"/catkey_core.dll >/dev/null 2>&1; then
    echo "Native core not found - building it..."
    "$PYTHON" -c "import importlib.util, sys
spec = importlib.util.spec_from_file_location('catkey_core_bind', r'$ROOT/catkey_ui/core.py')
m = importlib.util.module_from_spec(spec)
sys.modules['catkey_core_bind'] = m
spec.loader.exec_module(m)
print('core built:', m.core_available())"
    if ! ls "$CORE_DIR"/libcatkey_core.* "$CORE_DIR"/catkey_core.dll >/dev/null 2>&1; then
        echo "Failed to build the native core. Build it manually first." >&2; exit 1
    fi
fi

clean_artifacts

# Stage only the built native libraries (not C sources) for bundling.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
find "$CORE_DIR" -maxdepth 1 -type f \( -name '*.so' -o -name '*.dylib' -o -name '*.dll' \) \
    -exec cp {} "$STAGE/" \;

if [ "$TOOL" = "pyinstaller" ]; then
    "$PYTHON" -m pip install --quiet --upgrade pyinstaller
    ARGS=(-m PyInstaller --noconfirm --clean --name "$NAME" --windowed
          --add-data "$STAGE:catkey_core"
          --add-data "$LOCALES:locales")
    if [ "$ONEFILE" -eq 1 ]; then ARGS+=(--onefile); else ARGS+=(--onedir); fi
    ARGS+=("$ENTRY")
    "$PYTHON" "${ARGS[@]}"
    if [ "$ONEFILE" -eq 1 ]; then OUT="$ROOT/dist/$NAME"; else OUT="$ROOT/dist/$NAME/$NAME"; fi
elif [ "$TOOL" = "nuitka" ]; then
    "$PYTHON" -m pip install --quiet --upgrade nuitka
    if [ "$ONEFILE" -eq 1 ]; then MODE="--onefile"; else MODE="--standalone"; fi
    # Nuitka's --include-data-dir skips shared libraries, so include each
    # native lib explicitly as a data file (ctypes loads it at runtime).
    NUITKA_LIBS=()
    for f in "$STAGE"/*; do
        [ -e "$f" ] && NUITKA_LIBS+=("--include-data-files=$f=catkey_core/$(basename "$f")")
    done
    "$PYTHON" -m nuitka "$MODE" \
        --enable-plugin=pyside6 \
        --output-filename="$NAME" \
        --include-data-dir="$LOCALES=locales" \
        "${NUITKA_LIBS[@]}" \
        --assume-yes-for-downloads \
        --output-dir="$ROOT/dist" \
        "$ENTRY"
    if [ "$ONEFILE" -eq 1 ]; then OUT="$ROOT/dist/$NAME"; else OUT="$ROOT/dist/run_ui.dist/$NAME"; fi
else
    echo "Unknown tool: $TOOL (use pyinstaller or nuitka)" >&2; exit 1
fi

if [ -f "$OUT" ]; then
    echo "Build OK -> $OUT"
else
    echo "Build finished but expected output not found: $OUT"
    echo "Check the dist/ folder."
fi
