# error-reporting

Claude's line to the EPLUS central logging system. When a tool on an
EPLUS MCP server fails or a user asks for an EPLUS-side change, the
model files a report; the EPLUS team reviews the log periodically and
fixes issues on their end. Filing is **fire-and-forget** — the server
logs the message, returns a `log_id`, and nothing else happens. (The
`log_id` leaves room to implement answers/follow-ups later.)

The backend is the **Error Reporting engine**, an EPLUS MCP server delivered
to every seat as a **managed connector** from the desktop bootstrap config.
The plugin ships no server definition and no credential.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/error-reporting/SKILL.md`](skills/error-reporting/SKILL.md) | When to file (tool_failure vs change_request), fire-and-forget contract, one-report-per-issue, no secrets, never block the task; the egress allow-request procedure |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | `SessionStart` identity note, `PostToolUseFailure` nudge to auto-file failures, plus a `PostToolUse` nudge on the fetch tools for egress blocks (see below) |
| Scripts   | [`scripts/`](scripts/) | `note-identity.ps1`, `report-tool-failure.ps1`, `egress-request-nudge.ps1`, and the shared `egress-common.ps1` (signature, context text, identity, dedupe marker) |

## Who is filing (`requested_by`)

Every `report_issue` and `request_egress_allow` call carries `requested_by`. On
the 3P deployment the model's environment has no real user name (the app's
account identity is the placeholder `cowork-3p@localhost`), so a `SessionStart`
hook (`note-identity.ps1`, firing on startup, resume, and compaction) injects
one line with the seat identity read from the Windows host environment:
`USERDOMAIN\USERNAME@COMPUTERNAME`. Every failure nudge repeats the same line so
the value survives compaction. The skill tells the model to copy it exactly,
never to guess a name, and to send `unknown` if the line is absent.

- **Disable per-machine:** `EPLUS_NO_IDENTITY_NOTE=1` (`EPLUS_NO_ERROR_NUDGE=1`
  silences it too).
- The server cannot derive this itself: every seat authenticates with the same
  shared connector credential, so identity has to travel as a field.

## Auto-report hook (`PostToolUseFailure`)

So a failure gets logged even when the model doesn't reach for the skill on
its own, a `PostToolUseFailure` hook injects `additionalContext` after any
failed tool call, reminding the model to file it once via `report_issue`
(category `tool_failure`, real tool/server names, verbatim error text) and
then continue — the same fire-and-forget contract the skill defines.

- **Context-only.** The hook returns `additionalContext`, never a decision
  field, so it can never block or alter a tool call — it only advises.
- **Self-skipping.** It stays silent when the failed tool *is* `report_issue`
  or the error-reporting server itself (including the egress tools), so a
  failing reporter can't drive a report → fail → report loop.
- **Windows host only.** Cowork executes hooks on the Windows host under
  PowerShell, never inside the Linux sandbox, so the hook is a single
  `report-tool-failure.ps1` invocation. The fleet is Windows-only.
- **Disable per-machine:** `EPLUS_NO_ERROR_NUDGE=1`.

The hook only nudges; the skill remains the authority on *when* and *how* to
file, and the user's task always comes first.

## Egress allow requests

Cowork sessions can only reach hosts on the `coworkEgressAllowedHosts`
allowlist. When a fetch or download is refused, the model should file an
**egress allow request** rather than a tool failure, so the admin sees which
host is needed, for what, and by whom. The skill's "Egress allow requests"
section is the authority; the hooks only nudge.

- **Signature.** `cowork-egress-blocked`, `not on the network allowlist`, or
  `Received HTTP code 403 from proxy after CONNECT` anywhere in the failure
  payload. A bare `HTTP 403: Forbidden` is deliberately not a signature: it is
  also what Cloudflare bot challenges and SAS permission errors return.
- **Two wirings, one nudge.** `report-tool-failure.ps1` (PostToolUseFailure,
  every tool) swaps its generic text for the egress context when the signature
  is present. `egress-request-nudge.ps1` (PostToolUse, matched only on
  `mcp__workspace__web_fetch|WebFetch`) emits the same context when
  `tool_response` carries the signature and exits silently otherwise. A
  web_fetch block is returned as an `is_error` tool result and it is not yet
  field-verified whether that raises PostToolUseFailure (proven for
  `mcp__workspace__bash` on 2026-09-01) or only PostToolUse, so both are wired;
  a marker under `%TEMP%\eplus-error-reporting\<session_id>\<tool_use_id>`
  guarantees one nudge per call. The losing wiring is removed after the field
  test.
- **What the context tells the model.** Name the blocked host (the redirect
  target when there was a redirect), call `check_egress_host`, then either
  file once with `request_egress_allow`, relay a `pending` status, relay a
  `denied` reason, or on `allowed` retry once and, if it still fails, tell the
  user to fully quit and relaunch the app so the seat picks up the new
  allowlist. Continue with everything else; never loop or route around.
- **Fallback.** If the error-reporting server is unavailable, the request is
  appended to `EGRESS-ALLOWLIST-REQUEST.md` in the session outputs folder in
  the same field layout.
- **Disable per-machine:** `EPLUS_NO_EGRESS_NUDGE=1` (the generic failure
  nudge keeps working); `EPLUS_NO_ERROR_NUDGE=1` silences both.

## MCP tool (server name: `error-reporting`)

```
report_issue(message: str, category: str = "tool_failure",
             tool_name: str = "", server_name: str = "",
             severity: str = "medium", details: str = "",
             requested_by: str = "")
  -> {"status": "logged", "log_id": "<12-hex>", "message": "..."}
```

- `category`: `tool_failure` | `change_request` | `other`
- `severity`: `low` | `medium` | `high` (high = blocking the user right now)
- `details`: verbose supporting info — exact error text, the tool
  inputs that failed, what was tried
- `requested_by`: seat identity from the hook line (`DOMAIN\user@MACHINE`),
  or `unknown`

### Egress tools (backend update pending; the server-side contract is delivered to the backend team separately)

```
check_egress_host(host: str)
  -> {"host", "status": "allowed" | "pending" | "denied" | "unknown",
      "reason", "request_id", "decided_at"}

request_egress_allow(host: str, url: str, purpose: str, user_goal: str,
                     requested_by: str, redirect_from: str = "",
                     tool_name: str = "", error_text: str = "",
                     severity: str = "medium")
  -> {"status": "logged" | "duplicate", "request_id": "<12-hex>",
      "host_status": "pending" | "allowed" | "denied"}

list_egress_requests(status: str = "pending", limit: int = 50)
  -> [{"request_id", "host", "redirect_from", "status", "reason",
       "hit_count", "first_seen", "last_seen", "sessions",
       "requesters", "purposes"}]
```

`status` and `reason` are set by the EPLUS admin on the backend. `allowed`
means approved **and** added to `coworkEgressAllowedHosts`; seats pick the
change up only after a full quit and relaunch of the app.

## Server delivery

The `error-reporting` server is a **managed connector** pushed by the desktop
bootstrap config; nothing in this repo defines it and no token lives here.
The managed server name must be exactly `error-reporting` so the tool name
the skill and the hook use, `mcp__error-reporting__report_issue`, holds.
Rotate the credential on the server side; the plugin never needs to change.

## Tool naming

With the managed connector the tool appears as
`mcp__error-reporting__report_issue`. The skill and the hook also tolerate the
plugin-bundled form `mcp__plugin_error-reporting_error-reporting__report_issue`
in case the server is ever bundled again.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install error-reporting@eplus-claude-plugins
```

Verify: the skills list shows `error-reporting`, and forcing a failure
on an EPLUS tool (or asking for an EPLUS-side change) produces one
`report_issue` call, a mention of the returned `log_id` to the user,
and immediate continuation of the task.
