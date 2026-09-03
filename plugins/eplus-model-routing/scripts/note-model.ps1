# SessionStart hook. Runs on the Windows host under PowerShell.
#
# The SessionStart payload carries the session's model (field "model", for
# example claude-opus-5[1m] or claude-fable-5-1). This script records it to
# <CLAUDE_PLUGIN_DATA>/<session_id>/model.txt and emits NOTHING, so it costs
# one short process launch per session open and zero context tokens.
# route-check.ps1 reads that file on every prompt to decide whether to inject
# the routing note, which lets a Sonnet or Haiku session stay completely silent.
#
# Fires on startup, resume, and after compaction; each rewrite is harmless.
# Always exits 0. Disable with EPLUS_NO_MODEL_ROUTING=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_MODEL_ROUTING) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $model = ''
    if ($data.PSObject.Properties['model'] -and $data.model) { $model = [string]$data.model }
    if (-not $model) { exit 0 }

    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    if ($env:CLAUDE_PLUGIN_DATA) {
        $dir = Join-Path $env:CLAUDE_PLUGIN_DATA $session
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Set-Content -Path (Join-Path $dir 'model.txt') -Value $model -Encoding ascii
    }
} catch {
    # Recording the model is a convenience; never fail a session start over it.
}

exit 0
