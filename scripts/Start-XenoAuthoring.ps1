param([string]$EngineRoot, [switch]$Visible)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Get-XenoEngine.ps1')
$engine = Get-XenoEngineRoot $EngineRoot
$workspace = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $workspace 'runs\authoring-editor.pid'
if (Test-Path -LiteralPath $pidFile) {
    $previousAuthorPid = [int](Get-Content -LiteralPath $pidFile)
    $existingAuthor = Get-CimInstance Win32_Process -Filter "ProcessId=$previousAuthorPid" -ErrorAction SilentlyContinue
    if ($existingAuthor -and $existingAuthor.ExecutablePath -eq (Join-Path $engine 'Engine\Binaries\Win64\UnrealEditor.exe') -and $existingAuthor.CommandLine -like '*Life_v2*Xeno.uproject*') {
        Write-Output 'XENO authoring editor is already running or starting.'
        return
    }
}
$previousScene = $env:XENO_SCENE_FILE
try {
    $env:XENO_SCENE_FILE = Join-Path $workspace 'runs\scenario-studio\active-scene.json'
    if (-not (Test-Path -LiteralPath $env:XENO_SCENE_FILE)) { throw 'Start Scenario Studio first.' }
    $arguments = @(('"{0}"' -f (Join-Path $workspace 'unreal\Xeno\Xeno.uproject')), '-nosplash','-nosound','-unattended',('-abslog="{0}"' -f (Join-Path $workspace 'runs\authoring-editor.log')))
    if (-not $Visible) { $arguments += '-nullrhi' }
    $style = if ($Visible) { 'Normal' } else { 'Hidden' }
    $p = Start-Process -FilePath (Join-Path $engine 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $arguments -WorkingDirectory $workspace -WindowStyle $style -PassThru
    $p.Id | Set-Content -LiteralPath (Join-Path $workspace 'runs\authoring-editor.pid')
    Write-Output 'XENO authoring editor starting. Native MCP: http://127.0.0.1:8000/mcp'
} finally { $env:XENO_SCENE_FILE = $previousScene }
