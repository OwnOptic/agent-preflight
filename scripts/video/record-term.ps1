# Capture the real console window. conhost is required: Windows Terminal owns the title bar, so
# gdigrab cannot find a window called PREFLIGHT-DEMO when the script runs under it.
$v = $PSScriptRoot
$out = Join-Path $v 'term.mp4'
if (Test-Path $out) { Remove-Item $out -Force }

Start-Process conhost -ArgumentList @(
    'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $v 'demo-term.ps1')
)
Start-Sleep -Seconds 3

$vf = 'scale=1920:-2:flags=lanczos,pad=1920:1080:0:(1080-ih)/2:color=0x0C0C0C'
& ffmpeg -y -loglevel warning -f gdigrab -framerate 12 -i title=PREFLIGHT-DEMO -t 66 `
    -vf $vf -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p $out

$f = Get-Item $out
"{0}  {1:N1} MB" -f $f.Name, ($f.Length / 1MB)
& ffprobe -v error -show_entries format=duration -of csv=p=0 $out
