#!/bin/sh
# PostToolUseFailure hook (POSIX half; report-tool-failure.ps1 is the Windows
# half). On any EPLUS tool failure, nudges the model to file it via this
# plugin's own report_issue tool. Bundled WITH the error-reporting MCP + skill,
# so the nudge names them directly instead of asking the model to discover them.
#
# Self-skip: stays silent when the FAILED tool is report_issue / the
# error-reporting server itself, so a failing reporter can't drive a
# report -> fail -> report loop.
#
# Context-only output (additionalContext); never decision fields; always
# exits 0. Disable with EPLUS_NO_ERROR_NUDGE=1.
#
# Pure POSIX sh: a grep on the raw payload handles the self-skip, so no python
# or JSON parser is needed. The model already has the failed call in context,
# so the nudge carries no payload data.

# Windows guard: report-tool-failure.ps1 handles Windows hosts. Exit before
# reading stdin so the .ps1 (which runs first in the polyglot command) gets the
# full payload and this half never double-fires.
[ "${OS:-}" = "Windows_NT" ] && exit 0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

payload=$(cat)

[ -n "${EPLUS_NO_ERROR_NUDGE:-}" ] && exit 0

# Self-skip: don't nudge about the reporter's own failures.
case "$payload" in
  *report_issue*|*error-reporting__*|*_error-reporting_*) exit 0 ;;
esac

printf '%s' '{"hookSpecificOutput":{"hookEventName":"PostToolUseFailure","additionalContext":"[error-reporting] An EPLUS tool call just failed. Per the error-reporting skill, file it once with the report_issue tool (mcp__error-reporting__report_issue, or the mcp__plugin_error-reporting_error-reporting__report_issue form): category tool_failure, the real tool_name and server_name, a one-line message, and the exact error text plus the failing inputs in details. Fire-and-forget: on the {status: logged, log_id} response, mention the log_id and continue the task. File one report per distinct issue, never a secret in the body. If report_issue itself is unavailable or fails, say so in one line and move on - do not retry in a loop and never let reporting derail the task."}}'

exit 0
