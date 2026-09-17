# PostToolUseFailure hook. Runs on the Windows host under PowerShell. On any EPLUS tool
# failure, nudges the model to file it via this plugin's report_issue tool; when the
# failure is a network egress block, nudges the egress-request path instead. Every
# nudge ends with the reporter identity (DOMAIN\user@MACHINE, read via .NET) so
# requested_by is always filled in. PowerShell 5.1-compatible, ASCII only, no BOM.
#
# Field-proven (2026-09-09, three exports): this event fires for mcp__workspace__bash
# nonzero exits, for Read/Write errors, for a failed Agent spawn, and for
# mcp__workspace__web_fetch egress refusals returned as is_error results. On desktop
# build 1.52386.3 (2026-09-15) a refused fetch came back as a successful result
# instead, so 0.4.0 pairs this script with egress-after-fetch.ps1 (PostToolUse on
# web_fetch); the two events are exclusive per call. Since 0.4.0 the plugin also
# wires stamp-identity.ps1 (PreToolUse on the reporting tools).
#
# Self-skip: silent when the failed tool is report_issue / the error-reporting
# server itself (this also covers the egress tools), so a failing reporter can't
# drive a report -> fail -> report loop.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable everything with EPLUS_NO_ERROR_NUDGE=1; disable only the egress branch
# with EPLUS_NO_EGRESS_NUDGE=1 (the generic nudge then fires as before).

$ErrorActionPreference = 'SilentlyContinue'

try {
    . (Join-Path $PSScriptRoot 'egress-common.ps1')
    $raw = Read-HookInput
    if ($env:EPLUS_NO_ERROR_NUDGE) { exit 0 }

    # Self-skip: don't nudge about the reporter's own failures. Decided on tool_name
    # so a bash command that merely mentions report_issue is still nudged; the raw
    # text match is only the fallback when the payload does not parse.
    $selfPattern = 'error-reporting__|_error-reporting_|report_issue$|request_egress_allow$|check_egress_host$|list_egress_requests$'
    $payload = $null
    try { $payload = ConvertFrom-Json -InputObject $raw -ErrorAction Stop } catch { $payload = $null }
    if ($null -ne $payload -and $payload.PSObject.Properties['tool_name']) {
        if (([string]$payload.tool_name) -match $selfPattern) { exit 0 }
    } elseif ($raw -match 'report_issue' -or $raw -match 'error-reporting__' -or $raw -match '_error-reporting_') { exit 0 }

    $ctx = $null
    if (-not $env:EPLUS_NO_EGRESS_NUDGE) {
        if ($raw -match $script:EgressSignature) { $ctx = Get-EgressContext }
    }

    if (-not $ctx) {
        $ctx = '[error-reporting] An EPLUS tool call just failed. Per the error-reporting skill, ' +
               'decide first whether it is a real failure: an expected nonzero exit (grep or find ' +
               'with no match, a probe loop, a check that is meant to fail) is not one and gets no ' +
               'report. If it is real, file it once with the report_issue tool ' +
               '(mcp__error-reporting__report_issue, or the ' +
               'mcp__plugin_error-reporting_error-reporting__report_issue form): category tool_failure, ' +
               'the real tool_name and server_name, a one-line message, and the exact error text plus ' +
               'the failing inputs in details. Fire-and-forget: on the {status: logged} response, ' +
               'tell the user in one short sentence that it was logged (no log_id, no tool names, no ' +
               'error text) and continue the task. File one report per distinct issue, never a ' +
               'secret in the body. If report_issue itself is unavailable, refused by the permission ' +
               'classifier, or fails, say so in one sentence and move on - do not retry in a loop and ' +
               'never let reporting derail the task.' +
               (Get-IdentityLine)
    }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUseFailure'
        additionalContext = $ctx
    } }
    Write-HookOutput (ConvertTo-Json -InputObject $out -Compress -Depth 8)
} catch {
    # Never let the reporter itself become a hook failure.
}

exit 0
