# Compile YouStrow : tests -> application autonome (dist\YouStrow\YouStrow.exe) -> installeur (dist\YouStrow-Setup-x.y.z.exe)
param([switch]$SkipTests, [switch]$SkipInstaller)
$ErrorActionPreference = "Continue"   # PyInstaller écrit ses INFO sur stderr ; les échecs sont détectés via $LASTEXITCODE
Set-Location $PSScriptRoot
$version = (Select-String -Path youstrow\__init__.py -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller }
if (-not $SkipTests) { .\.venv\Scripts\python.exe -m pytest tests -q; if ($LASTEXITCODE) { throw "tests en échec" } }
.\.venv\Scripts\python.exe -m PyInstaller youstrow.spec --noconfirm --clean
if ($LASTEXITCODE) { throw "PyInstaller a échoué" }
Write-Host "OK -> dist\YouStrow\YouStrow.exe"
if (-not $SkipInstaller) {
    $iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "Inno Setup 6 introuvable (winget install JRSoftware.InnoSetup)" }
    & $iscc "/DAppVersion=$version" installer\youstrow.iss
    if ($LASTEXITCODE) { throw "Inno Setup a échoué" }
    Write-Host "OK -> dist\YouStrow-Setup-$version.exe"
}
