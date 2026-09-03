# PreToolUse:Agent hook. Runs on the Windows host under PowerShell.
#
# Two jobs. (1) Log every Agent spawn (subagent_type, requested model) to
# routing.log under <TEMP>\eplus-model-routing\ (and CLAUDE_PLUGIN_DATA when
# set), so the routing trail is visible on the machine. (2) Return
# permissionDecision "ask" when a spawn requests an expensive model (opus or
# fable), so the expensive tier needs an explicit click. Field test
# 2026-09-03: the approval prompt appears in Cowork under auto permission
# mode; the person at the keyboard decides. The only workers this plugin ships
# run on Sonnet and Haiku.
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
    $stores = @()
    if ($env:TEMP) { $stores += (Join-Path $env:TEMP 'eplus-model-routing') }
    if ($env:CLAUDE_PLUGIN_DATA) { $stores += $env:CLAUDE_PLUGIN_DATA }
    foreach ($dir in $stores) {
        try {
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Add-Content -Path (Join-Path $dir 'routing.log') -Value $logLine -Encoding utf8
        } catch { }
    }

    if ($env:EPLUS_ALLOW_EXPENSIVE_SPAWN) { exit 0 }

    $expensive = ($reqModel -match '(?i)opus|fable') -or ($sub -match '(?i)opus|fable')
    if (-not $expensive) { exit 0 }

    $reason = 'model-routing: this spawn asks for an expensive model (Opus is about 2.5x Sonnet per token, ' +
              'Fable about 5x). The routing workers are haiku-fast for mechanical work and sonnet-standard for ' +
              'everything else; hard reasoning and review stay on the main thread. Approve only if a cheaper ' +
              'worker genuinely cannot do this. (EPLUS_ALLOW_EXPENSIVE_SPAWN=1 disables this gate.)'

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
