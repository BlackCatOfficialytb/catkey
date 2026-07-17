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
    [string]$Python = ''
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

# The C core DLL must exist so it can be bundled.
$Dll = Join-Path $CoreDir 'catkey_core.dll'
if (-not (Test-Path $Dll)) {
    Write-Host 'catkey_core.dll not found - building it...' -ForegroundColor Yellow
    & $Python -c "import sys; sys.path.insert(0, r'$Root'); from catkey_ui import core; print('core built:', core.core_available())"
    if (-not (Test-Path $Dll)) { throw "Failed to build catkey_core.dll. Build it manually first." }
}

Remove-Artifacts

# Stage only the built native libraries (not C sources) for bundling.
$Stage = Join-Path $env:TEMP "catkey_core_stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Path $Stage | Out-Null
Get-ChildItem $CoreDir -File | Where-Object { $_.Extension -in '.dll', '.so', '.dylib' } |
    Copy-Item -Destination $Stage

if ($Tool -eq 'pyinstaller') {
    & $Python -m pip install --quiet --upgrade pyinstaller
    $args = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--name', $Name, '--windowed',
        '--add-data', "$Stage;catkey_core",
        '--add-data', "$Locales;locales"
    )
    $args += $OneFile ? '--onefile' : '--onedir'
    $args += $Entry
    & $Python @args
    $out = $OneFile ? (Join-Path $Root "dist\$Name.exe") : (Join-Path $Root "dist\$Name\$Name.exe")
}
else {
    & $Python -m pip install --quiet --upgrade nuitka
    $mode = $OneFile ? '--onefile' : '--standalone'
    $args = @(
        '-m', 'nuitka', $mode,
        '--enable-plugin=pyside6',
        '--windows-console-mode=disable',
        "--output-filename=$Name.exe",
        "--include-data-dir=$Stage=catkey_core",
        "--include-data-dir=$Locales=locales",
        '--assume-yes-for-downloads',
        "--output-dir=$(Join-Path $Root 'dist')",
        $Entry
    )
    & $Python @args
    $out = $OneFile ? (Join-Path $Root "dist\$Name.exe") : (Join-Path $Root "dist\run_ui.dist\$Name.exe")
}

if (Test-Path $out) {
    Write-Host "Build OK -> $out" -ForegroundColor Green
} else {
    Write-Host "Build finished but expected output not found: $out" -ForegroundColor Yellow
    Write-Host 'Check the dist/ folder.' -ForegroundColor Yellow
}
