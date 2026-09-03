# UserPromptSubmit hook. Runs on the Windows host under PowerShell.
#
# Decides whether this session's main thread is on an expensive tier (Opus or
# Fable) and, only then, injects a short routing note as additionalContext.
# On Sonnet or Haiku it emits nothing. The note always tells the model to
# confirm against the "Model:" line in its own env block, which is the value
# the model can see directly.
#
# Detection, in order:
#   1. model.txt written by note-model.ps1 from the SessionStart payload, in
#      <TEMP>\eplus-model-routing\<session_id>\ (or CLAUDE_PLUGIN_DATA).
#      FIELD RESULT 2026-09-03 (Cowork, two exports): the SessionStart payload
#      carries session_id, transcript_path, cwd, hook_event_name, source and
#      NO model field, so this step never fires on Cowork today. Kept in case
#      a later build adds the field.
#   2. The last assistant message's model field in the transcript tail. The
#      payload does name transcript_path, but on the FIRST prompt the transcript
#      holds no assistant turn yet, so this works from the second prompt on.
#   3. Unknown (always the first prompt on Cowork): inject the env-check
#      variant and let the model read its own Model: line. Verified: the model
#      reads it correctly.
#
# First injection per session is the full digest; later prompts get a one-line
# reminder. The payload's key names are appended to payload-keys.txt as a
# diagnostic. Context-only; never a decision field; always exits 0.
# Disable with EPLUS_NO_MODEL_ROUTING=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_MODEL_ROUTING) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { }

    $session = 'unknown-session'
    $transcript = $null
    $keys = ''
    if ($null -ne $data) {
        if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }
        if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) { $transcript = [string]$data.transcript_path }
        $keys = ($data.PSObject.Properties | ForEach-Object { $_.Name }) -join ','
    }

    # Per-session store: TEMP first (always present on the host), plugin data second.
    $dir = $null
    $candidates = @()
    if ($env:TEMP) { $candidates += (Join-Path (Join-Path $env:TEMP 'eplus-model-routing') $session) }
    if ($env:CLAUDE_PLUGIN_DATA) { $candidates += (Join-Path $env:CLAUDE_PLUGIN_DATA $session) }
    foreach ($c in $candidates) {
        try {
            if (-not (Test-Path -LiteralPath $c)) { New-Item -ItemType Directory -Path $c -Force | Out-Null }
            if (-not $dir) { $dir = $c }
        } catch { }
    }
    if ($dir -and $keys) { try { Add-Content -Path (Join-Path $dir 'payload-keys.txt') -Value ("UserPromptSubmit keys: $keys") -Encoding ascii } catch { } }

    # --- 1. model recorded at SessionStart (any candidate store) -----------
    $model = ''
    foreach ($c in $candidates) {
        $mf = Join-Path $c 'model.txt'
        if (-not $model -and (Test-Path -LiteralPath $mf)) { $model = ([string](Get-Content -LiteralPath $mf -Raw)).Trim() }
    }

    # --- 2. transcript tail -------------------------------------------------
    if (-not $model -and $transcript -and (Test-Path -LiteralPath $transcript)) {
        try {
            $fs = [IO.File]::Open($transcript, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            $len = $fs.Length
            $take = [Math]::Min($len, 262144)
            if ($take -gt 0) {
                [void]$fs.Seek(-$take, [IO.SeekOrigin]::End)
                $buf = New-Object byte[] $take
                [void]$fs.Read($buf, 0, $take)
                $text = [Text.Encoding]::UTF8.GetString($buf)
                $found = [regex]::Matches($text, '"model"\s*:\s*"(claude-[^"]+)"')
                if ($found.Count -gt 0) { $model = $found[$found.Count - 1].Groups[1].Value }
            }
            $fs.Close()
        } catch { }
    }

    $tier = 'unknown'
    if ($model -match '(?i)claude-(opus|fable)') { $tier = 'expensive' }
    elseif ($model -match '(?i)claude-(sonnet|haiku)') { $tier = 'cheap' }

    if ($tier -eq 'cheap') { exit 0 }

    # --- first-time vs reminder ----------------------------------------------
    $first = $true
    if ($dir) {
        $marker = Join-Path $dir 'routed.flag'
        if (Test-Path -LiteralPath $marker) { $first = $false } else { try { Set-Content -Path $marker -Value $model -Encoding ascii } catch { } }
    }

    if ($tier -eq 'expensive') {
        if ($first) {
            $ctx = "[model-routing] This session runs on $model, an expensive tier (confirm on the Model: line " +
                   'of your env block). Before any work beyond a one-line answer, read the model-routing skill ' +
                   'and follow it: hand mechanical work to haiku-fast, and research, file reading, drafting, ' +
                   'coding, and every loop over files or tools to sonnet-standard. Keep this thread to decisions, ' +
                   'user questions, review of client-facing output, and the final answer. Every tool call here ' +
                   're-reads the whole context at this tier''s price, so batch commands and never read large ' +
                   'files in this thread.'
        } else {
            $ctx = "[model-routing] Still on $model. Delegate: haiku-fast for mechanical work, sonnet-standard for the rest; keep this thread to decisions."
        }
    } else {
        if ($first) {
            $ctx = '[model-routing] Check the "Model:" line in your env block. If it names Opus or Fable, read the ' +
                   'model-routing skill before doing any work: hand mechanical work to haiku-fast and the rest to ' +
                   'sonnet-standard, and keep this thread to decisions and the final answer. If it names Sonnet ' +
                   'or Haiku, ignore this note.'
        } else {
            $ctx = '[model-routing] If your env Model line names Opus or Fable, delegate to haiku-fast and sonnet-standard.'
        }
    }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'UserPromptSubmit'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # A routing reminder is never worth failing a prompt over.
}

exit 0
