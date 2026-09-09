<#
  install.ps1 -- copy this skill into a directory an agent reads. That is the whole installer.

  keel-cloud canon/designs/keel-skill-design.md Sec8.3, decision 13: the personal install is a
  flag on the bare tree, not a fifth packaging, because a second tree of identical bytes is a copy
  to keep honest for no gain. install.sh is that flag on POSIX; this is the same job on Windows,
  where there is no `sh` to run install.sh with (2026-09-09 Windows-clean pass).

    ./install.ps1 -HostName claude   [-Project]   $HOME\.claude\skills\   or  .\.claude\skills\
    ./install.ps1 -HostName copilot  [-Project]   $HOME\.copilot\skills\  or  .\.github\skills\
    ./install.ps1 -HostName agents                $HOME\.agents\skills\  -- more than one agent reads it

    -Dest DIR    put it somewhere else entirely; -HostName is then not needed
    -DryRun      say where it would go and copy nothing
    -Force       replace an existing install without asking

  It copies one directory. It edits no PATH, no PowerShell profile and no configuration file
  (invariant X-6), writes nothing outside the destination, and needs no network.

  The flag is `-HostName`, not `-Host`: PowerShell already has a read-only automatic variable
  named `$Host` (the host program itself), and a parameter binding to it fails outright.

  Runs under both Windows PowerShell 5.1 and PowerShell 7+ (pwsh) -- both ship `$HOME` resolved to
  `%USERPROFILE%`, which is what a founder's `claude`/`copilot` CLI (both Node, both `os.homedir()`
  -based) resolves `~` to on Windows as well, so this lands beside what those hosts already read.
#>

[CmdletBinding()]
param(
    [string]$HostName = "",
    [switch]$Project,
    [string]$Dest = "",
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Help
)

function Write-Err([string]$Message) {
    [Console]::Error.WriteLine($Message)
}

$SkillName = "keel-connect"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $ScriptDir $SkillName

if ($Help) {
    Write-Output "install.ps1 -HostName claude|copilot|agents [-Project] [-Dest DIR] [-DryRun] [-Force]"
    exit 0
}

if (-not (Test-Path -LiteralPath $Src -PathType Container)) {
    Write-Err "install.ps1: no $SkillName/ beside this script -- this distribution is incomplete."
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Src "SKILL.md") -PathType Leaf) `
        -or -not (Test-Path -LiteralPath (Join-Path $Src "scripts\keel_connect_check.py") -PathType Leaf)) {
    Write-Err "install.ps1: $SkillName/ is missing SKILL.md or scripts/ -- this distribution is incomplete."
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Src "keel_runtime\__main__.py") -PathType Leaf)) {
    Write-Err "install.ps1: $SkillName/ carries no keel_runtime/ -- the runtime is supposed to travel inside"
    Write-Err "  the skill, and without it nothing here can start a Keel. Re-download in full."
    exit 1
}

if (-not $Dest) {
    switch ($HostName) {
        "claude" {
            if ($Project) { $Dest = Join-Path (Get-Location).Path ".claude\skills" }
            else { $Dest = Join-Path $HOME ".claude\skills" }
        }
        "copilot" {
            if ($Project) { $Dest = Join-Path (Get-Location).Path ".github\skills" }
            else { $Dest = Join-Path $HOME ".copilot\skills" }
        }
        "agents" {
            # Read by more than one agent -- the answer to "I use both". Not the default, because
            # a founder with one agent is better served by that agent's own directory, which that
            # agent's own tooling can list and remove.
            if ($Project) {
                Write-Err "install.ps1: -HostName agents has no project location; drop -Project."
                exit 2
            }
            $Dest = Join-Path $HOME ".agents\skills"
        }
        "" {
            Write-Err "install.ps1: say where it goes -- -HostName claude|copilot|agents, or -Dest DIR."
            exit 2
        }
        default {
            Write-Err "install.ps1: unknown host $HostName (claude, copilot, agents)."
            exit 2
        }
    }
}

$Target = Join-Path $Dest $SkillName

Write-Output "keel-connect -> $Target"
if ($DryRun) {
    Write-Output "(-DryRun: nothing copied)"
    exit 0
}

if ((Test-Path -LiteralPath $Target) -and -not $Force) {
    Write-Err "There is already something at $Target."
    Write-Err "Re-run with -Force to replace it."
    exit 1
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
if (Test-Path -LiteralPath $Target) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}
Copy-Item -LiteralPath $Src -Destination $Target -Recurse -Force

# Caches from whoever built or ran this copy are nobody else's business.
Get-ChildItem -LiteralPath $Target -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $Target -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Output "Installed."

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) { $PythonCommand = Get-Command py -ErrorAction SilentlyContinue }
if ($PythonCommand) {
    $VersionCheck = & $PythonCommand.Source -c "import sys; print('%d.%d' % sys.version_info[:2]); sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
    $PyVersion = if ($VersionCheck) { ($VersionCheck | Select-Object -First 1) } else { "?" }
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Python $PyVersion -- clears the 3.9 floor. Say `"keel connect`" in your agent."
    } else {
        Write-Output "Python $PyVersion is below the 3.9 Keel needs. Install a newer one once, then say"
        Write-Output "  `"keel connect`" in your agent."
    }
} else {
    Write-Output "No python found. Keel needs Python 3.9 or newer, installed once:"
    Write-Output "  winget install Python.Python.3.12, or the Microsoft Store"
}
