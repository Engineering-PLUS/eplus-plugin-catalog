# SubagentStop echo for rfi-researcher -- PowerShell, runs on the Windows host
# (NO python, NO sh). Adapted from punch-subagent/scripts/show-subagent-final.ps1.
# Writes the researcher's FULL final message (the evidence brief) to
# <session project dir>/<session_id>/subagent-final-messages.log, the
# directory the session exporter zips, so the complete brief is readable in
# the export even though the main thread only relays a summary. The entry
# header carries a ~220-char excerpt for quick scanning.
#
# The source script also queued a banner line for a MessageDisplay drain
# hook (displayContent). That drain is deliberately NOT wired here: it fires
# on every message and costs a PowerShell start each time, and this plugin
# keeps hooks to the two that matter. Only the log is written.
#
# Never additionalContext or decision fields (on SubagentStop they would
# continue the turn). PowerShell 5.1-compatible. Never blocks; exit 0.
# Escape hatch: EPLUS_NO_RFI_SUBAGENT_ECHO=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_RFI_SUBAGENT_ECHO) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $msg = $null
    if ($data.PSObject.Properties['last_assistant_message'] -and ($data.last_assistant_message -is [string])) {
        $msg = $data.last_assistant_message
    }
    if (-not $msg -or -not $msg.Trim()) { exit 0 }
    $body = $msg.Trim()

    $agent = 'subagent'
    if ($data.PSObject.Properties['agent_type'] -and $data.agent_type) { $agent = [string]$data.agent_type }
    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    $excerpt = $body -replace '\s+', ' '
    if ($excerpt.Length -gt 220) { $excerpt = $excerpt.Substring(0, 220) + '...' }

    # Full final message -> session project dir (rides along in the export).
    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $session
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                $stamp = '{0:yyyy-MM-ddTHH:mm:ssZ}' -f [DateTime]::UtcNow
                $entry = "==== $stamp $agent ($($body.Length) chars) ====`r`nexcerpt: $excerpt`r`n$body`r`n"
                Add-Content -Path (Join-Path $exportDir 'subagent-final-messages.log') -Value $entry -Encoding utf8
            }
        } catch { }
    }
} catch {
    # Never let the echo become a hook failure.
}

exit 0
