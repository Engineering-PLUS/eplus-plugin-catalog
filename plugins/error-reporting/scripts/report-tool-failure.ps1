# PostToolUseFailure hook -- Windows half (see report-tool-failure.sh for the
# rationale). On any EPLUS tool failure, nudges the model to file it via this
# plugin's report_issue tool. PowerShell 5.1-compatible.
#
# Self-skip: silent when the failed tool is report_issue / the error-reporting
# server itself, so a failing reporter can't drive a report -> fail -> report loop.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_ERROR_NUDGE=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_ERROR_NUDGE) { exit 0 }

    # Self-skip: don't nudge about the reporter's own failures.
    if ($raw -match 'report_issue' -or $raw -match 'error-reporting__' -or $raw -match '_error-reporting_') { exit 0 }

    $ctx = '[error-reporting] An EPLUS tool call just failed. Per the error-reporting skill, ' +
           'file it once with the report_issue tool (mcp__error-reporting__report_issue, or the ' +
           'mcp__plugin_error-reporting_error-reporting__report_issue form): category tool_failure, ' +
           'the real tool_name and server_name, a one-line message, and the exact error text plus ' +
           'the failing inputs in details. Fire-and-forget: on the {status: logged, log_id} response, ' +
           'mention the log_id and continue the task. File one report per distinct issue, never a ' +
           'secret in the body. If report_issue itself is unavailable or fails, say so in one line ' +
           'and move on - do not retry in a loop and never let reporting derail the task.'
    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUseFailure'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the reporter itself become a hook failure.
}

exit 0
