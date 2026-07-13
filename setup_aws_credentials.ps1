Param(
    [string]$ProfileName = "survey_of_israel",
    [string]$AccessKey,
    [string]$SecretKey
)

if (-not $AccessKey) { $AccessKey = Read-Host "Enter AWS Access Key" }
if (-not $SecretKey) { $SecretKey = Read-Host "Enter AWS Secret Key" }

$credDir = Join-Path $env:USERPROFILE ".aws"
if (-not (Test-Path $credDir)) { New-Item -ItemType Directory -Path $credDir | Out-Null }
$credFile = Join-Path $credDir "credentials"

$profileContent = "[$ProfileName]`naws_access_key_id = $AccessKey`naws_secret_access_key = $SecretKey`n"

if (Test-Path $credFile) {
    $text = Get-Content $credFile -Raw
    $pattern = "(?ms)^\[$ProfileName\].*?(?=^\[|\z)"
    if ($text -match $pattern) {
        $newText = [regex]::Replace($text, $pattern, $profileContent)
    } else {
        $newText = $text + "`n" + $profileContent
    }
    Set-Content -Path $credFile -Value $newText
} else {
    Set-Content -Path $credFile -Value $profileContent
}

Write-Host "Wrote profile '$ProfileName' to $credFile" -ForegroundColor Green
