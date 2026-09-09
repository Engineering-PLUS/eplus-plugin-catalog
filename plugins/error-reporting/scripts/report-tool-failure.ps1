# PostToolUseFailure hook. Runs on the Windows host under PowerShell. On any EPLUS tool
# failure, nudges the model to file it via this plugin's report_issue tool; when the
# failure is a network egress block, nudges the egress-request path instead. Every
# nudge ends with the reporter identity (DOMAIN\user@MACHINE from the host
# environment) so requested_by is always filled in. PowerShell 5.1-compatible,
# ASCII only, no BOM.
#
# Self-skip: silent when the failed tool is report_issue / the error-reporting
# server itself (this also covers the egress tools), so a failing reporter can't
# drive a report -> fail -> report loop.
#
# Egress branch: if the payload carries the egress signature (see egress-common.ps1)
# the generic nudge is replaced by the egress context. A marker under
# %TEMP%\eplus-error-reporting\<session_id>\<tool_use_id> keeps this hook and the
# PostToolUse web_fetch hook from nudging twice for one call.
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
        if ($raw -match $script:EgressSignature) {
            if (Test-EgressAlreadyNudged -Raw $raw) { exit 0 }
            $ctx = Get-EgressContext
        }
    }

    if (-not $ctx) {
        $ctx = '[error-reporting] An EPLUS tool call just failed. Per the error-reporting skill, ' +
               'file it once with the report_issue tool (mcp__error-reporting__report_issue, or the ' +
               'mcp__plugin_error-reporting_error-reporting__report_issue form): category tool_failure, ' +
               'the real tool_name and server_name, a one-line message, and the exact error text plus ' +
               'the failing inputs in details. Fire-and-forget: on the {status: logged, log_id} response, ' +
               'mention the log_id and continue the task. File one report per distinct issue, never a ' +
               'secret in the body. If report_issue itself is unavailable or fails, say so in one line ' +
               'and move on - do not retry in a loop and never let reporting derail the task.' +
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
