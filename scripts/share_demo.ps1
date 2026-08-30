<#
.SYNOPSIS
    Start a Cloudflare tunnel and the frontend wired to it, in one step.

.DESCRIPTION
    Serving the demo publicly needs the tunnel's hostname passed to Vite, and
    the hostname is not known until the tunnel is already running. Doing that by
    hand means starting the tunnel, reading a URL out of its output, stopping
    the frontend and starting it again -- three steps to get wrong while people
    are watching.

    This starts the tunnel, waits for its URL, and launches Vite already
    configured for it.

    Tunnelling port 5173 rather than 8000 is deliberate: Vite proxies /api to
    the backend, so a single tunnel serves the whole app and there is no CORS
    to configure.

.PARAMETER Port
    The frontend port. Defaults to 5173.

.EXAMPLE
    # Terminal 1
    cd backend; ..\.venv311\Scripts\python.exe -m uvicorn app.main:app --port 8000

    # Terminal 2
    .\scripts\share_demo.ps1
#>
[CmdletBinding()]
param(
    [ValidateSet('ngrok', 'cloudflare')]
    [string]$Provider = 'ngrok',
    [string]$NgrokDomain = 'richness-feminine-auction.ngrok-free.dev',
    [int]$Port = 5173,
    [int]$BackendPort = 8000,
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Write-Warn($message) { Write-Host "!!  $message" -ForegroundColor Yellow }

# --- Preconditions --------------------------------------------------------
$binary = if ($Provider -eq 'ngrok') { 'ngrok' } else { 'cloudflared' }
if (-not (Get-Command $binary -ErrorAction SilentlyContinue)) {
    Write-Warn "$binary is not installed, or your shell has not picked it up yet."
    if ($Provider -eq 'ngrok') {
        Write-Host "    winget install --id Ngrok.Ngrok"
    } else {
        Write-Host "    winget install --id Cloudflare.cloudflared"
    }
    Write-Host ""
    Write-Host "    The installer edits PATH, so open a NEW terminal afterwards."
    exit 1
}

# A tunnel to a dead backend produces a page that loads and then fails every
# request, which reads as a broken app rather than a missing service.
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/v1/health" `
        -TimeoutSec 3 -UseBasicParsing
    Write-Step "Backend is up on :$BackendPort"
} catch {
    Write-Warn "No backend answering on :$BackendPort. Start it first, in another terminal:"
    Write-Host "    cd backend; ..\.venv311\Scripts\python.exe -m uvicorn app.main:app --port $BackendPort"
    Write-Host ""
    $reply = Read-Host "Continue anyway? [y/N]"
    if ($reply -ne 'y') { exit 1 }
}

# Vite reads VITE_ALLOWED_HOSTS once, at startup, so an already-running dev
# server cannot be told about the tunnel hostname -- it has to be restarted.
# Left alone, npm would fail with "Port 5173 is already in use", which does not
# explain what to do about it.
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($existing) {
    $owner = Get-Process -Id $existing.OwningProcess -ErrorAction SilentlyContinue
    Write-Warn "Something is already listening on :$Port (PID $($existing.OwningProcess)$(if ($owner) { ", $($owner.ProcessName)" }))."
    Write-Host "    Vite reads VITE_ALLOWED_HOSTS only at startup, so it has to be"
    Write-Host "    restarted for the tunnel hostname to be accepted."
    Write-Host ""
    $reply = Read-Host "Stop it and continue? [y/N]"
    if ($reply -ne 'y') {
        Write-Host "Left it running. Stop it yourself, then re-run this script."
        exit 1
    }
    Stop-Process -Id $existing.OwningProcess -Force
    Start-Sleep -Seconds 2
    Write-Step "Stopped the process on :$Port"
}

# --- Tunnel ---------------------------------------------------------------
$logFile = Join-Path ([System.IO.Path]::GetTempPath()) "bionano-tunnel-$PID.log"

if ($Provider -eq 'ngrok') {
    # The reserved domain is fixed, so the URL is known before the tunnel is
    # even up -- no log parsing, and nothing to reconfigure between runs.
    # The reserved-domain flag was renamed: --domain on ngrok 3.x up to ~3.18,
    # --url on newer builds. winget currently ships 3.3.1, so pick by version
    # rather than assuming -- the wrong one fails with 'unknown flag'.
    $ngrokVersion = (& ngrok version) -replace '[^0-9.]', ''
    $useUrlFlag = $false
    try {
        $parsed = [version]($ngrokVersion -split '\s+' | Select-Object -First 1)
        $useUrlFlag = $parsed -ge [version]'3.19.0'
    } catch { $useUrlFlag = $false }
    $domainFlag = if ($useUrlFlag) { "--url=$NgrokDomain" } else { "--domain=$NgrokDomain" }

    Write-Step "Starting ngrok $ngrokVersion on $NgrokDomain ($domainFlag)..."
    $tunnel = Start-Process -FilePath 'ngrok' `
        -ArgumentList @('http', "$Port", $domainFlag, '--log', 'stdout') `
        -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
        -NoNewWindow -PassThru
    $publicUrl = "https://$NgrokDomain"
    $hostname = $NgrokDomain

    # Give it a moment to fail loudly on a bad authtoken or a domain that is
    # not on this account, rather than handing over a URL that will not answer.
    Start-Sleep -Seconds 4
    if ($tunnel.HasExited) {
        Write-Warn "ngrok exited immediately. Its output:"
        foreach ($f in @($logFile, "$logFile.err")) {
            if (Test-Path $f) { Get-Content $f -Tail 15 }
        }
        Write-Host ""
        Write-Host "    Common causes: no authtoken set (ngrok config add-authtoken ...),"
        Write-Host "    or the domain is not reserved on this account."
        exit 1
    }
} else {
    Write-Step "Starting the Cloudflare tunnel..."
    $tunnel = Start-Process -FilePath 'cloudflared' `
        -ArgumentList @('tunnel', '--no-autoupdate', '--url', "http://localhost:$Port") `
        -RedirectStandardError $logFile -RedirectStandardOutput "$logFile.out" `
        -NoNewWindow -PassThru

    # cloudflared assigns a random hostname and prints it to stderr a second or
    # two after starting, so poll rather than assuming it is ready.
    $publicUrl = $null
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline -and -not $publicUrl) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $logFile) {
            $match = Select-String -Path $logFile -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' `
                -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($match) { $publicUrl = $match.Matches[0].Value }
        }
    }

    if (-not $publicUrl) {
        Write-Warn "The tunnel did not report a URL within $TimeoutSeconds seconds. Its log:"
        if (Test-Path $logFile) { Get-Content $logFile -Tail 20 }
        if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
        exit 1
    }
    $hostname = ([System.Uri]$publicUrl).Host
}

Write-Host ""
Write-Host "  Public URL:  $publicUrl" -ForegroundColor Green
Write-Host ""
Write-Host "  This is your laptop, reachable from anywhere. It stops when you"
Write-Host "  close this window. The URL is unguessable but NOT authenticated:"
Write-Host "  anyone holding it can start simulations on this machine."
if ($Provider -eq 'ngrok') {
    Write-Host ""
    Write-Host "  First-time visitors see an ngrok interstitial before the app."
    Write-Host "  One click through it; that is the free plan, not a fault."
}
Write-Host ""

# --- Frontend -------------------------------------------------------------
# Vite rejects a Host header it does not recognise, so the hostname has to be
# allowed before it starts -- which is the whole reason this script exists.
$env:VITE_ALLOWED_HOSTS = $hostname
Write-Step "Starting Vite with VITE_ALLOWED_HOSTS=$hostname"
Write-Host ""

try {
    Push-Location (Join-Path $repo 'frontend')
    npm run dev
} finally {
    Pop-Location
    Write-Step "Stopping the tunnel"
    if ($tunnel -and -not $tunnel.HasExited) {
        Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $logFile, "$logFile.out", "$logFile.err" -ErrorAction SilentlyContinue
}
