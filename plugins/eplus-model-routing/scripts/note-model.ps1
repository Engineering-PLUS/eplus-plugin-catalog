# SessionStart hook. Runs on the Windows host under PowerShell.
#
# Records the session's model, taken from the payload's "model" field, so that
# route-check.ps1 can decide on every prompt whether to inject the routing
# note. Emits nothing; costs one short launch per session open, resume, or
# compaction and zero context tokens.
#
# FIELD RESULT 2026-09-03 (Cowork): the SessionStart payload has NO model
# field (keys: session_id, transcript_path, cwd, hook_event_name, source), so
# this hook records nothing useful on Cowork today and route-check falls back
# to the transcript from the second prompt on, and to the env-check note on the
# first. Kept because it costs one short launch and would start working the
# day the field appears. Store: <TEMP>\eplus-model-routing\<session_id>\ with
# CLAUDE_PLUGIN_DATA as a second copy (both were set on the test seat).
#
# Diagnostics: the payload's top-level key names (never values, except the
# model itself) are written to payload-keys.txt in the same folder so a field
# run shows whether "model" and "transcript_path" are present on this surface.
#
# Always exits 0. Disable with EPLUS_NO_MODEL_ROUTING=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_MODEL_ROUTING) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }
    $model = ''
    if ($data.PSObject.Properties['model'] -and $data.model) { $model = [string]$data.model }
    $keys = ($data.PSObject.Properties | ForEach-Object { $_.Name }) -join ','

    $stores = @()
    if ($env:TEMP) { $stores += (Join-Path (Join-Path $env:TEMP 'eplus-model-routing') $session) }
    if ($env:CLAUDE_PLUGIN_DATA) { $stores += (Join-Path $env:CLAUDE_PLUGIN_DATA $session) }
    foreach ($dir in $stores) {
        try {
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Set-Content -Path (Join-Path $dir 'payload-keys.txt') -Value ("SessionStart keys: $keys") -Encoding ascii
            if ($model) { Set-Content -Path (Join-Path $dir 'model.txt') -Value $model -Encoding ascii }
        } catch { }
    }
} catch {
    # Recording the model is a convenience; never fail a session start over it.
}

exit 0
