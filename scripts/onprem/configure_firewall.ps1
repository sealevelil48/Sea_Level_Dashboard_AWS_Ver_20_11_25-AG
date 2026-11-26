<#
.SYNOPSIS
    Configures Windows Firewall for Sea Level Dashboard external access
.DESCRIPTION
    Creates inbound rules for ports 30886 (backend) and 30887 (frontend)
    Run as Administrator
#>

param(
    [int]$BackendPort = 30886,
    [int]$FrontendPort = 30887
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Sea Level Dashboard - Firewall Config" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ ERROR: Must run as Administrator!" -ForegroundColor Red
    Write-Host "   Right-click PowerShell → 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Running as Administrator" -ForegroundColor Green
Write-Host ""

# Configure backend port
Write-Host "Configuring Backend Port ($BackendPort)..." -ForegroundColor Yellow
$ruleNameBackend = "SeaLevel Dashboard - Backend API ($BackendPort)"
$existingBackend = Get-NetFirewallRule -DisplayName $ruleNameBackend -ErrorAction SilentlyContinue

if ($existingBackend) {
    Write-Host "  Rule exists, updating..." -ForegroundColor Gray
    Set-NetFirewallRule -DisplayName $ruleNameBackend -Enabled True -Action Allow -Profile Any
} else {
    New-NetFirewallRule `
        -DisplayName $ruleNameBackend `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $BackendPort `
        -Action Allow `
        -Profile Any `
        -Enabled True `
        -Description "Sea Level Dashboard Backend API"
    Write-Host "  ✅ Created backend firewall rule" -ForegroundColor Green
}

# Configure frontend port
Write-Host "Configuring Frontend Port ($FrontendPort)..." -ForegroundColor Yellow
$ruleNameFrontend = "SeaLevel Dashboard - Frontend ($FrontendPort)"
$existingFrontend = Get-NetFirewallRule -DisplayName $ruleNameFrontend -ErrorAction SilentlyContinue

if ($existingFrontend) {
    Write-Host "  Rule exists, updating..." -ForegroundColor Gray
    Set-NetFirewallRule -DisplayName $ruleNameFrontend -Enabled True -Action Allow -Profile Any
} else {
    New-NetFirewallRule `
        -DisplayName $ruleNameFrontend `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $FrontendPort `
        -Action Allow `
        -Profile Any `
        -Enabled True `
        -Description "Sea Level Dashboard Frontend"
    Write-Host "  ✅ Created frontend firewall rule" -ForegroundColor Green
}

# Also allow Python/Node processes
Write-Host ""
Write-Host "Configuring Application Rules..." -ForegroundColor Yellow

# Python
$pythonRule = "SeaLevel Dashboard - Python Backend"
$existingPython = Get-NetFirewallRule -DisplayName $pythonRule -ErrorAction SilentlyContinue
if (-not $existingPython) {
    try {
        $pythonPath = (Get-Command python).Source
        New-NetFirewallRule `
            -DisplayName $pythonRule `
            -Direction Inbound `
            -Program $pythonPath `
            -Action Allow `
            -Profile Any `
            -Enabled True
        Write-Host "  ✅ Created Python rule" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not create Python rule: $_" -ForegroundColor Yellow
    }
}

# Node
$nodeRule = "SeaLevel Dashboard - Node Frontend"
$existingNode = Get-NetFirewallRule -DisplayName $nodeRule -ErrorAction SilentlyContinue
if (-not $existingNode) {
    try {
        $nodePath = (Get-Command node).Source
        New-NetFirewallRule `
            -DisplayName $nodeRule `
            -Direction Inbound `
            -Program $nodePath `
            -Action Allow `
            -Profile Any `
            -Enabled True
        Write-Host "  ✅ Created Node rule" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not create Node rule: $_" -ForegroundColor Yellow
    }
}

# npm
$npmRule = "SeaLevel Dashboard - NPM"
$existingNpm = Get-NetFirewallRule -DisplayName $npmRule -ErrorAction SilentlyContinue
if (-not $existingNpm) {
    try {
        $npmPath = (Get-Command npm.cmd).Source
        New-NetFirewallRule `
            -DisplayName $npmRule `
            -Direction Inbound `
            -Program $npmPath `
            -Action Allow `
            -Profile Any `
            -Enabled True
        Write-Host "  ✅ Created NPM rule" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not create NPM rule: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Windows Firewall Configuration Complete" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Rules created:" -ForegroundColor Green
Get-NetFirewallRule -DisplayName "SeaLevel Dashboard*" | Format-Table DisplayName, Enabled, Direction, Action, LocalPort -AutoSize
Write-Host ""
Write-Host "⚠️  IMPORTANT: You MUST ALSO configure your CLOUD PROVIDER firewall:" -ForegroundColor Yellow
Write-Host "   • AWS: Security Group → Inbound Rules → Add ports 30886, 30887" -ForegroundColor Gray
Write-Host "   • Azure: NSG → Inbound Security Rules → Add ports 30886, 30887" -ForegroundColor Gray
Write-Host "   • GCP: VPC Firewall → Ingress → Allow TCP 30886, 30887" -ForegroundColor Gray
Write-Host "   • DigitalOcean: Networking → Firewalls → Add ports 30886, 30887" -ForegroundColor Gray
Write-Host ""