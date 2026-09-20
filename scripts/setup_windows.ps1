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

function Show-ClipNestDownloadOptions {
    Write-Host 'Official download instructions (open these yourself if WinGet is unavailable):'
    Write-Host 'Python 3.11+: https://www.python.org/downloads/'
    Write-Host 'FFmpeg + ffprobe: https://ffmpeg.org/download.html'
    Write-Host 'Node.js 22+: https://nodejs.org/en/download'
    Write-Host 'Or Deno 2.3+: https://docs.deno.com/runtime/getting_started/installation/'
}

function Invoke-ClipNestPackageInstall {
    param([string]$InstallerPath, [string]$Package)
    & $InstallerPath install --id $Package --exact --source winget
    if ($LASTEXITCODE -ne 0) {
        throw "Installation did not complete: $Package. Resolve the displayed error before retrying."
    }
}

function Invoke-ClipNestSetup {
    $checks = @(Get-ClipNestEnvironment)
    $packages = @(Get-ClipNestInstallPlan $checks)
    if ($Json) {
        [pscustomobject]@{ready=($packages.Count -eq 0); checks=$checks; packages=$packages} | ConvertTo-Json -Depth 4
        return
    }
    Write-Host 'ClipNest environment check (offline; nothing installed by checking)'
    $checks | Format-Table Name,Ready,Detail -AutoSize | Out-Host
    Write-Host 'Deno OR Node is needed, not both.'
    if ($packages.Count -eq 0) {
        Write-Host 'System prerequisites are ready. Nothing downloaded or installed.'
        Write-Host 'Next: extract the separate ClipNest PC package and run start-local.bat.'
        Write-Host 'Project dependencies (yt-dlp / EJS) are separate; the launcher asks before downloading them.'
        return
    }
    Write-Host ('Missing / incompatible components: ' + ($packages -join ', '))
    Show-ClipNestDownloadOptions
    if (-not $InstallMissing) {
        Write-Host 'Nothing installed. Run install-missing.bat to review and install the components.'
        return
    }
    $winget = Get-Command winget -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $winget) {
        Write-Host 'WinGet is unavailable. Nothing downloaded or installed. Use the official links above.'
        return
    }
    Write-Host 'Only a Y answer permits downloading and installing that item from the WinGet source.'
    Write-Host 'Enter or N skips it. Windows may ask for administrator permission. Review publisher agreements.'
    $installed = 0
    foreach ($package in $packages) {
        $answer = Read-Host "Download AND install $package now? [y/N]"
        if ($answer -notmatch '^[Yy]$') {
            Write-Host "Skipped $package. No download or installation requested for this item."
            continue
        }
        Invoke-ClipNestPackageInstall -InstallerPath $winget.Source -Package $package
        $installed++
    }
    if ($installed -eq 0) { Write-Host 'Nothing downloaded or installed.'; return }
    Write-Host 'Close this window, reopen check-environment.bat and verify the new PATH/version results.'
    Write-Host 'An installer exit code is not a successful environment check. Do not continue until the recheck passes.'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-ClipNestSetup } catch { Write-Error $_; exit 1 }
}
