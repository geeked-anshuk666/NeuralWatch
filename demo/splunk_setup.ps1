# PowerShell Script: splunk_setup.ps1
# Purpose: Create indexes and configure Splunk HTTP Event Collector (HEC) on Windows
# Part of: NeuralWatch — AI Fleet Observatory for Splunk
# Hackathon: Splunk Agentic Ops 2026

# Load .env file
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line -split '=', 2
            if ($parts.Length -eq 2) {
                $key = $parts[0].Trim()
                $value = $parts[1].Trim()
                [System.Environment]::SetEnvironmentVariable($key, $value)
            }
        }
    }
}

$splunkHost = [System.Environment]::GetEnvironmentVariable("SPLUNK_HOST")
if (-not $splunkHost) { $splunkHost = "localhost" }
$splunkPort = [System.Environment]::GetEnvironmentVariable("SPLUNK_PORT")
if (-not $splunkPort) { $splunkPort = "8089" }
$splunkUser = [System.Environment]::GetEnvironmentVariable("SPLUNK_USERNAME")
if (-not $splunkUser) { $splunkUser = "admin" }
$splunkPass = [System.Environment]::GetEnvironmentVariable("SPLUNK_PASSWORD")

# Check if Splunk is installed in the default location
$splunkPath = "C:\Program Files\Splunk\bin\splunk.exe"
if (-not (Test-Path $splunkPath)) {
    Write-Host "[NeuralWatch] splunk.exe not found at $splunkPath. Attempting to use path environment." -ForegroundColor Yellow
    $splunkPath = "splunk"
}

Write-Host "[NeuralWatch] Initializing Splunk Indexes on Windows..." -ForegroundColor Cyan

# Create indexes
& $splunkPath add index neuralwatch_ai_calls -maxDataSize 5000 -frozenTimePeriodInSecs 7776000 -auth "${splunkUser}:${splunkPass}"
& $splunkPath add index neuralwatch_injections -maxDataSize 2000 -frozenTimePeriodInSecs 2592000 -auth "${splunkUser}:${splunkPass}"
& $splunkPath add index neuralwatch_costs -maxDataSize 1000 -frozenTimePeriodInSecs 31536000 -auth "${splunkUser}:${splunkPass}"
& $splunkPath add index neuralwatch_drift -maxDataSize 1000 -frozenTimePeriodInSecs 2592000 -auth "${splunkUser}:${splunkPass}"

Write-Host "[NeuralWatch] Indexes created successfully." -ForegroundColor Green
