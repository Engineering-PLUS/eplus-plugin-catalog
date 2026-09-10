# PostToolUseFailure hook. Runs on the Windows host under PowerShell. On any EPLUS tool
# failure, nudges the model to file it via this plugin's report_issue tool; when the
# failure is a network egress block, nudges the egress-request path instead. Every
# nudge ends with the reporter identity (DOMAIN\user@MACHINE, read via .NET) so
# requested_by is always filled in. PowerShell 5.1-compatible, ASCII only, no BOM.
#
# Field-proven (2026-09-09, three exports): this event fires for mcp__workspace__bash
# nonzero exits, for Read/Write errors, for a failed Agent spawn, and for
# mcp__workspace__web_fetch egress refusals returned as is_error results. It is the
# only tool-event hook this plugin wires.
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
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_ERROR_NUDGE) { exit 0 }

    # Self-skip: don't nudge about the reporter's own failures.
    if ($raw -match 'report_issue' -or $raw -match 'error-reporting__' -or $raw -match '_error-reporting_') { exit 0 }

    . (Join-Path $PSScriptRoot 'egress-common.ps1')

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
               'the failing inputs in details. Fire-and-forget: on the {status: logged, log_id} response, ' +
               'mention the log_id and continue the task. File one report per distinct issue, never a ' +
               'secret in the body. If report_issue itself is unavailable, refused by the permission ' +
               'classifier, or fails, say so in one line and move on - do not retry in a loop and ' +
               'never let reporting derail the task.' +
               (Get-IdentityLine)
    }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUseFailure'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the reporter itself become a hook failure.
}

exit 0
