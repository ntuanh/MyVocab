# Installs Python 3.12 for this Windows user, with progress bars and no
# questions. It needs no administrator rights. run.bat runs this when it finds
# no Python 3.12 or 3.11. The database package has no build for newer Pythons yet.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$version = '3.12.10'
$url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
$file = Join-Path $env:TEMP "python-$version-amd64.exe"

Write-Host "[MyVocab] Downloading Python $version (about 25 MB) ..."
try {
    Start-BitsTransfer -Source $url -Destination $file -DisplayName "Downloading Python $version" -Description 'MyVocab needs it'
} catch {
    Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing
}

# Only run an installer that the Python Software Foundation really signed.
$signature = Get-AuthenticodeSignature $file
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
    Remove-Item $file -ErrorAction SilentlyContinue
    throw 'The downloaded file is not signed by the Python Software Foundation, so it was not run.'
}

Write-Host '[MyVocab] Installing Python: a small window shows its progress ...'
$arguments = '/passive', 'InstallAllUsers=0', 'InstallLauncherAllUsers=0', 'Include_launcher=1',
             'PrependPath=1', 'Include_test=0', 'Include_doc=0', 'Shortcuts=0'
$installer = Start-Process -FilePath $file -ArgumentList $arguments -Wait -PassThru
Remove-Item $file -ErrorAction SilentlyContinue
if ($installer.ExitCode -ne 0) {
    throw "The Python installer stopped with code $($installer.ExitCode)."
}
Write-Host '[MyVocab] Python is installed.'
