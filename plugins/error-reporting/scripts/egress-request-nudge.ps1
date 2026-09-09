# PostToolUse hook, matched only on the fetch tools (mcp__workspace__web_fetch |
# WebFetch). Runs on the Windows host under PowerShell. PowerShell 5.1-compatible,
# ASCII only, no BOM.
#
# Why this exists: a web_fetch egress block comes back as an is_error tool result
# ("Host ... is not on the network allowlist (cowork-egress-blocked)"). It is not yet
# field-verified whether that raises PostToolUseFailure or only PostToolUse, so both
# events are wired (2026-09-09). This script emits ONLY when tool_response carries
# the egress signature; every other fetch exits silently. The marker under
# %TEMP%\eplus-error-reporting\<session_id>\<tool_use_id> keeps this hook and
# report-tool-failure.ps1 from nudging twice for one call. Once the field test shows
# which event fires on a blocked fetch, the losing wiring is removed.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_EGRESS_NUDGE=1 (EPLUS_NO_ERROR_NUDGE=1 also silences it).

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_ERROR_NUDGE -or $env:EPLUS_NO_EGRESS_NUDGE) { exit 0 }

    . (Join-Path $PSScriptRoot 'egress-common.ps1')
    if (-not ($raw -match $script:EgressSignature)) { exit 0 }
    if (Test-EgressAlreadyNudged -Raw $raw) { exit 0 }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUse'
        additionalContext = (Get-EgressContext)
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the nudge itself become a hook failure.
}

exit 0
