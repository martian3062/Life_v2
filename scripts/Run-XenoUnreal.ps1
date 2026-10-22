param(
    [string]$EngineRoot,
    [ValidateSet('EditorGame','Packaged')][string]$Mode = 'EditorGame',
    [ValidateSet('Overview','Rover')][string]$View = 'Overview',
    [ValidateSet('Lit','WorldNormal')][string]$RenderPass = 'Lit',
    [string]$SceneFile,
    [string]$PhysicsField,
    [switch]$NoLivePhysics,
    [switch]$WaitForGame,
    [switch]$CleanView,
    [switch]$Smoke
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Get-XenoEngine.ps1')
$engine = Get-XenoEngineRoot $EngineRoot
$workspace = Split-Path -Parent $PSScriptRoot
$project = Join-Path $workspace 'unreal\Xeno\Xeno.uproject'
$health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 5
if ($health.model_version -ne 'f0-maintenance-2') { throw 'Unexpected XENO model version' }
$adminToken = $env:XENO_ADMIN_TOKEN
if (-not $adminToken) {
    $credentialsPath = Join-Path $workspace 'runs\local\credentials.private.json'
    $adminToken = (Get-Content -LiteralPath $credentialsPath -Raw | ConvertFrom-Json).admin_token
}
$adminHeaders = @{ Authorization = "Bearer $adminToken" }
$episode = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8766/v1/admin/episodes' -Headers $adminHeaders -ContentType 'application/json' -Body '{}'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$output = Join-Path $workspace "runs\unreal-$Mode-$stamp"
New-Item -ItemType Directory -Path $output | Out-Null
$sessionPath = Join-Path $output 'session.private.json'
$resultPath = Join-Path $output 'runtime-check.json'
@{
    base_url = 'http://127.0.0.1:8766'
    episode_id = $episode.episode_id
    investigator_token = $episode.investigator_token
    result_path = $resultPath
} | ConvertTo-Json | Set-Content -LiteralPath $sessionPath -Encoding UTF8
$previousSession = $env:XENO_SESSION_FILE
$previousSmoke = $env:XENO_SMOKE
$previousAutorun = $env:XENO_AUTORUN
$previousView = $env:XENO_CAMERA_VIEW
$previousScene = $env:XENO_SCENE_FILE
$previousClean = $env:XENO_CLEAN_VIEW
$previousPhysics = $env:XENO_WELL_FIELD_FILE
$previousLive = $env:XENO_LIVE_PHYSICS_DIR
$physicsProcess = $null
try {
    $env:XENO_SESSION_FILE = $sessionPath
    $env:XENO_SMOKE = if ($Smoke) { '1' } else { '0' }
    $env:XENO_AUTORUN = '1'
    $env:XENO_CAMERA_VIEW = $View
    $env:XENO_CLEAN_VIEW = if ($CleanView) { '1' } else { '0' }
    if (-not $NoLivePhysics) {
        $pythonPhysics = Join-Path $workspace 'runs\physics\.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $pythonPhysics)) { throw 'Run scripts/Install-XenoPhysics.ps1 first.' }
        $liveDirectory = Join-Path $output 'physics'
        New-Item -ItemType Directory -Path $liveDirectory | Out-Null
        $env:XENO_LIVE_PHYSICS_DIR = $liveDirectory
        $physicsArguments = @('-m','xeno.physics.worker','--directory',('"{0}"' -f $liveDirectory))
        $physicsProcess = Start-Process -FilePath $pythonPhysics -ArgumentList $physicsArguments -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $liveDirectory 'worker.log') -RedirectStandardError (Join-Path $liveDirectory 'worker-error.log') -PassThru
        $physicsProcess.Id | Set-Content -LiteralPath (Join-Path $liveDirectory 'worker.pid')
    }
    if ($SceneFile) { $env:XENO_SCENE_FILE = (Resolve-Path -LiteralPath $SceneFile).Path }
    if (-not $PhysicsField) { $PhysicsField = Join-Path $workspace 'runs\well\reference-field.json' }
    if (Test-Path -LiteralPath $PhysicsField) { $env:XENO_WELL_FIELD_FILE = (Resolve-Path -LiteralPath $PhysicsField).Path }
    $arguments = @()
    if ($Mode -eq 'EditorGame') {
        $executable = Join-Path $engine 'Engine\Binaries\Win64\UnrealEditor.exe'
        $arguments += @(('"{0}"' -f $project), '/Game/Maps/XenoMission', '-game')
    } else {
        $executable = Join-Path $workspace 'runs\unreal-package\Windows\Xeno.exe'
        if (-not (Test-Path -LiteralPath $executable)) { throw 'Build the packaged target first' }
    }
    $arguments += @('-nosplash','-nosound','-unattended',('-abslog="{0}"' -f (Join-Path $output 'unreal.log')))
    if ($Smoke) { $arguments += '-nullrhi' } else {
        $arguments += @('-windowed','-ResX=1280','-ResY=800')
        if ($RenderPass -eq 'WorldNormal') {
            if ($Mode -ne 'EditorGame') { throw 'WorldNormal diagnostic capture requires EditorGame mode' }
            $arguments += '-ExecCmds="t.MaxFPS 30,ShowFlag.VisualizeBuffer 1,r.BufferVisualizationTarget WorldNormal"'
        } else { $arguments += '-ExecCmds="t.MaxFPS 30"' }
    }
    $windowStyle = if ($Smoke) { 'Hidden' } else { 'Normal' }
    $process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $workspace -WindowStyle $windowStyle -PassThru
    $process.Id | Set-Content -LiteralPath (Join-Path $output 'launcher.pid')
    if ($physicsProcess) { $process.Id | Set-Content -LiteralPath (Join-Path $liveDirectory 'owner.pid') }
    Write-Output "Unreal launched. Run artifacts: $output"
    if ($WaitForGame -and -not $Smoke) { $process.WaitForExit() }
    if ($Smoke) {
        if (-not $process.WaitForExit(300000)) { throw 'Unreal startup/check exceeded five minutes; see the run log' }
        if (-not (Test-Path -LiteralPath $resultPath)) { throw "Unreal exited without a verification result. See $output\unreal.log" }
        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        if (-not $result.success) { throw "Unreal verification failed: $($result.error)" }
        $evaluation = Invoke-RestMethod -Uri "http://127.0.0.1:8766/v1/admin/episodes/$($episode.episode_id)/evaluation" -Headers $adminHeaders
        if ($result.final_revision -ne 6 -or $result.stream_events -ne 7 -or
            $evaluation.costs.lab_actions -ne 1 -or
            [Math]::Abs($evaluation.costs.sample_volume_m3 - 2e-7) -gt 1e-18 -or
            $evaluation.global_inventory_residual_token -gt 1e-15) {
            throw 'The private evaluator did not confirm the expected finite-sample mission and inventory tolerance'
        }
        $evaluation | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $output 'evaluation.private.json') -Encoding UTF8
        $result | ConvertTo-Json -Depth 6
    }
} finally {
    $env:XENO_SESSION_FILE = $previousSession
    $env:XENO_SMOKE = $previousSmoke
    $env:XENO_AUTORUN = $previousAutorun
    $env:XENO_CAMERA_VIEW = $previousView
    $env:XENO_SCENE_FILE = $previousScene
    $env:XENO_CLEAN_VIEW = $previousClean
    $env:XENO_WELL_FIELD_FILE = $previousPhysics
    $env:XENO_LIVE_PHYSICS_DIR = $previousLive
    if ($physicsProcess -and ($WaitForGame -or $Smoke)) { New-Item -ItemType File -Path (Join-Path $liveDirectory 'stop') -Force | Out-Null }
    $adminToken = $null
}
