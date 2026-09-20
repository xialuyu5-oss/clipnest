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

# Exercise the permission boundary with simulated checks and an installer spy.
# Never invoke WinGet or change this computer's installed software in tests.
$script:testChecks = @(1..5 | ForEach-Object { [pscustomobject]@{Name='Test';Ready=$false;Detail='fixture'} })
$script:testAnswers = [System.Collections.Generic.Queue[string]]::new()
$script:installCalls = @()
$script:promptCalls = 0
$script:hasWinget = $true
function Get-ClipNestEnvironment { $script:testChecks }
function Get-Command {
    param($Name, $CommandType, $ErrorAction)
    if ($Name -ne 'winget') { throw 'Unexpected external tool lookup' }
    if ($script:hasWinget) { [pscustomobject]@{ Source='TEST-ONLY-NO-EXECUTABLE' } }
}
function Read-Host {
    param($Prompt)
    $script:promptCalls++
    if ($script:testAnswers.Count -eq 0) { throw 'Unexpected permission prompt' }
    $script:testAnswers.Dequeue()
}
function Invoke-ClipNestPackageInstall {
    param($InstallerPath, $Package)
    if ($InstallerPath -ne 'TEST-ONLY-NO-EXECUTABLE') { throw 'Unsafe installer path' }
    $script:installCalls += $Package
}
$InstallMissing = $false
$Json = $false
Invoke-ClipNestSetup
if ($script:promptCalls -or $script:installCalls.Count) { throw 'Check-only mode must not prompt or install' }
$InstallMissing = $true
$Json = $true
$null = Invoke-ClipNestSetup
if ($script:promptCalls -or $script:installCalls.Count) { throw 'JSON reporting must not install' }
$Json = $false
foreach ($answer in @('', 'N', 'yes')) { $script:testAnswers.Enqueue($answer) }
Invoke-ClipNestSetup
if ($script:installCalls.Count) { throw 'Blank, N or other unconfirmed answers must not install' }
foreach ($answer in @('N', 'Y', '')) { $script:testAnswers.Enqueue($answer) }
Invoke-ClipNestSetup
if (($script:installCalls -join ',') -ne 'Gyan.FFmpeg') { throw 'Install only the separately approved component' }
$script:installCalls = @()
$script:promptCalls = 0
$script:hasWinget = $false
Invoke-ClipNestSetup
if ($script:promptCalls -or $script:installCalls.Count) { throw 'No WinGet: instructions only' }
$script:hasWinget = $true
$script:testChecks | ForEach-Object { $_.Ready=$true }
Invoke-ClipNestSetup
if ($script:promptCalls -or $script:installCalls.Count) { throw 'Ready systems must not install or ask to install' }
Write-Output 'Setup consent cases passed; no real download or installer was invoked.'
