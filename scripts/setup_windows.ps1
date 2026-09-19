# A user-run prerequisite helper. Checks are offline; installation is explicit.
param([switch]$InstallMissing, [switch]$Json)
Set-StrictMode -Version Latest

function Get-ClipNestTool {
    param([string]$Name, [string[]]$Arguments, [version]$Minimum = '0.0')
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $detail = 'Not installed / not on PATH'
    $ready = $false
    if ($command) {
        try {
            $output = & $command.Source @Arguments 2>&1
            $code = $LASTEXITCODE
            $detail = ($output | Select-Object -First 1).ToString()
            $match = [regex]::Match($detail, '(\d+)\.(\d+)')
            $ready = $code -eq 0 -and $match.Success -and [version]$match.Value -ge $Minimum
        } catch { $detail = 'Could not run this component' }
    }
    [pscustomobject]@{ Name=$Name; Ready=[bool]$ready; Detail=$detail }
}

function Get-ClipNestEnvironment {
    $python = Get-ClipNestTool 'py' @('-3', '--version') '3.11'
    if (-not $python.Ready) { $python = Get-ClipNestTool 'python' @('--version') '3.11' }
    $python.Name = 'Python'
    @($python; (Get-ClipNestTool 'ffmpeg' @('-version')); (Get-ClipNestTool 'ffprobe' @('-version'));
      (Get-ClipNestTool 'deno' @('--version') '2.3'); (Get-ClipNestTool 'node' @('--version') '22.0'))
}

function Get-ClipNestInstallPlan {
    param([object[]]$Checks)
    if (-not $Checks[0].Ready) { 'Python.Python.3.13' }
    if (-not $Checks[1].Ready -or -not $Checks[2].Ready) { 'Gyan.FFmpeg' }
    if (-not $Checks[3].Ready -and -not $Checks[4].Ready) { 'OpenJS.NodeJS.LTS' }
}

function Invoke-ClipNestSetup {
    $checks = @(Get-ClipNestEnvironment)
    $packages = @(Get-ClipNestInstallPlan $checks)
    if ($Json) {
        [pscustomobject]@{ready=($packages.Count -eq 0); checks=$checks; packages=$packages} | ConvertTo-Json -Depth 4
        return
    }
    Write-Host 'ClipNest environment check (runs locally)'
    $checks | Format-Table Name,Ready,Detail -AutoSize | Out-Host
    Write-Host 'Deno OR Node is needed, not both.'
    if ($packages.Count -eq 0) { Write-Host 'Ready. Start ClipNest using start-local.bat.'; return }
    Write-Host ('Missing / incompatible components: ' + ($packages -join ', '))
    if (-not $InstallMissing) {
        Write-Host 'Nothing installed. Run install-missing.bat to review and install the components.'
        return
    }
    $winget = Get-Command winget -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $winget) { throw 'WinGet is unavailable. Use the publisher links in README.md / docs/LOCAL_PROCESSING.md.' }
    Write-Host 'This downloads third-party installers using WinGet and may request administrator approval.'
    Write-Host 'Installed working components will be left alone. Review any publisher agreements shown.'
    foreach ($package in $packages) {
        if ((Read-Host "Install $package now? Type Y to proceed") -notmatch '^[Yy]$') { continue }
        & $winget.Source install --id $package --exact --source winget
        if ($LASTEXITCODE -ne 0) { throw "Installation did not complete: $package. Resolve the displayed error before retrying." }
    }
    Write-Host 'Close this window, reopen check-environment.bat and verify PATH/version detection.'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-ClipNestSetup } catch { Write-Error $_; exit 1 }
}
