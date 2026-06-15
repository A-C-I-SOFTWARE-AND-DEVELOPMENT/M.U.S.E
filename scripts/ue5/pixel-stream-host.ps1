# UE5 Pixel Streaming — host launcher (Windows)
# Owner-gated: set MUSE_UE5_ALLOW_SPAWN=1 before running.
# See docs/plans/2026-06-15-nero-fleet-architecture.md §4

param(
    [string]$ProjectPath = "",
    [string]$SignalingPort = "8888",
    [string]$StreamPort = "8888",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $env:MUSE_UE5_ALLOW_SPAWN) {
    Write-Host "BLOCKED: MUSE_UE5_ALLOW_SPAWN is not set."
    Write-Host "Dry-run command that would execute:"
    Write-Host "  `$env:MUSE_UE5_ALLOW_SPAWN=1; .\scripts\ue5\pixel-stream-host.ps1 -ProjectPath <path>"
    exit 2
}

# Common UE5 install locations — adjust for your machine.
$UeCandidates = @(
    "${env:ProgramFiles}\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe",
    "${env:ProgramFiles}\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor.exe"
)

$UeEditor = $UeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $UeEditor) {
    Write-Error "UnrealEditor.exe not found. Install UE5.6+ or pass -ProjectPath to a packaged build."
}

if (-not $ProjectPath) {
    Write-Error "Pass -ProjectPath to your .uproject (e.g. apps/synapse-ue/Synapse.uproject when present)."
}

$Args = @(
    "`"$ProjectPath`"",
    "-game",
    "-PixelStreamingIP=0.0.0.0",
    "-PixelStreamingPort=$StreamPort",
    "-RenderOffScreen",
    "-ForceRes",
    "-ResX=1920",
    "-ResY=1080"
)

$Cmd = "& `"$UeEditor`" $($Args -join ' ')"
Write-Host "Launching Pixel Streaming host..."
Write-Host $Cmd

if ($DryRun) {
    exit 0
}

Invoke-Expression $Cmd
