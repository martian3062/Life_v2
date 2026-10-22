$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    uv venv runs/physics/.venv --python 3.12 --allow-existing
    if ($LASTEXITCODE -ne 0) { throw 'Physics virtual environment creation failed.' }
    uv pip install --python runs/physics/.venv/Scripts/python.exe -r configs/physics-requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Physics dependency installation failed.' }
} finally { Pop-Location }
