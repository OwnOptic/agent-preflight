# The terminal take for the demo video. Everything here is really executed: the output on screen is
# the tool's own, not a transcript. Typing is simulated only so the command is readable on video.
$ErrorActionPreference = 'Continue'
$host.UI.RawUI.WindowTitle = 'PREFLIGHT-DEMO'
$repo = 'C:\Users\Public\agent-preflight'
$py = "$repo\.venv\Scripts\python.exe"
Set-Location $repo
Clear-Host

function Type-Line([string]$text, [int]$ms = 38) {
    Write-Host "PS $((Get-Location).Path)> " -NoNewline -ForegroundColor DarkGray
    foreach ($c in $text.ToCharArray()) {
        Write-Host $c -NoNewline -ForegroundColor White
        Start-Sleep -Milliseconds $ms
    }
    Write-Host ''
}

Start-Sleep -Seconds 3

# 1. The scan, read-only, no traffic, no tokens.
Type-Line 'preflight scan fixtures --policy policy.example.yaml'
# 17 lines, not 26. Long finding lines wrap, and at 26 the console scrolled the CRITICAL block off
# the top: the one piece of output the whole demo exists to show.
& $py -m preflight.cli scan fixtures --policy policy.example.yaml --fail-on none 2>&1 |
    Select-Object -First 17 | Out-Host
Start-Sleep -Seconds 13

# 2. The same composition, as a governance artefact.
Clear-Host
Type-Line 'preflight whatif fixtures --approve callRecordsAgent'
& $py -m preflight.cli whatif fixtures --policy policy.example.yaml --approve callRecordsAgent 2>&1 |
    Select-Object -First 20 | Out-Host
Start-Sleep -Seconds 12

# 3. The gate, on the branch where an approved MCP server rewrote a tool description.
Clear-Host
Write-Host 'PS ...\agent-preflight> ' -NoNewline -ForegroundColor DarkGray
Write-Host 'git switch demo/rug-pull' -ForegroundColor White
# git reports the switch on stderr. Print its own text, but not as a PowerShell ErrorRecord: the
# red CategoryInfo block reads on video as a crash, which is the opposite of what happened.
& git -C $repo switch demo/rug-pull 2>&1 | ForEach-Object { Write-Host $_.ToString() -ForegroundColor Gray }
Start-Sleep -Seconds 2
Type-Line 'preflight scan fixtures --baseline preflight.baseline.json --lock preflight.lock.json --fail-on critical'
& $py -m preflight.cli scan fixtures --policy policy.example.yaml --baseline preflight.baseline.json `
    --lock preflight.lock.json --fail-on critical 2>&1 | Select-Object -First 14 | Out-Host
Write-Host ''
Write-Host "PS ...\agent-preflight> " -NoNewline -ForegroundColor DarkGray
Write-Host 'echo $LASTEXITCODE' -ForegroundColor White
Write-Host '1' -ForegroundColor Red
Write-Host ''
Write-Host '  the build fails: the manifest no longer matches its pin, and the new description' -ForegroundColor DarkYellow
Write-Host '  instructs the model to delete records and hide it.' -ForegroundColor DarkYellow
Start-Sleep -Seconds 12
& git -C $repo switch main 2>&1 | Out-Null
# Hold the window open so the capture is never truncated mid-frame by the console closing.
Start-Sleep -Seconds 8
