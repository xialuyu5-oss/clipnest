$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\scripts\setup_windows.ps1"
$checks = @(1..5 | ForEach-Object { [pscustomobject]@{Ready=$true} })
if (@(Get-ClipNestInstallPlan $checks).Count -ne 0) { throw 'Working components must be preserved' }
$checks[3].Ready = $false
if (@(Get-ClipNestInstallPlan $checks).Count -ne 0) { throw 'Do not install Deno when Node works' }
$checks[4].Ready = $false
if ((@(Get-ClipNestInstallPlan $checks) -join ',') -ne 'OpenJS.NodeJS.LTS') { throw 'Missing JS runtime not detected' }
$checks[1].Ready = $false
$checks[2].Ready = $false
if (@(Get-ClipNestInstallPlan $checks).Count -ne 2) { throw 'FFmpeg/ffprobe must use one package' }
$checks[0].Ready = $false
if ((@(Get-ClipNestInstallPlan $checks) -join ',') -ne 'Python.Python.3.13,Gyan.FFmpeg,OpenJS.NodeJS.LTS') { throw 'Unexpected installation scope' }
Write-Output 'Windows prerequisite selection passed; no installers invoked.'
