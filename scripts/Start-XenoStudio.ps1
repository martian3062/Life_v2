param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $workspace 'runs\scenario-studio'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
try { $null = Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 2 } catch {
    Start-Process -FilePath (Get-Command uv).Source -ArgumentList @('run','python','-m','xeno.cli','serve') -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runDir 'service.out.log') -RedirectStandardError (Join-Path $runDir 'service.err.log') | Out-Null
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:8770/api/status' -TimeoutSec 2 } catch {
    Start-Process -FilePath (Get-Command uv).Source -ArgumentList @('run','python','-m','xeno.cli','scene-studio') -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runDir 'studio.out.log') -RedirectStandardError (Join-Path $runDir 'studio.err.log') -PassThru | Select-Object -ExpandProperty Id | Set-Content -LiteralPath (Join-Path $runDir 'studio.pid')
}
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8770' }
Write-Output 'Scenario Studio: http://127.0.0.1:8770'
