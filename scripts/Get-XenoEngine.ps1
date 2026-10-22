function Get-XenoEngineRoot {
    param([string]$EngineRoot)
    if (-not $EngineRoot) { $EngineRoot = $env:XENO_ENGINE_ROOT }
    if (-not $EngineRoot) {
        $manifestPath = Join-Path $env:ProgramData 'Epic\UnrealEngineLauncher\LauncherInstalled.dat'
        if (Test-Path -LiteralPath $manifestPath) {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            $installed = $manifest.InstallationList | Where-Object { $_.AppName -eq 'UE_5.8' } | Select-Object -First 1
            if ($installed) { $EngineRoot = $installed.InstallLocation }
        }
    }
    if (-not $EngineRoot -or -not (Test-Path -LiteralPath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'))) {
        throw 'Unreal 5.8 was not found. Supply -EngineRoot with its installation directory.'
    }
    return (Resolve-Path -LiteralPath $EngineRoot).Path
}
