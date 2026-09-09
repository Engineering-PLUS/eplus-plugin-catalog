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
account line is a placeholder), so the identity comes from a hook: at
session start, and again at the end of every failure nudge, a line reads

```
[error-reporting] Reporter identity for this seat: DOMAIN\user@MACHINE. ...
```

Copy that value **exactly** into `requested_by`. Rules:

- Never guess, infer, or normalise a name. Do not turn `CORP\jdoe@WS01` into
  an email address or a display name.
- If no identity line is present anywhere in context (the hook did not run,
  or the note was lost), send `requested_by: "unknown"` and mention in one
  line that the seat identity was unavailable. Do not ask the user for it.
- The identity is a seat, not a person's consent: it says which machine
  and login filed the report, nothing more..

## When to file

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

1. Tell the user the issue was logged, mentioning the `log_id`.
2. Continue the task immediately.

Never wait for, poll for, or promise a response, an answer, or a fix.
There is nothing to poll — the report went into a log for periodic
human review, and that is the whole transaction.

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
   - `pending`: tell the user the request is awaiting admin approval and
     mention the `request_id`. File nothing.
   - `denied`: relay `reason` to the user. File nothing, and do not ask
     again in this session.
   - `allowed`: retry the fetch **once**. If it still fails, the seat has
     not picked up the change: tell the user to **fully close the Claude
     app (quit it, not just the window) and relaunch**, then move on to
     work that does not need the host. Do not retry again before the
     relaunch.
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
4. **Relay:** tell the user the `request_id`, that an admin must approve
   it, and that the app needs a full relaunch after approval. On
   `status: "duplicate"` say the host was already requested and give the
   existing id.
5. **Continue** with everything that does not depend on that host.

One request per host per session. Never retry the blocked fetch in a
loop, and never route around the block (a different tool, a mirror, a
proxy, a cached copy from another host). If the user asks what is still
waiting, `list_egress_requests(status="pending")` answers it.

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
