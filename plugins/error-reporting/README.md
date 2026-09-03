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
| Skill     | [`skills/error-reporting/SKILL.md`](skills/error-reporting/SKILL.md) | When to file (tool_failure vs change_request), fire-and-forget contract, one-report-per-issue, no secrets, never block the task |
| Hook      | [`hooks/hooks.json`](hooks/hooks.json) | `PostToolUseFailure` nudge to auto-file failures (see below) |

## Auto-report hook (`PostToolUseFailure`)

So a failure gets logged even when the model doesn't reach for the skill on
its own, a `PostToolUseFailure` hook injects `additionalContext` after any
failed tool call, reminding the model to file it once via `report_issue`
(category `tool_failure`, real tool/server names, verbatim error text) and
then continue — the same fire-and-forget contract the skill defines.

- **Context-only.** The hook returns `additionalContext`, never a decision
  field, so it can never block or alter a tool call — it only advises.
- **Self-skipping.** It stays silent when the failed tool *is* `report_issue`
  or the error-reporting server itself, so a failing reporter can't drive a
  report → fail → report loop.
- **Windows host only.** Cowork executes hooks on the Windows host under
  PowerShell, never inside the Linux sandbox, so the hook is a single
  `report-tool-failure.ps1` invocation. The fleet is Windows-only.
- **Disable per-machine:** `EPLUS_NO_ERROR_NUDGE=1`.

The hook only nudges; the skill remains the authority on *when* and *how* to
file, and the user's task always comes first.

## MCP tool (server name: `error-reporting`)

```
report_issue(message: str, category: str = "tool_failure",
             tool_name: str = "", server_name: str = "",
             severity: str = "medium", details: str = "")
  -> {"status": "logged", "log_id": "<12-hex>", "message": "..."}
```

- `category`: `tool_failure` | `change_request` | `other`
- `severity`: `low` | `medium` | `high` (high = blocking the user right now)
- `details`: verbose supporting info — exact error text, the tool
  inputs that failed, what was tried

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
