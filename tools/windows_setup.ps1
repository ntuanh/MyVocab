# MyVocab setup for Windows: the one thing to run. It downloads MyVocab (or
# updates it), finds a backup of your words, installs Python if needed, then
# opens the setup page (progress bar and keys) and adds the MyVocab icons.
# MyVocab-Setup.bat runs it. So does this, pasted into Windows+R:
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/ntuanh/MyVocab/main/tools/windows_setup.ps1 | iex"
# MyVocab lives in %LOCALAPPDATA%\MyVocab. Updates keep your words, keys and backups.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ZipUrl = 'https://github.com/ntuanh/MyVocab/archive/refs/heads/main.zip'
$Dir = Join-Path $env:LOCALAPPDATA 'MyVocab'
$Steps = 4

function Show-Step($number, $text) {
    Write-Progress -Activity 'Installing MyVocab' -Status "Step $number of ${Steps}: $text" -PercentComplete ((($number - 1) / $Steps) * 100)
    Write-Host ''
    Write-Host "[$number/$Steps] $text" -ForegroundColor Cyan
}

function Test-MyVocabRunning {
    try {
        Invoke-WebRequest 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-Python {
    # The database package needs Python 3.12 or 3.11 (run.bat looks in the same places).
    if (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')) { return $true }
    foreach ($version in '-3.12', '-3.11') {
        try {
            & py $version -c 'pass' 2>$null
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch { }
    }
    try {
        $fits = & python -c 'import sys; print(sys.version_info[:2] in ((3, 11), (3, 12)))' 2>$null
        return ($fits -eq 'True')
    } catch {
        return $false
    }
}

$Host.UI.RawUI.WindowTitle = 'MyVocab setup'
Write-Host 'MyVocab setup' -ForegroundColor Green
Write-Host "MyVocab will be installed in $Dir"
Write-Host 'Keep this window open. It does every step by itself.'

while (Test-MyVocabRunning) {
    Read-Host 'MyVocab is running. Close its black window first, then press Enter here' | Out-Null
}

# --- 1. Download (or update) MyVocab ---------------------------------------------
$python = Join-Path $Dir '.venv\Scripts\python.exe'
$hasDatabase = Test-Path (Join-Path $Dir '.localdb\PG_VERSION')
if ($hasDatabase -and (Test-Path $python)) {
    Show-Step 1 'Updating MyVocab (your words are saved to a backup first)'
    & $python (Join-Path $Dir 'tools\local_db.py') backup
    if ($LASTEXITCODE -ne 0) { throw 'The backup before the update failed, so nothing was changed.' }
} else {
    Show-Step 1 'Downloading MyVocab'
}
$temp = Join-Path $env:TEMP ('myvocab-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temp | Out-Null
$zip = Join-Path $temp 'myvocab.zip'
$ProgressPreference = 'SilentlyContinue'  # PowerShell's own download bar makes downloads very slow
Invoke-WebRequest $ZipUrl -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $temp
$ProgressPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
# Copies over the old files and leaves .env, .venv, .localdb and backup alone (they are not in the download).
robocopy (Join-Path $temp 'MyVocab-main') $Dir /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'Copying MyVocab into its folder failed.' }
Remove-Item $temp -Recurse -Force
Write-Host 'MyVocab is downloaded.'

# --- 2. Find your words and keys from before -------------------------------------
Show-Step 2 'Looking for your words and keys from before'
$backupDir = Join-Path $Dir 'backup'
$places = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:USERPROFILE 'Downloads'),
    [Environment]::GetFolderPath('MyDocuments')
)
$places += @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2' -ErrorAction SilentlyContinue | ForEach-Object { $_.DeviceID + '\' })  # USB sticks
if ($hasDatabase) {
    Write-Host 'Your words are already in MyVocab on this computer.'
} else {
    $searched = $places + @($backupDir)
    $found = $searched | Where-Object { $_ -and (Test-Path $_) } |
        ForEach-Object { Get-ChildItem -Path $_ -Filter 'myvocab-*.sql' -File -Recurse -Depth 3 -ErrorAction SilentlyContinue } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($found) {
        Write-Host "Found a backup: $($found.FullName)"
        Write-Host "  saved on $($found.LastWriteTime.ToString('d MMMM yyyy')), $([math]::Ceiling($found.Length / 1KB)) KB"
        $answer = Read-Host 'Load these words into MyVocab? Press Enter for yes, or type N for no'
        if ($answer -notmatch '^\s*[nN]') {
            New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
            if ($found.DirectoryName -ne $backupDir) { Copy-Item $found.FullName $backupDir -Force }
            Write-Host 'Your words will be loaded in step 4.'
        } elseif ($found.DirectoryName -eq $backupDir) {
            Rename-Item $found.FullName ($found.Name + '.skipped')  # so it is not loaded
        }
    } else {
        Write-Host 'No backup found, so MyVocab starts with an empty word list.'
        Write-Host 'Moving from another computer? Close this window, put your myvocab-....sql backup'
        Write-Host 'on the Desktop or on a USB stick, and run MyVocab setup again.'
    }
}

# Keys from an old MyVocab folder (a downloaded ZIP, or one on a USB stick), so they need no pasting.
# Only the keys come over: the database setting stays this computer's own.
$envFile = Join-Path $Dir '.env'
if (-not (Test-Path $envFile)) {
    $oldEnv = $places | Where-Object { $_ -and (Test-Path $_) -and ($_ -ne $Dir) } |
        ForEach-Object { Get-ChildItem -Path $_ -Filter 'app.py' -File -Recurse -Depth 2 -ErrorAction SilentlyContinue } |
        ForEach-Object { Join-Path $_.DirectoryName '.env' } |
        Where-Object { (Test-Path $_) -and (Select-String -Path $_ -Pattern '^GEMINI_API_KEY=.+' -Quiet) } |
        Select-Object -First 1
    if ($oldEnv) {
        $keys = Get-Content $oldEnv | Where-Object { $_ -match '^(GEMINI_API_KEY|PEXELS_API_KEY|VIEW_DATA_PASSWORD)=.+' }
        $lines = Get-Content (Join-Path $Dir '.env.example') | ForEach-Object {
            $line = $_
            $kept = $keys | Where-Object { $_.Split('=')[0] + '=' -eq $line } | Select-Object -First 1
            if ($kept) { $kept } else { $line }
        }
        Set-Content -Path $envFile -Value $lines -Encoding UTF8
        Write-Host "Your keys are copied from $(Split-Path $oldEnv -Parent)"
    }
}

# --- 3. Python -------------------------------------------------------------------
Show-Step 3 'Checking Python 3.12'
if (Test-Python) {
    Write-Host 'Python is ready.'
} else {
    & (Join-Path $Dir 'tools\get_python.ps1')
}

# --- 4. Set up and start ------------------------------------------------------------
Show-Step 4 'Setting up MyVocab: the setup page opens in your browser'
Write-Progress -Activity 'Installing MyVocab' -Completed
Set-Location $Dir
& (Join-Path $Dir 'run.bat') --setup
