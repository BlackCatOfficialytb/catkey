<#
.SYNOPSIS
    Build CatKey into a standalone executable using PyInstaller or Nuitka.

.DESCRIPTION
    Builds the native C core (catkey_core.dll) for the requested arch/compiler,
    stages it, then packages the PySide6 app via PyInstaller (onedir/onefile)
    or Nuitka (standalone/onefile). Output is placed under dist/ and suffixed
    by arch and compiler so matrix builds don't collide.

.EXAMPLE
    .\build.ps1                       # PyInstaller onedir, x64, MSVC
    .\build.ps1 -Tool nuitka          # Nuitka standalone
    .\build.ps1 -t nuitka             # same, short form (-t == -Tool)
    .\build.ps1 -OneFile              # single-file exe (PyInstaller)
    .\build.ps1 -Tool nuitka -OneFile # Nuitka onefile
    .\build.ps1 -Arch x86 -Compiler mingw   # 32-bit Windows build via MSYS2
    .\build.ps1 -a x86 -c mingw            # same, short form (-a/-c)
    .\build.ps1 -Arch arm64 -Compiler msvc  # ARM64 Windows via MSVC
    .\build.ps1 -Clean                # remove build artifacts and exit
    .\build.ps1 -Help                  # show this help and exit

.NOTES
    Requires: Python 3.11+ and a C compiler (MSVC vcvars64/32/arm64, or MSYS2
    mingw64/mingw32/clangarm64). See requirements.txt.
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [Alias('t')]
    [ValidateSet('pyinstaller', 'nuitka')]
    [string]$Tool = 'pyinstaller',
    [switch]$OneFile,
    [switch]$Clean,
    [Alias('p')]
    [string]$Python = '',
    [Alias('a')]
    [ValidateSet('x64', 'x86', 'arm64')]
    [string]$Arch = 'x64',
    [Alias('c')]
    [ValidateSet('msvc', 'mingw')]
    [string]$Compiler = 'msvc'
)

if ($Help) {
    Get-Help $PSCommandPath -Detailed | Out-String | Write-Host
    exit 0
}

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
    # Also remove suffixed output dirs from previous arch/compiler builds.
    Get-ChildItem $Root -Directory -Filter "$Name-*" -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
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
        # MinGW (MSYS2): the setup-msys2 action has already put the matching
        # toolchain (gcc/clang) on PATH and set MSYSTEM. Call the compiler
        # directly - no msys2_shell.cmd indirection (which is async + fragile).
        $cc = if ($Arch -eq 'arm64') { 'clang' } else { 'gcc' }
        if (-not (Get-Command $cc -ErrorAction SilentlyContinue)) {
            throw "$cc not found on PATH (install MSYS2 + the matching toolchain first)."
        }
        # MinGW needs the .def as a plain input file to export symbols
        # (functions in vietnamese_tep.c are not __declspec(dllexport)).
        # Run from the core dir so the relative .def / source paths resolve.
        Push-Location $CoreDir
        try {
            $relSrcs = ($srcs | ForEach-Object {
                $rel = [System.IO.Path]::GetRelativePath($CoreDir, $_) -replace '\\','/'
                '"{0}"' -f $rel
            }) -join ' '
            $cmd = "$cc -shared -O2 -o `"$Dll`" $relSrcs catkey_core.def -Wl,--kill-at -luser32"
            & cmd /c $cmd 2>&1 | Write-Host
            if ($LASTEXITCODE -ne 0) { throw "MinGW ($Arch) build failed (exit $LASTEXITCODE)." }
        } finally {
            Pop-Location
        }
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
    $outDir = Join-Path $Root "dist\$Name-$Suffix"
    # Onefile linker can fail with LNK1104 when the output-dir was just
    # written to by the internal standalone step.  Use a temp dir for the
    # build, then move the final exe to the expected dist/ location.
    if ($OneFile) {
        $tempDir = Join-Path $env:TEMP "catkey_nk_onefile_$(Get-Random)"
        if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
        New-Item -ItemType Directory -Path $tempDir | Out-Null
        # Try to exclude the temp dir from Windows Defender / BitDefender so
        # Nuitka's post-processing (PE resource embedding) isn't blocked.
        try { Add-MpExclusion -ExclusionPath $tempDir -ErrorAction Stop } catch {}
        $buildDir = $tempDir
    } else {
        $buildDir = $outDir
    }
    $args = @(
        '-m', 'nuitka', $mode,
        '--enable-plugin=pyside6',
        '--windows-console-mode=disable',
        "--output-filename=$Name.exe",
        "--include-data-dir=$Locales=locales",
        '--assume-yes-for-downloads',
        "--output-dir=$buildDir"
    ) + $narch
    # Nuitka's --include-data-dir skips *.dll; force each native lib in as a
    # data file so ctypes can load it at runtime (no compiler on user's box).
    foreach ($lib in $libs) {
        $args += "--include-data-files=$($lib.FullName)=catkey_core/$($lib.Name)"
    }
    $args += $Entry
    & $Python @args
    if ($OneFile) {
        $built = Join-Path $tempDir "$Name.exe"
        $final = Join-Path $outDir "$Name-$Suffix.exe"
        if (Test-Path $built) {
            if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
            # Defender may still hold the file briefly after Nuitka finishes.
            for ($i = 0; $i -lt 5; $i++) {
                try { Move-Item -Force $built $final -ErrorAction Stop; break }
                catch { Start-Sleep -Seconds 2 }
            }
        }
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        $out = $final
    } else {
        $out = Join-Path $outDir "run_ui.dist\$Name.exe"
    }
}

if (Test-Path $out) {
    Write-Host "Build OK -> $out" -ForegroundColor Green
} else {
    Write-Host "Build finished but expected output not found: $out" -ForegroundColor Yellow
    Write-Host 'Check the dist/ folder.' -ForegroundColor Yellow
}
