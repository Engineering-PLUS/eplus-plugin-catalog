# document-extraction-engine

Enterprise document extraction for the EPLUS fleet. The backend is the
**Document Analysis engine** — a FastMCP server over HTTP/SSE on port
8651 of the same Azure VM that hosts the Hermes RFI engine (same bearer
token). Jobs are asynchronous: submission returns a `job_id`
immediately, results are fetched when the job completes.

Like `eplus-rfis-submittals`, the server is **remote** SSE — safe to
bundle. The plugin ships an `.mcp.json` at the plugin root; no local
process is launched, so it works in Claude Code, Cowork, and managed
fleets alike.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/document-extraction/SKILL.md`](skills/document-extraction/SKILL.md) | Enterprise extraction doctrine: async job workflow, upload-hook contract, subagent delegation, failure protocol |
| Agent     | [`agents/doc-extractor.md`](agents/doc-extractor.md) | Haiku subagent that runs submit → poll → fetch and returns a distilled result |
| Hook      | [`hooks/hooks.json`](hooks/hooks.json) + [`hooks/upload_document.py`](hooks/upload_document.py) | PreToolUse on `analyze_document`: uploads raw file bytes out-of-band, denies the call with the `{status, job_id}` payload |
| MCP       | [`.mcp.json`](.mcp.json) | Bundled remote SSE connection to the Document Analysis VM with Bearer auth |

## MCP tools (server name: `document-analysis`)

1. `analyze_document(filename: str, file_base64: str = "", file_path: str = "", note: str = "") -> dict`
   — submits an extraction job, returns `{status, job_id, ...}` immediately.
2. `get_job_status(job_id: str) -> dict` — job progress.
3. `get_job_result(job_id: str) -> dict` — finished extraction output.
4. `list_jobs(limit: int = 20) -> dict` — recent jobs.

## The upload hook

Base64-encoding a document into `analyze_document`'s `file_base64` field
would put the entire payload into the model transcript and burn the
context window. Instead, the bundled PreToolUse hook intercepts any
`analyze_document` call whose `file_path` exists locally and uploads the
raw bytes directly:

```
POST http://20.9.42.66:8651/upload
Authorization: Bearer <token>
X-Filename: <basename>
<raw file bytes>
```

The endpoint returns the same `{status, job_id, ...}` JSON as the tool.
The hook then denies the tool call with that JSON in the denial reason;
the model (per the skill) treats a job-carrying denial as success and
proceeds to `get_job_status(job_id)`. If the path doesn't exist locally
or the upload fails, the hook stays silent and the tool call proceeds
untouched.

The hook script is Linux/python3 (Cowork VM deployment target).

## Claude Code / Cowork configuration

Bundled in [`.mcp.json`](.mcp.json):

```json
{
  "mcpServers": {
    "document-analysis": {
      "type": "sse",
      "url": "http://20.9.42.66:8651/sse",
      "headers": {
        "Authorization": "Bearer af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"
      }
    }
  }
}
```

> **Security note:** the bearer token is the shared static credential
> also used by the Hermes RFI engine, sent over plain HTTP. Rotate both
> together if it leaks, and prefer fronting the VM with HTTPS before
> wide deployment.

## Tool naming

Tools appear as
`mcp__plugin_document-extraction-engine_document-analysis__<tool>` when
loaded from this plugin, or `mcp__document-analysis__<tool>` from a
desktop/managed connection. The skill and the hook matcher
(`^mcp__.*__analyze_document$`) tolerate both.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install document-extraction-engine@eplus-claude-plugins
```

Verify: the skills list shows `document-extraction`, the agents list
shows `doc-extractor`, and submitting a local PDF via `analyze_document`
gets intercepted by the hook (denial containing a `job_id`) rather than
transferring base64 through the transcript.
