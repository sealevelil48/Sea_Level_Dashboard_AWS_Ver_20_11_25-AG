<# 
.SYNOPSIS
    Tests Sea Level Dashboard connectivity (local and external)
.DESCRIPTION
    Verifies backend/frontend are accessible locally and externally.
#>

param(
    [string]$PublicIP = "85.155.88.90",
    [int]$BackendPort = 30886,
    [int]$FrontendPort = 30887
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Sea Level Dashboard - Connectivity Test" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check if backend process is running
Write-Host "1. Backend Process Check" -ForegroundColor Yellow
Write-Host "------------------------"
$pythonProcs = Get-Process python* -ErrorAction SilentlyContinue
$backendProc = $pythonProcs | Where-Object { $_.CommandLine -match "local_server" }
if ($backendProc) {
    Write-Host "  ✅ Backend running (PID: $($backendProc.Id))" -ForegroundColor Green
    Write-Host "     Command: $($backendProc.CommandLine)" -ForegroundColor Gray
} else {
    Write-Host "  ❌ Backend NOT running" -ForegroundColor Red
    Write-Host "     Start with: start_backend.bat" -ForegroundColor Gray
}

# Test 2: Check if frontend process is running
Write-Host ""
Write-Host "2. Frontend Process Check" -ForegroundColor Yellow
Write-Host "-------------------------"
$nodeProcs = Get-Process node* -ErrorAction SilentlyContinue
$frontendProc = $nodeProcs | Where-Object { $_.CommandLine -match "react-scripts" }
if ($frontendProc) {
    Write-Host "  ✅ Frontend running (PID: $($frontendProc.Id))" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Frontend NOT running (or not detected)" -ForegroundColor Yellow
    Write-Host "     Start with: npm run start (local) or npm run start-external (external)" -ForegroundColor Gray
}

# Test 3: Local backend connectivity
Write-Host ""
Write-Host "3. Local Backend (127.0.0.1:$BackendPort)" -ForegroundColor Yellow
Write-Host "------------------------------------"
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 5 -UseBasicParsing
    $health = $response.Content | ConvertFrom-Json
    Write-Host "  ✅ Backend responding locally" -ForegroundColor Green
    Write-Host "     Status: $($health.status)" -ForegroundColor Gray
    Write-Host "     Database: $($health.database)" -ForegroundColor Gray
    Write-Host "     Platform: $($health.platform)" -ForegroundColor Gray
} catch {
    Write-Host "  ❌ Backend NOT responding locally" -ForegroundColor Red
    Write-Host "     Error: $($_.Exception.Message)" -ForegroundColor Gray
}

# Test 4: Local frontend connectivity
Write-Host ""
Write-Host "4. Local Frontend (127.0.0.1:$FrontendPort)" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✅ Frontend serving on localhost" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Frontend returned HTTP $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Frontend NOT responding on localhost" -ForegroundColor Red
    Write-Host "     Error: $($_.Exception.Message)" -ForegroundColor Gray
}

# Test 5: External backend (public IP)
Write-Host ""
Write-Host "5. External Backend ($($PublicIP):$($BackendPort))" -ForegroundColor Yellow
Write-Host "----------------"

try {
    $response = Invoke-WebRequest -Uri "http://$($PublicIP):$($BackendPort)/api/health" -TimeoutSec 10 -UseBasicParsing
    $health = $response.Content | ConvertFrom-Json
    Write-Host "  ✅ Backend accessible EXTERNALLY" -ForegroundColor Green
    Write-Host "     Status: $($health.status)" -ForegroundColor Gray
} catch {
    Write-Host "  ❌ Backend NOT accessible externally" -ForegroundColor Red
    Write-Host "     Error: $($_.Exception.Message)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     LIKELY CAUSES:" -ForegroundColor Yellow
    Write-Host "     • Cloud Security Group / NSG / Firewall blocking port $BackendPort" -ForegroundColor Gray
    Write-Host "     • Windows Firewall not configured (run configure_firewall.ps1)" -ForegroundColor Gray
    Write-Host "     • Backend not binding to 0.0.0.0 (check HOST env var)" -ForegroundColor Gray
}

# Test 6: External frontend
Write-Host ""
Write-Host "6. External Frontend ($($PublicIP):$($FrontendPort))" -ForegroundColor Yellow
Write-Host "----------------"

try {
    $response = Invoke-WebRequest -Uri "http://$($PublicIP):$($FrontendPort)" -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✅ Frontend accessible EXTERNALLY" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Frontend returned HTTP $($response.StatusCode) externally" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Frontend NOT accessible externally" -ForegroundColor Red
    Write-Host "     Error: $($_.Exception.Message)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     LIKELY CAUSES:" -ForegroundColor Yellow
    Write-Host "     • Cloud Security Group / NSG / Firewall blocking port $FrontendPort" -ForegroundColor Gray
    Write-Host "     • Windows Firewall not configured (run configure_firewall.ps1)" -ForegroundColor Gray
    Write-Host "     • Frontend not binding to 0.0.0.0 (check HOST in start-external)" -ForegroundColor Gray
}

# Test 7: CORS test
Write-Host ""
Write-Host "7. CORS Preflight Test" -ForegroundColor Yellow
Write-Host "----------------"

try {
    $headers = @{
        "Origin" = "http://$($PublicIP):$($FrontendPort)"
        "Access-Control-Request-Method" = "GET"
        "Access-Control-Request-Headers" = "Content-Type"
    }
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/stations" -Method Options -Headers $headers -TimeoutSec 5 -UseBasicParsing
    $corsHeaders = @(
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods", 
        "Access-Control-Allow-Headers"
    )
    $corsHeaders | ForEach-Object {
        $headerName = $_
        if ($response.Headers[$headerName]) {
            Write-Host "  ✅ ${headerName}: $($response.Headers[$headerName])" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  ${headerName}: Not set" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  ❌ CORS test failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Summary & Next Steps" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "FOR LOCAL DEVELOPMENT:" -ForegroundColor Cyan
Write-Host "  1. Backend: start_backend.bat" -ForegroundColor Gray
Write-Host "  2. Frontend: cd frontend && npm run start  (uses localhost API)" -ForegroundColor Gray
Write-Host ""

Write-Host "FOR EXTERNAL CLIENT ACCESS:" -ForegroundColor Cyan
Write-Host "  1. Run configure_firewall.ps1 as Administrator" -ForegroundColor Gray
Write-Host "  2. Configure CLOUD PROVIDER firewall (Security Group/NSG)" -ForegroundColor Gray
Write-Host "  3. Backend: start_backend.bat" -ForegroundColor Gray
Write-Host "  4. Frontend: cd frontend && npm run start-external" -ForegroundColor Gray
Write-Host "  5. Clients access: http://$($PublicIP):$($FrontendPort)" -ForegroundColor Gray
Write-Host ""