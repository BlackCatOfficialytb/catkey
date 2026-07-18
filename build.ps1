<#
.SYNOPSIS
    Build CatKey into a standalone executable using PyInstaller or Nuitka.

.EXAMPLE
    .\build.ps1                       # PyInstaller, onedir (default)
    .\build.ps1 -Tool nuitka          # Nuitka, standalone
    .\build.ps1 -OneFile              # single-file exe
    .\build.ps1 -Tool nuitka -OneFile # Nuitka onefile
    .\build.ps1 -Clean                # remove build artifacts and exit
#>
[CmdletBinding()]
param(
    [ValidateSet('pyinstaller', 'nuitka')]
    [string]$Tool = 'pyinstaller',
    [switch]$OneFile,
    [switch]$Clean,
    [string]$Python = '',
    [ValidateSet('x64', 'x86', 'arm64')]
    [string]$Arch = 'x64',
    [ValidateSet('msvc', 'mingw')]
    [string]$Compiler = 'msvc'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Name = 'CatKey'
$Entry = Join-Path $Root 'run_ui.py'
$CoreDir = Join-Path $Root 'catkey_core'
$Locales = Join-Path $Root 'locales'

# Prefer the project venv's python if not overridden.
if (-not $Python) {
    $venvPy = Join-Path $Root '..\.venv\Scripts\python.exe'
    $Python = (Test-Path $venvPy) ? (Resolve-Path $venvPy).Path : 'python'
}

function Remove-Artifacts {
    foreach ($d in @('build', 'dist', '__pycache__', "$Name.build", "$Name.dist", "$Name.onefile-build")) {
        $p = Join-Path $Root $d
        if (Test-Path $p) { Remove-Item -Recurse -Force $p }
    }
    Get-ChildItem $Root -Filter '*.spec' | Remove-Item -Force -ErrorAction SilentlyContinue
}

if ($Clean) { Remove-Artifacts; Write-Host 'Cleaned.' -ForegroundColor Green; exit 0 }

# --- Build the native core for the requested arch/compiler ---------------
$Dll = Join-Path $CoreDir 'catkey_core.dll'
$srcs = @((Join-Path $CoreDir 'vietnamese_tep.c'), (Join-Path $CoreDir 'windows' 'catkey_hook.c'))
if (-not (Test-Path $Dll)) {
    Write-Host "Building catkey_core.dll ($Arch/$Compiler)..." -ForegroundColor Yellow
    if ($Compiler -eq 'msvc') {
        $vc = switch ($Arch) {
            'x86'    { 'vcvars32.bat' }
            'arm64'  { 'vcvarsarm64.bat' }
            default  { 'vcvars64.bat' }
        }
        $vcvars = Get-ChildItem "C:\Program Files\Microsoft Visual Studio",
            "C:\Program Files (x86)\Microsoft Visual Studio", "E:\Visual Studio" `
            -Filter $vc -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
        if (-not $vcvars) { throw "MSVC $vc not found." }
        $deff = Join-Path $CoreDir 'catkey_core.def'
        $cmd = ('"{0}" && cl /nologo /w /std:c17 /utf-8 /LD /Fe:"{1}" {2} /link /DEF:"{3}" user32.lib' `
                -f $vcvars, $Dll, (($srcs | ForEach-Object { "`"$_`"" }) -join ' '), $deff)
        cmd /c $cmd | Out-Null
        if (-not (Test-Path $Dll)) { throw "MSVC build failed." }
    } else {
        # MinGW (MSYS2): select the toolchain matching the target arch.
        $envs = @{
            x64    = 'mingw64'
            x86    = 'mingw32'
            arm64  = 'clangarm64'
        }
        $msys = "C:\msys64\msys2_shell.cmd"
        if (-not (Test-Path $msys)) { throw "MSYS2 not found at $msys." }
        $tool = if ($Arch -eq 'arm64') { 'clang' } else { 'gcc' }
        # MinGW needs the .def as a plain input file to export symbols
        # (functions in vietnamese_tep.c are not __declspec(dllexport)).
        # cd into the core dir so the relative .def path resolves.
        $relSrcs = ($srcs | ForEach-Object { '"{0}"' -f (Split-Path $_ -Leaf) }) -join ' '
        $cmd = ('C:\msys64\msys2_shell.cmd -{0} -defterm -no-start -here -c ' +
                '"cd \"{1}\" && {2} -shared -O2 -o \"{3}\" {4} catkey_core.def -Wl,--kill-at -luser32"' `
                -f $envs[$Arch], $CoreDir, $tool, $Dll, $relSrcs)
        cmd /c $cmd | Out-Null
        if (-not (Test-Path $Dll)) { throw "MinGW ($Arch) build failed." }
    }
    Write-Host "core built: $Dll" -ForegroundColor Green
    # Verify the required symbol is actually exported (MinGW omits it
    # without the .def; would fail only at runtime in the bundled exe).
    & $Python -c @"
import ctypes, sys
try:
    lib = ctypes.CDLL(r'$Dll')
    _ = lib.catkey_convert_word
    print('export OK: catkey_convert_word')
except Exception as e:
    print('EXPORT CHECK FAILED:', e, file=sys.stderr); sys.exit(1)
"@
    if ($LASTEXITCODE -ne 0) { throw "Native core missing required exports." }
}

# Suffix to keep matrix outputs (arch/compiler) from colliding.
$Suffix = "$Arch-$Compiler"

Remove-Artifacts

# Stage only the built native libraries (not C sources) for bundling.
$Stage = Join-Path $env:TEMP "catkey_core_stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Path $Stage | Out-Null
$libs = Get-ChildItem $CoreDir -File | Where-Object { $_.Extension -in '.dll', '.so', '.dylib' }
if (-not $libs) { throw "No native libraries (*.dll/*.so/*.dylib) found in $CoreDir to bundle." }
$libs | Copy-Item -Destination $Stage
Write-Host "Staged native libs: $(($libs | ForEach-Object Name) -join ', ')" -ForegroundColor Cyan

if ($Tool -eq 'pyinstaller') {
    & $Python -m pip install --quiet --upgrade pyinstaller
    $args = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--name', "$Name-$Suffix", '--windowed',
        '--add-data', "$Stage;catkey_core",
        '--add-data', "$Locales;locales"
    )
    $args += $OneFile ? '--onefile' : '--onedir'
    $args += $Entry
    & $Python @args
    $out = $OneFile ? (Join-Path $Root "dist\$Name-$Suffix.exe") : (Join-Path $Root "dist\$Name-$Suffix\$Name-$Suffix.exe")
}
else {
    & $Python -m pip install --quiet --upgrade nuitka
    $mode = $OneFile ? '--onefile' : '--standalone'
    # Cross-arch: tell Nuitka the target. Native (x64 on x64) needs nothing.
    $narch = if ($Arch -eq 'x64') { @() } else { "--target-arch=$Arch" }
    $args = @(
        '-m', 'nuitka', $mode,
        '--enable-plugin=pyside6',
        '--windows-console-mode=disable',
        "--output-filename=$Name.exe",
        "--include-data-dir=$Locales=locales",
        '--assume-yes-for-downloads',
        "--output-dir=$(Join-Path $Root 'dist' $Suffix)"
    ) + $narch
    # Nuitka's --include-data-dir skips *.dll; force each native lib in as a
    # data file so ctypes can load it at runtime (no compiler on user's box).
    foreach ($lib in $libs) {
        $args += "--include-data-files=$($lib.FullName)=catkey_core/$($lib.Name)"
    }
    $args += $Entry
    & $Python @args
    $out = $OneFile ? (Join-Path $Root "dist\$Suffix\$Name.exe") : (Join-Path $Root "dist\$Suffix\run_ui.dist\$Name.exe")
}

if (Test-Path $out) {
    Write-Host "Build OK -> $out" -ForegroundColor Green
} else {
    Write-Host "Build finished but expected output not found: $out" -ForegroundColor Yellow
    Write-Host 'Check the dist/ folder.' -ForegroundColor Yellow
}
