# Sea Level Dashboard - watchdog (Task Scheduler: at startup, repeat every 1 minute, indefinitely).
# Action: powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<app>\scripts\onprem\watchdog.ps1"
# If the API (30886) or the site (30887) is not listening, it runs start_servers_noninteractive.bat,
# which starts only the missing one and never kills other python/node processes (the DB sync keeps running).
$App          = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Starter      = Join-Path $PSScriptRoot 'start_servers_noninteractive.bat'
$LogDir       = Join-Path $App 'logs'
$Log          = Join-Path $LogDir 'watchdog.log'
$Lock         = Join-Path $LogDir 'watchdog.lock'
$GraceMinutes = 3

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log([string]$Message) {
    if ((Test-Path $Log) -and (Get-Item $Log).Length -gt 5MB) { Move-Item $Log "$Log.old" -Force }
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message" | Add-Content -Path $Log -Encoding UTF8
}
function Test-Port([int]$Port) {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

$backendUp  = Test-Port 30886
$frontendUp = Test-Port 30887
if ($backendUp -and $frontendUp) { exit 0 }

if (Test-Path $Lock) {
    $age = (Get-Date) - (Get-Item $Lock).LastWriteTime
    if ($age.TotalMinutes -lt $GraceMinutes) { exit 0 }   # a start is already in progress
}
if (-not (Test-Path $Starter)) { Write-Log "ERROR: starter not found at $Starter"; exit 1 }

Set-Content -Path $Lock -Value (Get-Date).ToString('s')
Write-Log "Down (api=$backendUp, site=$frontendUp) - running $Starter"
Start-Process -FilePath $Starter -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
exit 0
