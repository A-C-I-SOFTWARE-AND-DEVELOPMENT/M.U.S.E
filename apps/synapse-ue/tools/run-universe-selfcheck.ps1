param(
    [switch]$KeepBinary
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$HeaderRoot = Join-Path $ProjectRoot "Source\SynapseUniverse\Public"
$Source = Join-Path $ProjectRoot "tools\universe-selfcheck\selfcheck.cpp"
$Output = Join-Path $env:TEMP "muse-universe-selfcheck.exe"

if (-not (Test-Path -LiteralPath $Source)) {
    throw "Universe self-check source is missing: $Source"
}

$Cl = Get-Command cl.exe -ErrorAction SilentlyContinue
$Clang = Get-Command clang++.exe -ErrorAction SilentlyContinue
$Gxx = Get-Command g++.exe -ErrorAction SilentlyContinue

if ($Cl) {
    & $Cl.Source /nologo /std:c++17 /W4 /WX /EHsc "/I$HeaderRoot" $Source "/Fe:$Output"
} elseif ($Clang) {
    & $Clang.Source -std=c++17 -Wall -Wextra -Werror -I $HeaderRoot $Source -o $Output
} elseif ($Gxx) {
    & $Gxx.Source -std=c++17 -Wall -Wextra -Werror -I $HeaderRoot $Source -o $Output
} else {
    Write-Error "No C++17 compiler found. Install VS2022 C++ tools, clang++, or g++; the self-check gate remains open."
    exit 2
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Output
$Result = $LASTEXITCODE
if (-not $KeepBinary -and (Test-Path -LiteralPath $Output)) {
    Remove-Item -LiteralPath $Output -Force
}
exit $Result

