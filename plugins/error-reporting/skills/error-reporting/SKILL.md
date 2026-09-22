---
name: error-reporting
description: Use this skill whenever a tool call on any EPLUS MCP server (rfi-knowledge-hub, punch-knowledge-hub, error-reporting itself) errors, misbehaves, or returns something clearly wrong, whenever the user explicitly asks for a change, fix, or feature on the EPLUS side of the tooling, or whenever a fetch or download is refused by the Cowork network allowlist (cowork-egress-blocked, "not on the network allowlist", "403 from proxy after CONNECT"). Teaches when and how to file a report with the report_issue tool — fire-and-forget logging to the EPLUS central review system, one report per distinct issue, never blocking the user's actual task — and how to check and file egress allow requests with check_egress_host, request_egress_allow, and list_egress_requests.
---

# EPLUS error & change-request reporting (error-reporting MCP)

Rules for filing reports through the `error-reporting` MCP server.
The server is a managed connector, so the tool appears as
`mcp__error-reporting__report_issue`; the plugin-bundled form
`mcp__plugin_error-reporting_error-reporting__report_issue` is tolerated too.
Same server, same rules.

This is Claude's line to the EPLUS central logging system. Reports are
reviewed periodically by the EPLUS team to fix issues on their end.
Filing a report does exactly one thing: logs the message. Nothing else
happens.

## The tool

```
report_issue(message: str, category: str = "tool_failure",
             tool_name: str = "", server_name: str = "",
             severity: str = "medium", details: str = "",
             requested_by: str = "")
```

Returns `{"status": "logged", "log_id": "<12-hex>", "message": "..."}`.

- `category` — `tool_failure` | `change_request` | `other`
- `severity` — `low` | `medium` | `high`. Use `high` only when the
  issue is blocking the user right now.
- `details` — the verbose supporting info: exact error text, the tool
  inputs that failed, what was tried
- `requested_by` — who is at this seat. See "Who is filing" below.

## Who is filing (`requested_by`)

Every report and every egress request carries `requested_by`. On this
deployment the model's own environment does **not** know the user (the
account line is a placeholder), so the identity comes from the plugin's
hooks on the Windows host. Three of them carry it:

- At session start (and after every resume and compaction) a note reads
  `[error-reporting] Reporter identity for this seat: DOMAIN\user@MACHINE. ...`
- Every failure or egress nudge ends with the same line.
- At filing time, a hook on `report_issue` and `request_egress_allow`
  itself fills `requested_by` with the seat identity when the call sent it
  empty or `unknown`, and appends one bracketed trace tag (`[seat session
  <id>; env session <id or none>; agent <type>/<id> or main]`) to `details`
  or `error_text`. This runs inside subagents too, so a worker that files a
  report is covered even though it never saw the session-start note. Its
  identity line arrives next to the tool result. If the hook cannot read a
  user name on the machine it leaves `requested_by` as you sent it and
  tells you so; keep the value you had.

Copy the value **exactly** into `requested_by`. Rules:

- Never guess, infer, or normalise a name. Do not turn `CORP\jdoe@WS01` into
  an email address or a display name.
- The stamp is a safety net, not the plan: still send the identity you
  have. Do not remove or rewrite the bracketed trace tag; it is how the
  EPLUS team ties a worker's report back to its session.
- **No identity line anywhere in context** (a session with the hooks
  switched off, or an older app build). Read the login from your working
  directory: it is always
  `C:\Users\<login>\AppData\Local\Claude-3p\local-agent-mode-sessions\...\outputs`,
  and the `<login>` segment is the Windows account at the seat. Send
  `requested_by: "<login>@chat"`. That is a deterministic read, not a
  guess. Never take a name from the selected folder, a file, or the
  conversation.
- If even the working directory does not have that shape, send
  `requested_by: "unknown"` and mention in one line that the seat identity
  was unavailable. Do not ask the user for it. (When the stamp hook is
  running it replaces that `unknown` with the seat identity on the way
  out; the one-line mention still stands.)
- The identity is a seat, not a person's consent: it says which machine
  and login filed the report, nothing more.

## When to file

**Not a failure, do not file:** an expected nonzero exit. `grep` or `find`
with no match, a probe loop where some URLs are meant to fail, a check
script that exits 1 to say "not found", a `wc` on a missing file you were
testing for, your own mistaken call. The failure hook counts every failure
in the session and nudges in proportion: a full reminder when an EPLUS
server tool failed, a one-line counted reminder for anything else (silent
after five), and the egress procedure on a network block. The count is for
the EPLUS team's diagnostics; you decide whether anything actually went
wrong. If the command did what you meant and the exit code is the answer,
there is nothing to report.

**Tool failure** — a tool call on any EPLUS MCP server
(`rfi-knowledge-hub`, `punch-knowledge-hub`, or `error-reporting` itself)
errors, misbehaves, or returns something clearly wrong (empty payloads,
stub markers, malformed results, wrong-document answers). File with:

- `category: "tool_failure"`
- the real `tool_name` and `server_name` that failed
- `message`: one line stating what went wrong
- `details`: the exact error text **verbatim**, the tool inputs that
  triggered it (argument names and shapes), and what was tried

**Change request** — the user explicitly asks for a change, fix, or
feature on the EPLUS side (server behavior, tool capabilities, workflow
gaps). File with:

- `category: "change_request"`
- `message`: one line summarizing the request
- `details`: the user's request **quoted** in their own words, plus any
  context on what prompted it

Anything worth logging that fits neither bucket: `category: "other"`.

## Fire-and-forget — the core contract

Filing a report is log-only. After the `{status: "logged", log_id}`
response comes back:

1. Tell the user, in one short sentence, that the issue was logged for
   the EPLUS team. No `log_id`, no tool names, no list of what you sent.
2. Continue the task immediately.

Never wait for, poll for, or promise a response, an answer, or a fix.
There is nothing to poll — the report went into a log for periodic
human review, and that is the whole transaction.

## Keep it quiet

Reporting is bookkeeping, not conversation. Whatever you file, the user
hears about it in one sentence folded into your normal answer, and only
then do you get on with the task. Do not enumerate the tools you called,
do not quote error text or allowlists back, do not explain the procedure,
and do not restate the same block twice in one reply. Ids stay on the
backend where the admin reads them. The only time you say more is when
the user asks what happened or what is waiting.

## One report per distinct issue

Do not re-file the same failure on every retry. File once when the
issue is established, then either work around it or tell the user it is
not working. Two genuinely different issues get two reports; the same
issue recurring gets one.

## No secrets in reports

Never put tokens, keys, credentials, or file contents into `message` or
`details`. Error text and tool argument names/shapes are enough for the
EPLUS team to diagnose.

## Reporting must never block the task

The user's actual task always comes first. If `report_issue` itself
fails, mention that to the user in one line and move on — do not retry
in a loop, and do not let a failed report derail the work. (A failure
of the error-reporting server is itself worth one `tool_failure` report
later, once it is reachable again — not a reason to stall now.)

## Egress allow requests

Cowork sessions (Chat tab and Cowork alike) can only reach hosts on the
`coworkEgressAllowedHosts` allowlist. A refused host is an **egress
block**, not a site failure, and it has its own path: check, file once,
relay, continue.

### Recognising a block

Three shapes, all meaning "this host is not on the allowlist":

| Where the request ran | What comes back |
|---|---|
| `mcp__workspace__web_fetch` (host side) | `Host "x" is not on the network allowlist (cowork-egress-blocked). Ask your administrator to add this domain to the Cowork egress allowlist (coworkEgressAllowedHosts). Allowed: ...` |
| `curl`, `pip`, `npm`, or any client inside the sandbox | `curl: (56) Received HTTP code 403 from proxy after CONNECT` (exit 56) |
| An EPLUS client script inside the sandbox | `HTTP 403: Forbidden` with no body and no `x-ms-error-code` |

**Not an egress block, do not file:** a Cloudflare bot challenge
(`cf-mitigated: challenge` header, a challenge HTML page), an Azure SAS
`AuthorizationPermissionMismatch`, a WAF page with a body, or any 403 that
arrives *after* the TLS connection succeeded. Those go on the user's
manual-download list instead.

**Redirect targets are the hidden case.** The host the user asked for can
be allowed while the host it redirects to is not (`cloud.google.com` to
`docs.cloud.google.com`, `mistral.ai` to `legal.mistral.ai`). The blocked
host is the *redirect target*. `curl` still prints it on the failed hop:

```
curl -sS -o /dev/null -L --max-time 20 -w "%{http_code} %{url_effective}\n" "<url>"
```

Record both hosts: the target as `host`, the allowed one as `redirect_from`.

### The tools

Same server, same two name prefixes as `report_issue`.

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

`status` and `reason` are set by the EPLUS admin. `allowed` means the host
has been approved **and** added to the allowlist; `denied` carries the
reason in `reason`.

### The procedure

1. **Name the host** (lower-case, keep a port if there is one). Apply the
   redirect rule above.
2. **Check first:** `check_egress_host(host)`.
   - `unknown`: go to step 3.
   - `pending`: one sentence, "a request for that site is already in with
     the admin." File nothing.
   - `denied`: one sentence, "that site was declined: <reason>." File
     nothing, and do not ask again in this session.
   - `allowed`: retry the fetch **once**. If it still fails, one sentence:
     "that site was approved but this seat needs a full quit and relaunch
     of the Claude app to pick it up." Then move on to work that does not
     need the host. Do not retry again before the relaunch.
3. **File once:** `request_egress_allow` with
   - `host`, and `redirect_from` when a redirect was involved
   - `url`: scheme, host and path only. Never a query string, which can
     carry tokens or SAS signatures.
   - `user_goal`: the user's request **in their own words**
   - `purpose`: one or two lines on why this site is needed for that goal
   - `tool_name` and the verbatim `error_text`
   - `requested_by`: the seat identity from the hook line, exactly as
     given (see "Who is filing")
   - `severity: "high"` only when the task cannot proceed at all without
     this host
4. **Relay in one sentence:** "I could not reach <host>, it is not on the
   network allowlist, so I filed an access request for the admin." On
   `status: "duplicate"`: "a request for that site is already in." No
   request id, no tool names, no error text, no explanation of the
   approval or relaunch mechanics unless the user asks.
5. **Continue** with everything that does not depend on that host.

One request per host per session. Never retry the blocked fetch in a
loop, and never route around the block (a different tool, a mirror, a
proxy, a cached copy from another host). If the user asks what is still
waiting, `list_egress_requests(status="pending")` answers it.

### No nudge arrived

A nudge is absent when the seat has the hooks switched off, on app builds
before 2026-09-11 in Chat-tab sessions (no plugin hooks ran there), and on
any build where a refused fetch comes back as an ordinary *successful*
result instead of an error (seen on desktop build 1.52386.3, 2026-09-15:
the failure hook never fired, so from 0.4.0 a second hook watches
successful `web_fetch` results for the block text as well). Whatever the
reason, recognise the block from the message text alone (the three shapes
above), then follow exactly the same procedure. If no identity line is in
context either, use the no-identity-line rule from "Who is filing" for
`requested_by`.

### When a reporting tool is refused by the permission classifier

Under auto mode a call to `request_egress_allow` or `report_issue` can come
back as "Permission for this action was denied by the Claude Code auto mode
classifier". That is not an egress block and not a tool failure, and it is
not deterministic. Do not retry the call in the same turn and do not file a
`tool_failure` about it. Write the fallback block below, say in one line
that the request was written to the file because the call was refused, and
continue. If a later `check_egress_host` for that host returns `unknown`,
file once then; the server never received the first attempt.

### When the error-reporting tools are unavailable

Append the same fields to `EGRESS-ALLOWLIST-REQUEST.md` in the session
outputs folder, one block per host:

```
## <host>
- requested: <ISO timestamp>
- url: <scheme://host/path>
- redirect_from: <host or empty>
- tool: <tool_name>
- requested_by: <seat identity or unknown>
- user_goal: <quoted>
- purpose: <why>
- error: <verbatim>
```

Tell the user in one line that the request was written to that file
because the reporting server was not reachable, and continue.
