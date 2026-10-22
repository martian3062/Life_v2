param([Parameter(Mandatory=$true)][int]$LauncherPid)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$gamePath = Join-Path $workspace 'runs\unreal-package\Windows\Xeno\Binaries\Win64\Xeno.exe'
Get-CimInstance Win32_Process -Filter "Name='Xeno.exe'" | Where-Object {
    $_.ExecutablePath -eq $gamePath -and $_.ParentProcessId -eq $LauncherPid
} | ForEach-Object {
    $ownedGame = Get-Process -Id $_.ProcessId
    $null = $ownedGame.CloseMainWindow()
    if (-not $ownedGame.WaitForExit(10000)) { throw 'The owned game did not close.' }
}
