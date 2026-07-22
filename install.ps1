#
# BBS Browser 1985 -- Windows installer.
#
#   iwr -useb https://raw.githubusercontent.com/tesenwein/bbs-browser/main/install.ps1 | iex
#
# Fetches the latest release wheel from GitHub and installs the 'bbs' command
# -- preferably via pipx, otherwise into its own venv under
# %LOCALAPPDATA%\bbs-browser. Both paths bring the AI SDK along ([ai] extra
# resp. 'pipx inject anthropic'), just like 'make install' and the browser's
# built-in 'up' command.
#
# No git and no checkout needed -- just Python 3.9+ and internet access.

$ErrorActionPreference = "Stop"
# The progress bar makes Invoke-WebRequest an order of magnitude slower on
# Windows PowerShell 5.1 -- switch it off for the wheel download.
$ProgressPreference = "SilentlyContinue"
# Older Windows installs still negotiate TLS 1.0 by default, which GitHub refuses.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo   = if ($env:BBS_REPO)   { $env:BBS_REPO }   else { "tesenwein/bbs-browser" }
$Prefix = if ($env:BBS_PREFIX) { $env:BBS_PREFIX } else { Join-Path $env:LOCALAPPDATA "bbs-browser" }
$Api    = "https://api.github.com/repos/$Repo/releases/latest"

function Say($msg)  { Write-Host $msg }
function Warn($msg) { Write-Warning $msg }

# 'throw' rather than 'exit': under 'iwr | iex' the script shares the caller's
# scope, so an 'exit' would close the user's shell.
function Die($msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    throw "BBS Browser installation aborted."
}

# $ErrorActionPreference does not apply to native executables, so every external
# command needs its exit code checked explicitly.
function Assert-ExitCode($what) {
    if ($LASTEXITCODE -ne 0) { Die "$what failed (exit code $LASTEXITCODE)." }
}

Say "CARRIER 2400 -- BBS Browser 1985 Installer"

# --- Prerequisites -----------------------------------------------------
# Returns @{ Exe = <name>; Args = <array> } for the first usable Python 3.9+.
function Find-Python {
    foreach ($cand in @("python", "python3", "py")) {
        $cmd = Get-Command $cand -ErrorAction SilentlyContinue
        # Windows ships a Store stub under this name that just opens the
        # Store instead of running Python when invoked -- ignore it.
        if (-not $cmd -or $cmd.Source -like "*WindowsApps*") { continue }
        # The 'py' launcher needs a leading '-3' to pick Python 3.
        $extra = if ($cand -eq "py") { @("-3") } else { @() }
        try {
            & $cand @extra -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>&1 | Out-Null
        } catch { continue }
        if ($LASTEXITCODE -eq 0) { return @{ Exe = $cand; Args = $extra } }
    }
    return $null
}

# Python missing: install it via winget (built into Windows since 10 1809+).
function Install-Python {
    Say "Python not found -- attempting installation via winget ..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Die "winget not found -- please install Python 3.9+ manually from https://python.org (check 'Add python.exe to PATH')."
    }
    # winget package ids are version-pinned; try newest first and fall back so
    # the script keeps working as releases come and go.
    foreach ($id in @("Python.Python.3.13", "Python.Python.3.12", "Python.Python.3.11")) {
        Say "Trying winget package $id ..."
        winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            # winget only updates PATH for new processes -- pull it into this session too.
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            return
        }
    }
    Die "Python installation via winget failed -- please install manually from https://python.org."
}

$Py = Find-Python
if (-not $Py) {
    Install-Python
    $Py = Find-Python
    if (-not $Py) { Die "Python installation failed -- open a new terminal and rerun the script, or install Python manually." }
}

# --- Determine latest release -------------------------------------------
Say "Querying latest version from GitHub ..."
try {
    $Release = Invoke-RestMethod -UseBasicParsing -Uri $Api
} catch {
    Die "GitHub releases API unreachable."
}

$Tag = $Release.tag_name
if (-not $Tag) { Die "no release found (repo $Repo)." }

$Asset = $Release.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
if (-not $Asset) { Die "release $Tag contains no wheel." }

$WheelUrl  = $Asset.browser_download_url
$WheelName = $Asset.name
Say "Latest version: $Tag"

# --- Download wheel -------------------------------------------------------
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bbs-install-" + [System.Guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $TmpDir | Out-Null
$WheelPath = Join-Path $TmpDir $WheelName

try {
    Say "Downloading $WheelName ..."
    Invoke-WebRequest -UseBasicParsing -Uri $WheelUrl -OutFile $WheelPath

    # --- Install: pipx preferred, otherwise own venv ------------------
    # Chromium for JS rendering. The pip package only ships the bindings --
    # the browser binary (~150 MB) has to be fetched separately. If that
    # fails, the browser still runs, just without JS.
    # Important: trigger the download with EXACTLY the Python that playwright
    # was installed into -- the browser builds are tied to the playwright
    # version, a stray 'playwright' would otherwise fetch the wrong build.
    function Install-Chromium($pythonExe) {
        Say "Downloading Chromium for JS rendering (~150 MB) ..."
        & $pythonExe -m playwright install chromium
        if ($LASTEXITCODE -ne 0) {
            Warn "Note: Chromium download failed -- pages with JS will stay blank until 'playwright install chromium' runs."
        }
    }

    # pipx moved its venv root between versions and honours PIPX_HOME -- ask
    # pipx itself rather than guessing, and fall back to the known layouts.
    function Get-PipxVenvPython {
        $venvs = $null
        try {
            $venvs = (pipx environment --value PIPX_LOCAL_VENVS 2>$null) | Select-Object -First 1
            if ($LASTEXITCODE -ne 0) { $venvs = $null }
        } catch { $venvs = $null }

        $candidates = @()
        if ($venvs) { $candidates += (Join-Path $venvs "bbs-browser\Scripts\python.exe") }
        if ($env:PIPX_HOME) { $candidates += (Join-Path $env:PIPX_HOME "venvs\bbs-browser\Scripts\python.exe") }
        $candidates += (Join-Path $env:USERPROFILE "pipx\venvs\bbs-browser\Scripts\python.exe")
        $candidates += (Join-Path $env:USERPROFILE ".local\pipx\venvs\bbs-browser\Scripts\python.exe")

        foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
        return $null
    }

    $Bin = $null
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        Say "Installing with pipx (incl. AI SDK) ..."
        pipx install --force $WheelPath
        Assert-ExitCode "pipx install"

        pipx inject --force bbs-browser anthropic openai pyfiglet rich
        if ($LASTEXITCODE -ne 0) {
            Warn "Note: 'anthropic'/'openai'/'pyfiglet'/'rich' not injected -- AI SysOp stays off until 'pipx inject bbs-browser anthropic openai pyfiglet rich' runs."
        }

        $PipxPy = Get-PipxVenvPython
        if ($PipxPy) {
            Install-Chromium $PipxPy
        } else {
            Warn "Note: pipx venv not found -- JS rendering only after 'playwright install chromium'."
        }

        # pipx's bin directory is not necessarily on PATH yet.
        try { pipx ensurepath 2>&1 | Out-Null } catch { }

        $Bin = (Get-Command bbs -ErrorAction SilentlyContinue).Source
        if (-not $Bin) {
            Warn "Note: 'bbs' not on PATH in this session -- open a new terminal (pipx ensurepath has been run)."
        }
    } else {
        Say "pipx not found -- installing to $Prefix ..."
        # '--clear' rather than deleting $Prefix: BBS_PREFIX is user supplied and
        # a recursive delete of whatever it points at would be unforgiving.
        $PyExe = $Py.Exe; $PyArgs = $Py.Args   # splatting needs a plain variable
        & $PyExe @PyArgs -m venv --clear $Prefix
        Assert-ExitCode "python -m venv"

        $VenvPy = Join-Path $Prefix "Scripts\python.exe"
        if (-not (Test-Path $VenvPy)) { Die "venv created but $VenvPy is missing." }

        # Drive pip through the venv interpreter -- works even when pip.exe was
        # not generated, and guarantees the right environment.
        & $VenvPy -m pip install -q --upgrade pip
        Assert-ExitCode "pip upgrade"

        # Extras can be pulled straight from the wheel path -- the AI SDK comes along.
        & $VenvPy -m pip install -q "$WheelPath[ai]"
        Assert-ExitCode "pip install"

        Install-Chromium $VenvPy
        $Bin = Join-Path $Prefix "Scripts\bbs.exe"

        $ScriptsDir = Join-Path $Prefix "Scripts"
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        # Compare entry by entry: '-like' would treat brackets in the path as wildcards.
        $Entries = @()
        if ($UserPath) { $Entries = @($UserPath.Split(';') | Where-Object { $_ }) }
        if ($Entries -notcontains $ScriptsDir) {
            [Environment]::SetEnvironmentVariable("Path", (($Entries + $ScriptsDir) -join ';'), "User")
            $env:Path = "$env:Path;$ScriptsDir"
            Warn "Note: $ScriptsDir was added to your user PATH -- open a new terminal so 'bbs' is found everywhere."
        }
    }

    Say ""
    Say "CONNECT -- 'bbs' installed$(if ($Bin) { " ($Bin)" })."
    Say "Get started:  bbs            (main menu)"
    Say "              bbs heise.de   (dial a page directly)"
} finally {
    Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
}
