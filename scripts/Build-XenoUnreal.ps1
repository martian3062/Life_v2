param(
    [string]$EngineRoot,
    [ValidateSet('Editor','Package')][string]$Target = 'Editor'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Get-XenoEngine.ps1')
$engine = Get-XenoEngineRoot $EngineRoot
$workspace = Split-Path -Parent $PSScriptRoot
$project = Join-Path $workspace 'unreal\Xeno\Xeno.uproject'
if ($Target -eq 'Editor') {
    & (Join-Path $workspace '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'prepare_canyon_assets.py')
    if ($LASTEXITCODE -ne 0) { throw 'Canyon asset preparation failed' }
    & (Join-Path $engine 'Engine\Build\BatchFiles\Build.bat') XenoEditor Win64 Development "-Project=$project" -WaitMutex -NoHotReloadFromIDE
    if ($LASTEXITCODE -ne 0) { throw "Unreal editor compilation failed ($LASTEXITCODE)" }
    & (Join-Path $engine 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript "-script=$PSScriptRoot\create_unreal_assets.py" -unattended -nullrhi -nosound -nosplash
    if ($LASTEXITCODE -ne 0) { throw "Unreal asset generation failed ($LASTEXITCODE)" }
} else {
    $archive = Join-Path $workspace 'runs\unreal-package'
    & (Join-Path $engine 'Engine\Build\BatchFiles\RunUAT.bat') BuildCookRun "-project=$project" -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -archive "-archivedirectory=$archive" -utf8output -unattended -nullrhi -NoCodeSign
    if ($LASTEXITCODE -ne 0) { throw "Unreal packaging failed ($LASTEXITCODE)" }
    Write-Output "Packaged build: $archive"
}
