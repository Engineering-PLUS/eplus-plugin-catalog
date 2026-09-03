# PreToolUse:Agent hook. Runs on the Windows host under PowerShell.
#
# Two jobs. (1) Log every Agent spawn (subagent_type, requested model) to
# routing.log in plugin data and in the exported session dir, so the routing
# trail is visible in an export. (2) Return permissionDecision "ask" when a
# spawn requests an expensive model (opus or fable), so the expensive tier
# needs an explicit click. The only workers this plugin ships run on Sonnet
# and Haiku; there is no legitimate reason for a worker on Opus or Fable.
#
# Escape hatch: EPLUS_ALLOW_EXPENSIVE_SPAWN=1 skips the gate (logging stays).
# Always exits 0; the decision travels in the JSON body.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $data = $null
    try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $data) { exit 0 }

    $sub = ''; $reqModel = ''
    if ($data.PSObject.Properties['tool_input'] -and $data.tool_input) {
        if ($data.tool_input.PSObject.Properties['subagent_type']) { $sub = [string]$data.tool_input.subagent_type }
        if ($data.tool_input.PSObject.Properties['model'])         { $reqModel = [string]$data.tool_input.model }
    }
    $session = 'unknown-session'
    if ($data.PSObject.Properties['session_id'] -and $data.session_id) { $session = [string]$data.session_id }

    $logLine = "{0:yyyy-MM-ddTHH:mm:ssZ} session={1} event=PreToolUse:Agent subagent_type={2} model={3}" -f [DateTime]::UtcNow, $session, $sub, $reqModel
    if ($env:CLAUDE_PLUGIN_DATA) {
        try {
            if (-not (Test-Path -LiteralPath $env:CLAUDE_PLUGIN_DATA)) { New-Item -ItemType Directory -Path $env:CLAUDE_PLUGIN_DATA -Force | Out-Null }
            Add-Content -Path (Join-Path $env:CLAUDE_PLUGIN_DATA 'routing.log') -Value $logLine -Encoding utf8
        } catch { }
    }
    if ($data.PSObject.Properties['transcript_path'] -and $data.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$data.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $session
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                Add-Content -Path (Join-Path $exportDir 'routing.log') -Value $logLine -Encoding utf8
            }
        } catch { }
    }

    if ($env:EPLUS_ALLOW_EXPENSIVE_SPAWN) { exit 0 }

    $expensive = ($reqModel -match '(?i)opus|fable') -or ($sub -match '(?i)opus|fable')
    if (-not $expensive) { exit 0 }

    $reason = 'This spawn asks for an expensive model (Opus is about 2.5x Sonnet per token, Fable about 5x). ' +
              'The routing workers are haiku-fast for mechanical work and sonnet-standard for everything else; ' +
              'hard reasoning and review stay on the main thread. Approve only if a cheaper worker genuinely ' +
              'cannot do this. (EPLUS_ALLOW_EXPENSIVE_SPAWN=1 disables this gate.)'

    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = $reason
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the gate itself break a tool call.
}

exit 0
