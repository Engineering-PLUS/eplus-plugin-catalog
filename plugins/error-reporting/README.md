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
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | Four wirings: `SessionStart` identity note, `PreToolUse` identity stamp on the reporting tools, `PostToolUse` egress watch on `web_fetch`, and the `PostToolUseFailure` nudge for tool failures and egress blocks (see below and "Hook wiring notes") |
| Scripts   | [`scripts/`](scripts/) | `note-identity.ps1`, `stamp-identity.ps1`, `egress-after-fetch.ps1`, `report-tool-failure.ps1`, and the shared `egress-common.ps1` (signature, context text, identity) |

## Who is filing (`requested_by`)

Every `report_issue` and `request_egress_allow` call carries `requested_by`. On
the 3P deployment the model's environment has no real user name (the app's
account identity is the placeholder `cowork-3p@localhost`), so a `SessionStart`
hook (`note-identity.ps1`, firing on startup, resume, and compaction) injects
one line with the seat identity, `DOMAIN\user@MACHINE`, read through the .NET
API (`[Environment]::UserDomainName`, `UserName`, `MachineName`); environment
variables are only the fallback, because on one pilot seat `COMPUTERNAME` was
absent from the hook environment. Every failure nudge repeats the same line so
the value survives compaction. The skill tells the model to copy it exactly and
never to guess a name.

- **Stamped at filing time (0.4.0).** The note above reaches the main thread
  only. A subagent that files a report never held it, and reports arrived at
  the backend with `requested_by: "unknown"` (Hermes, 2026-09-15). So a
  `PreToolUse` hook on `report_issue` and `request_egress_allow`
  (`stamp-identity.ps1`) now fills `requested_by` with the seat identity when
  the call sent it empty or `unknown`, and appends one trace tag to `details`
  or `error_text`: `[seat session <id>; env session <CLAUDE_CODE_SESSION_ID or
  none>; agent <agent_type or main>]`. Plugin hooks run inside subagents (hooks
  reference), so the worker case is covered. See "Identity stamp hook" below.

- **Chat tab.** Since the desktop app release of 2026-09-11, organization-plugin
  hooks run in Chat too (matching Cowork and Code), so the same identity line
  arrives there and a Chat report carries `DOMAIN\user@MACHINE` like any other.
  Not yet confirmed from a Chat export. On older builds no plugin hook loaded in
  Chat; for those, and for any session where no identity line is in context,
  the skill has the model read the login from the session working directory,
  which is always
  `C:\Users\<login>\AppData\Local\Claude-3p\local-agent-mode-sessions\...\outputs`
  (verified on four seats; the selected folder is a separate mount and never the
  cwd), and send `<login>@chat`. Only if the cwd does not have that shape does
  it send `unknown`.
- **Disable per-machine:** `EPLUS_NO_IDENTITY_NOTE=1` for the session-start
  note, `EPLUS_NO_IDENTITY_STAMP=1` for the filing-time stamp
  (`EPLUS_NO_ERROR_NUDGE=1` silences both).
- The server cannot derive this itself: every seat authenticates with the same
  shared connector credential, so identity has to travel as a field.

## Identity stamp hook (`PreToolUse`)

`stamp-identity.ps1` runs before every `report_issue` and
`request_egress_allow` call, under both tool-name forms
(`mcp__error-reporting__*` and `mcp__plugin_error-reporting_error-reporting__*`).
`check_egress_host` and `list_egress_requests` are not matched: neither takes
`requested_by`.

- **What it rewrites.** When `tool_input.requested_by` is empty or `unknown` it
  is set to `DOMAIN\user@MACHINE`; a name the model already supplied is kept. When
  `details` (`report_issue`) or `error_text` (`request_egress_allow`) lacks a
  complete `[seat session <id>; env session <id or none>; agent <type>/<id> or main]`
  tag, one is appended after the existing text, which is not trimmed or changed.
  If the host identity itself cannot be read, `requested_by` is never overwritten
  and the context line says so.
- **UTF-8.** Hook processes start with an IBM437 console, so every script reads stdin
  and writes stdout through the UTF-8 helpers in `egress-common.ps1`; a report with
  accents or dashes round-trips intact through `updatedInput`.
- **How.** The hook returns `permissionDecision: "allow"` with `updatedInput`,
  which per the hooks reference "Replaces the entire input object", so the
  script echoes every field back with the two changes. When nothing needed
  changing it returns only `additionalContext` (the identity line) and leaves
  the permission decision to the harness. Deny and ask rules, and any MCP tool
  marked `requiresUserInteraction`, still win over the hook's allow.
- **Side effect to know about.** On a stamped call the allow resolves the
  permission before the auto-mode classifier runs, so the classifier refusals
  the skill describes should stop for stamped calls. Unstamped calls behave as
  before.
- **Field status.** Unverified on a seat. First export to check: the
  `PreToolUse:mcp__error-reporting__report_issue` hook attachment, the
  `tool_use` input carrying the identity and the trace tag, and whether the
  `env session` part is a real id or `none` (that settles whether
  `CLAUDE_CODE_SESSION_ID` reaches hook processes on Cowork). If Desktop
  ignores `updatedInput`, the identity line still lands next to the tool
  result and the fallback is context-only, same as 0.3.x.
- **Disable per-machine:** `EPLUS_NO_IDENTITY_STAMP=1`.

## Auto-report hook (`PostToolUseFailure`)

So a failure gets logged even when the model doesn't reach for the skill on
its own, a `PostToolUseFailure` hook injects `additionalContext` after any
failed tool call, reminding the model to file it once via `report_issue`
(category `tool_failure`, real tool/server names, verbatim error text) and
then continue — the same fire-and-forget contract the skill defines.

- **Context-only.** This hook returns `additionalContext`, never a decision
  field, so it can never block or alter a tool call — it only advises. (The
  identity stamp hook above is the one wiring that rewrites a call.)
- **Self-skipping.** It stays silent when the failed tool *is* `report_issue`
  or the error-reporting server itself (including the egress tools), so a
  failing reporter can't drive a report → fail → report loop. Decided on the
  payload's `tool_name` (0.4.0); a bash command that merely mentions
  `report_issue` is still nudged.
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
- **Two wirings.** `report-tool-failure.ps1` (PostToolUseFailure, every tool)
  swaps its generic text for the egress context when the signature is present.
  Field-verified on 2026-09-09 across three exports: PostToolUseFailure fires
  for `mcp__workspace__web_fetch` refusals returned as `is_error` results, one
  nudge per refused fetch, so the provisional 0.3.0 PostToolUse wiring was
  removed in 0.3.1 with its marker-file dedupe. On desktop build 1.52386.3
  (export of 2026-09-15) the same refusal came back as a *successful* result
  (57 fetches, zero failure hooks), so 0.4.0 adds `egress-after-fetch.ps1`
  (PostToolUse on `mcp__workspace__web_fetch`): it reads `tool_response` and
  emits the egress context only when the signature is present, silent
  otherwise. Success and failure events are exclusive per call, so no dedupe.
  Cost: one spawn per fetch.
- **Chat tab.** The nudge fires in Chat too since the desktop app release of
  2026-09-11 (organization-plugin hooks now run in Chat, matching Cowork and
  Code; not yet confirmed from a Chat export). On older builds no plugin hook
  loaded there. Either way the skill carries the same procedure from the
  message text alone, and the no-identity-line rule for `requested_by` (below).
- **Classifier refusals.** Under auto mode the permission classifier can refuse
  a reporting call non-deterministically. The skill treats that as neither
  egress nor a tool failure: fallback file, one line to the user, no retry that
  turn, file once later if `check_egress_host` still says `unknown`.
- **What the context tells the model.** Name the blocked host (the redirect
  target when there was a redirect), call `check_egress_host`, then either
  file once with `request_egress_allow`, do nothing on `pending` or `denied`,
  or on `allowed` retry once. Then one sentence to the user folded into the
  normal answer: could not reach the site, request filed (or already
  requested, or declined with the reason, or approved but this seat needs a
  full quit and relaunch). No request ids, tool names, error text, or
  procedure. Continue with everything else; never loop or route around.
- **Quiet by design (0.3.2).** Reporting is bookkeeping. Ids stay on the
  backend for the admin; the user hears one sentence and the task goes on.
  The model only elaborates when the user asks what happened.
- **Fallback.** If the error-reporting server is unavailable, the request is
  appended to `EGRESS-ALLOWLIST-REQUEST.md` in the session outputs folder in
  the same field layout.
- **Disable per-machine:** `EPLUS_NO_EGRESS_NUDGE=1` silences both egress
  wirings (the generic failure nudge keeps working); `EPLUS_NO_ERROR_NUDGE=1`
  silences everything in this plugin.

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

## Hook wiring notes

The prose that used to sit in a top-level `description` field of
`hooks/hooks.json` lives here: the plugins reference documents no such field,
so it is kept out of the file the app parses.

- **Windows host, single PowerShell call.** The fleet is Windows-only and
  Cowork executes hooks on the Windows host under PowerShell, never inside the
  Linux sandbox. Every entry uses `"shell": "powershell"` with a direct
  `& "${CLAUDE_PLUGIN_ROOT}\scripts\<name>.ps1"` call (adopted 2026-09-03 after
  a field A/B in one export: the app's own PowerShell runs the script in one
  process instead of launching a second `powershell.exe`). This single-launch
  form is the standard for the catalog. Scripts are PowerShell 5.1-compatible,
  ASCII, no BOM, read stdin with `[Console]::In.ReadToEnd()`, always exit 0,
  and carry any decision in the JSON body.
- **Four wirings.** `SessionStart` on `*` (startup, resume, compact):
  `note-identity.ps1`, one spawn (~750 ms) per session open, resume, or
  compaction. `PreToolUse` on the two filing tools under both name forms:
  `stamp-identity.ps1`, one spawn per reporting call. `PostToolUse` on
  `mcp__workspace__web_fetch`: `egress-after-fetch.ps1`, one spawn per fetch.
  `PostToolUseFailure` on `*`: `report-tool-failure.ps1`, one spawn per failed
  tool call; self-skips when the failed tool is the error-reporting server.
- **Field results.** 2026-09-09 (three exports): PostToolUseFailure fires for
  `web_fetch` egress refusals, bash nonzero exits, Read/Write errors and failed
  Agent spawns. 2026-09-14 (CTX2 exports): PostToolUseFailure fires inside
  subagent transcripts. 2026-09-15 (desktop 1.52386.3): a refused fetch
  returned as a success, and a subagent's report carried `requested_by:
  "unknown"`; both drove 0.4.0.
- **Chat tab.** Through the 2026-09-09 exports plugin hooks did not load in
  Chat-tab sessions (no `load_plugin_hooks` in cli-diagnostics). The desktop
  release of 2026-09-11 runs organization-plugin hooks in Chat too, matching
  Cowork and Code, so all four wirings are expected there from that build on
  (not yet confirmed from a Chat export). The skill keeps the cwd-based
  identity rule as the fallback for any session with no identity line.
- **Switches.** `EPLUS_NO_ERROR_NUDGE=1` disables everything;
  `EPLUS_NO_EGRESS_NUDGE=1` only the two egress wirings;
  `EPLUS_NO_IDENTITY_NOTE=1` only the session-start note;
  `EPLUS_NO_IDENTITY_STAMP=1` only the filing-time stamp.

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
`report_issue` call, one sentence to the user saying it was logged,
and immediate continuation of the task.
