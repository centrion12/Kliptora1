$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python Launcher (py.exe) bulunamadı. Python 3.12 kur.' }

Push-Location .\Kliptora
try {
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip wheel
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
    .\.venv\Scripts\pyinstaller.exe --clean --noconfirm Kliptora.spec
} finally {
    Pop-Location
}

$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidate = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    if (Test-Path $candidate) { $iscc = $candidate } else { throw 'Inno Setup 6 bulunamadı.' }
}

& $iscc .\installer\Kliptora.iss

$setup = Resolve-Path .\release\Kliptora-Setup-v2.3.3.exe
Write-Host "Kurulum hazır: $setup" -ForegroundColor Green
Get-FileHash $setup -Algorithm SHA256 | Format-List
