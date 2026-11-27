# Borderlands 2 (Switch) on Android — prepare the phone folder from your own dump.
#
# This is the step that has no one-click equivalent yet: it turns an extracted game dump
# into the three things the app needs besides the APK.
#
# Prerequisites (see README-BL2.md):
#   * <Exefs>       the extracted game program: main, sdk, main.npdm (NSO modules)
#   * <Decoded>     the Oodle-decoded UE3 packages (README-BL2.md section 5, step 1)
#   * <GlobalCache> GlobalShaderCache-Switch.bin from the dump
#   * Python 3.10+  with capstone and lz4   (DM_PYTHON, deps\venv or tools\.runtime\venv)
#   * .NET 10 SDK   only for the shader translator (dotnet build, see README-BL2.md section 5)
#   * SPIRV-Tools   spirv-opt / spirv-val (ANDROID_NDK_HOME shader-tools, or SPIRV_OPT / SPIRV_VAL)
#
# What it does:
#   1. patch_nso.py (DM_TARGET=android) -> main.patched.bin / sdk.patched.bin + tables
#   2. bl2_shader_jobs.py               -> shader jobs from the RomFS
#   3. dmsh_vk_xc2.py                   -> <key>.xgs bundles
#   4. assembles <OutDir>\dm\{out,shaders}   (the folder you copy next to romfs/ on the phone)
#
# Usage:
#   powershell -File tools\setup_bl2.ps1
#   powershell -File tools\setup_bl2.ps1 -Exefs D:\dump\exefs -Decoded D:\dump\decoded `
#       -GlobalCache D:\dump\GlobalShaderCache-Switch.bin -OutDir D:\phone
#   powershell -File tools\setup_bl2.ps1 -SkipShaders -Push -Serial <adb-serial>

[CmdletBinding()]
param(
    [string]$Exefs = '',
    [string]$Decoded = '',
    [string]$GlobalCache = '',
    [string]$OutDir = '',
    [int]$Jobs = 8,
    [switch]$SkipShaders,
    [switch]$Push,
    [string]$Serial = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

if (-not $Exefs)  { $Exefs  = Join-Path $Root 'work\bl2\exefs' }
if (-not $OutDir) { $OutDir = Join-Path $Root 'work\bl2\phone' }

function Find-Python {
    if ($env:DM_PYTHON -and (Test-Path $env:DM_PYTHON)) { return $env:DM_PYTHON }
    foreach ($p in @(
        (Join-Path $Root 'deps\venv\Scripts\python.exe'),
        (Join-Path $Root 'tools\.runtime\venv\Scripts\python.exe')
    )) { if (Test-Path $p) { return $p } }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'Python 3 not found. Set DM_PYTHON=<python.exe> or install Python 3.10+.'
}

function Find-Xlate {
    $candidates = @(
        (Join-Path $Root 'dm\gfx\tools\dmsh_xlate\bin\Release\net10.0\dmsh_xlate.exe'),
        (Join-Path $Root 'dm\gfx\tools\dmsh_xlate\bin\Release\net10.0\dmsh_xlate')
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    throw ('Shader translator not built. Run: dotnet build dm/gfx/tools/dmsh_xlate/dmsh_xlate.csproj -c Release' +
           ' (needs the .NET 10 SDK, README-BL2.md section 5).')
}

function Find-Spirv([string]$name) {
    $envVar = $name.ToUpper().Replace('-', '_')
    if ([Environment]::GetEnvironmentVariable($envVar)) { return [Environment]::GetEnvironmentVariable($envVar) }
    if ($env:ANDROID_NDK_HOME) {
        foreach ($h in @('windows-x86_64', 'linux-x86_64', 'darwin-x86_64')) {
            $p = Join-Path $env:ANDROID_NDK_HOME "shader-tools\$h\$name.exe"
            if (Test-Path $p) { return $p }
            $p = Join-Path $env:ANDROID_NDK_HOME "shader-tools\$h\$name"
            if (Test-Path $p) { return $p }
        }
    }
    throw "$name not found. Set $envVar or ANDROID_NDK_HOME (SPIRV-Tools ship with the NDK)."
}

foreach ($m in @('main', 'sdk')) {
    if (-not (Test-Path (Join-Path $Exefs $m))) { throw "Missing NSO module: $Exefs\$m (README-BL2.md section 1)." }
}

$py = Find-Python
$outModuleDir = Join-Path $OutDir 'dm\out'
$shaderDir    = Join-Path $OutDir 'dm\shaders'
$jobsDir      = Join-Path $Root 'work\bl2\shaders-jobs'
New-Item -ItemType Directory -Force $outModuleDir, $shaderDir | Out-Null

Write-Host "== 1/3  patching the game program for Android" -ForegroundColor Cyan
$env:DM_TARGET = 'android'
foreach ($m in @('main', 'sdk')) {
    Write-Host "   $m"
    & $py (Join-Path $Root 'dm\tools\patch_nso.py') (Join-Path $Exefs $m) $outModuleDir $m
    if ($LASTEXITCODE -ne 0) { throw "patch_nso.py failed for $m" }
}
Remove-Item Env:DM_TARGET

if ($SkipShaders) {
    Write-Host "== 2/3  shader bundles skipped (-SkipShaders)" -ForegroundColor Yellow
} else {
    if (-not $Decoded -or -not $GlobalCache) {
        throw ('Shader translation needs -Decoded <decoded packages> and -GlobalCache ' +
               '<GlobalShaderCache-Switch.bin>. Decode them first (README-BL2.md section 5, step 1), ' +
               'or pass -SkipShaders.')
    }
    $xlate = Find-Xlate
    $opt = Find-Spirv 'spirv-opt'
    $val = Find-Spirv 'spirv-val'
    $env:XLATE = $xlate
    $env:SPIRV_OPT = $opt
    $env:SPIRV_VAL = $val
    $env:J = "$Jobs"

    Write-Host "== 2/3  collecting shader records from the decoded packages" -ForegroundColor Cyan
    & $py (Join-Path $Root 'tools\bl2_shader_jobs.py') $Decoded $GlobalCache $jobsDir
    if ($LASTEXITCODE -ne 0) { throw 'bl2_shader_jobs.py failed' }

    Write-Host "== 3/3  translating shaders to Vulkan (J=$Jobs, this takes a while)" -ForegroundColor Cyan
    & $py (Join-Path $Root 'dm\gfx\tools\dmsh_vk_xc2.py') $jobsDir $shaderDir
    if ($LASTEXITCODE -ne 0) { throw 'dmsh_vk_xc2.py failed' }
}

Write-Host ''
Write-Host "Prepared: $OutDir" -ForegroundColor Green
Write-Host "  dm\out      $((Get-ChildItem $outModuleDir -File).Count) files"
Write-Host "  dm\shaders  $((Get-ChildItem $shaderDir -File -ErrorAction SilentlyContinue).Count) files"
Write-Host ''
Write-Host 'Next:' -ForegroundColor Cyan
Write-Host '  1. Build the APK:  tools\build_apk.ps1  (see README-BL2.md section 4)'
Write-Host "  2. Put your own romfs\ and aoc\ next to dm\ on the phone under Download\Borderlands2Mobile\"
Write-Host '  3. Optional: copy a patch-cn\ overlay there and set DM_ROMFS_OVERLAY in dm\env'

if ($Push) {
    $adb = Get-Command adb -ErrorAction SilentlyContinue
    if (-not $adb) { throw 'adb not found in PATH; add platform-tools or drop -Push.' }
    $dest = '/sdcard/Download/Borderlands2Mobile/dm'
    $target = if ($Serial) { @('-s', $Serial, 'push') } else { @('push') }
    Write-Host ''
    Write-Host "Pushing dm\out and dm\shaders to $dest" -ForegroundColor Cyan
    & $adb.Source @target $outModuleDir "$dest/out"
    & $adb.Source @target $shaderDir "$dest/shaders"
}
