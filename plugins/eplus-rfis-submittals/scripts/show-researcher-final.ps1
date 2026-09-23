# SubagentStop echo for rfi-researcher -- PowerShell, runs on the Windows host
# (NO python, NO sh). Adapted from punch-subagent/scripts/show-subagent-final.ps1.
# Writes the researcher's FULL final report (the evidence brief) to
# <session project dir>/<session_id>/subagent-final-messages.log, the
# directory the session exporter zips, so the complete brief is readable in
# the export even though the main thread only relays a summary. The entry
# header carries a ~220-char excerpt for quick scanning.
#
# Where the brief comes from (field result 2026-09-23, export 1790148676704):
# Cowork subagents deliver their report through a SubagentHandback tool call,
# SubagentHandback({message: <report>}), and then usually write a short stub
# such as "Report delivered.". The payload's last_assistant_message is that
# stub, not the brief. So the hook reads the subagent's own transcript and
# takes the message of its LAST SubagentHandback call:
#   1. agent_transcript_path from the payload, when present and on disk;
#   2. else <dirname(transcript_path)>\<session_id>\subagents\agent-<agent_id>.jsonl,
#      the layout the export shows;
#   3. else last_assistant_message, as before.
# The header names the source used (handback or last_message) so the next
# export shows which path worked on the seat.
#
# The source script also queued a banner line for a MessageDisplay drain
# hook (displayContent). That drain is deliberately NOT wired here: it fires
# on every message and costs a PowerShell start each time, and this plugin
# keeps hooks to the two that matter. Only the log is written.
#
# stdin is read as UTF-8 bytes (the hook console code page is IBM437 on the
# seats, which mangles non-ASCII text such as em-dashes in a brief) and the
# log is appended as UTF-8 without a BOM.
#
# Never additionalContext or decision fields (on SubagentStop they would
# continue the turn). PowerShell 5.1-compatible. Never blocks; exit 0.
# Escape hatch: EPLUS_NO_RFI_SUBAGENT_ECHO=1.

$ErrorActionPreference = 'SilentlyContinue'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Get-HandbackMessage([string] $path) {
    # Last SubagentHandback({message}) in a subagent transcript, or $null.
    if (-not $path -or -not (Test-Path -LiteralPath $path)) { return $null }
    $found = $null
    try {
        $fs = New-Object System.IO.FileStream($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        $sr = New-Object System.IO.StreamReader($fs, $Utf8)
        while ($null -ne ($line = $sr.ReadLine())) {
            if ($line -notmatch '"name"\s*:\s*"SubagentHandback"') { continue }
            try { $o = ConvertFrom-Json -InputObject $line -ErrorAction Stop } catch { continue }
            $content = $null
            if ($o.PSObject.Properties['message'] -and $o.message -and $o.message.PSObject.Properties['content']) { $content = $o.message.content }
            foreach ($c in @($content)) {
                if ($null -eq $c) { continue }
                if ($c.PSObject.Properties['type'] -and $c.type -eq 'tool_use' -and $c.PSObject.Properties['name'] -and $c.name -eq 'SubagentHandback') {
                    if ($c.PSObject.Properties['input'] -and $c.input -and $c.input.PSObject.Properties['message'] -and ($c.input.message -is [string]) -and $c.input.message.Trim()) {
                        $found = [string]$c.input.message
                    }
                }
            }
        }
        $sr.Close()
    } catch { }
    return $found
}

try {
    $raw = ''
    try {
        $in = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $Utf8)
        $raw = $in.ReadToEnd()
    } catch { $raw = '' }
    if ($env:EPLUS_NO_RFI_SUBAGENT_ECHO) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }
    $agent = 'subagent'
    if ($data.PSObject.Properties['agent_type'] -and $data.agent_type) { $agent = [string]$data.agent_type }
    $tdir = $null
    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try { $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent } catch { }
    }

    # --- 1/2: the handback message from the subagent's transcript ---------------
    $candidates = @()
    if ($data.PSObject.Properties['agent_transcript_path'] -and $data.agent_transcript_path) { $candidates += [string]$data.agent_transcript_path }
    if ($tdir -and $data.PSObject.Properties['agent_id'] -and $data.agent_id) {
        $aid = ([string]$data.agent_id) -replace '^agent-', ''
        $candidates += (Join-Path (Join-Path (Join-Path $tdir $session) 'subagents') ('agent-' + $aid + '.jsonl'))
    }
    $body = $null; $source = 'last_message'
    foreach ($p in $candidates) {
        $hb = Get-HandbackMessage $p
        if ($hb) { $body = $hb.Trim(); $source = 'handback'; break }
    }

    # --- 3: fall back to the last assistant message -----------------------------
    if (-not $body) {
        if ($data.PSObject.Properties['last_assistant_message'] -and ($data.last_assistant_message -is [string])) {
            $body = ([string]$data.last_assistant_message).Trim()
        }
    }
    if (-not $body) { exit 0 }

    $excerpt = $body -replace '\s+', ' '
    if ($excerpt.Length -gt 220) { $excerpt = $excerpt.Substring(0, 220) + '...' }

    # Full final report -> session project dir (rides along in the export).
    if ($tdir) {
        try {
            $exportDir = Join-Path $tdir $session
            if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
            $stamp = '{0:yyyy-MM-ddTHH:mm:ssZ}' -f [DateTime]::UtcNow
            $entry = "==== $stamp $agent ($($body.Length) chars) source=$source ====`r`nexcerpt: $excerpt`r`n$body`r`n"
            [IO.File]::AppendAllText((Join-Path $exportDir 'subagent-final-messages.log'), $entry, $Utf8)
        } catch { }
    }
} catch {
    # Never let the echo become a hook failure.
}

exit 0
