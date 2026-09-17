# PostToolUse hook on mcp__workspace__web_fetch. Runs on the Windows host under
# PowerShell. PowerShell 5.1-compatible, ASCII only, no BOM.
#
# Why (0.4.0): PostToolUseFailure is the primary egress wiring and stays. But on
# Desktop build 1.52386.3 (export of 2026-09-15) a fetch refused by the network
# allowlist came back as a *successful* tool result carrying the egress text, so
# the failure event never fired (57 fetches, zero failure hooks in telemetry) and
# the model filed nothing. PostToolUse fires on success, PostToolUseFailure on
# failure, so the two never double up on one call and no dedupe is needed.
#
# What it does: reads tool_response (the serialized result the model sees) and,
# only when it matches the egress signature from egress-common.ps1, emits the same
# egress context the failure hook would have. Silent on every ordinary fetch, and
# silent when the payload does not parse or carries no tool_response: the URL in
# tool_input must never be able to trigger the nudge.
#
# Always exits 0. Disable with EPLUS_NO_EGRESS_NUDGE=1 (EPLUS_NO_ERROR_NUDGE=1 also
# silences it). Cost: one PowerShell spawn per web_fetch call.

$ErrorActionPreference = 'SilentlyContinue'

try {
    . (Join-Path $PSScriptRoot 'egress-common.ps1')
    $raw = Read-HookInput
    if ($env:EPLUS_NO_ERROR_NUDGE -or $env:EPLUS_NO_EGRESS_NUDGE) { exit 0 }

    $payload = $null
    try { $payload = ConvertFrom-Json -InputObject $raw -ErrorAction Stop } catch { exit 0 }
    if ($null -eq $payload -or -not $payload.PSObject.Properties['tool_response']) { exit 0 }

    $resp = ConvertTo-Json -InputObject $payload.tool_response -Compress -Depth 12
    if (-not $resp) { exit 0 }
    if ($resp -notmatch $script:EgressSignature) { exit 0 }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUse'
        additionalContext = (Get-EgressContext)
    } }
    Write-HookOutput (ConvertTo-Json -InputObject $out -Compress -Depth 8)
} catch {
    # Never let the nudge itself become a hook failure.
}

exit 0
