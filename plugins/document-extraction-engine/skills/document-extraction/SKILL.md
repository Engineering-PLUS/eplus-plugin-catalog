---
name: document-extraction
description: Use this skill whenever a task needs enterprise-level document extraction or analysis — pulling structured data, text, tables, or metadata out of PDFs, Word documents, spreadsheets, scanned drawing sets, submittal packages, or spec books — or whenever the Document Analysis MCP tools (analyze_document, get_job_status, get_job_result, list_jobs) are involved. Encodes the async job workflow (submit → poll → fetch), the upload-hook contract (a denied analyze_document call carrying a job_id means the file was already uploaded), and the rule to delegate bulk extraction to the doc-extractor subagent. Always load it before calling any Document Analysis tool.
---

# EPLUS enterprise document extraction (Document Analysis MCP)

Rules for running document extraction through the `document-analysis`
MCP server. Depending on delivery, its tools appear as
`mcp__document-analysis__<tool>` (managed/desktop connector) or
`mcp__plugin_document-extraction-engine_document-analysis__<tool>`
(this plugin). Same server, same rules.

## Backend

The Document Analysis engine is an enterprise extraction service on a
dedicated VM (FastMCP over HTTP/SSE, port 8651 — sibling of the Hermes
RFI engine). It ingests PDFs, Office documents, scanned drawings, and
submittal packages, and runs asynchronous extraction jobs: submission
returns a `job_id` immediately; results are fetched when the job
completes.

## Available tools

- `analyze_document(filename, file_base64="", file_path="", note="")` —
  submits an extraction job; returns `{status, job_id, ...}`
  immediately. `filename` must keep the file's real extension.
- `get_job_status(job_id)` — poll job progress.
- `get_job_result(job_id)` — fetch the finished extraction.
- `list_jobs(limit=20)` — recent jobs, for finding a prior `job_id`.

## Submitting a document — the upload-hook contract

For any file that exists locally, call `analyze_document` with
`file_path` set to the absolute path and leave `file_base64` empty.
**Never base64-encode file content into the tool call yourself** — the
encoded payload lands in the transcript and wastes the context window.

This plugin installs a PreToolUse hook on `analyze_document`: when
`file_path` points at a real local file, the hook uploads the raw bytes
to the engine's `/upload` endpoint out-of-band and then **denies the
tool call with the upload response JSON in the denial reason**.

**A denial that contains `{status, job_id, ...}` is a SUCCESS**, not an
error and not a permissions problem:

- take the `job_id` from the denial reason,
- do NOT retry `analyze_document` for that file,
- proceed straight to `get_job_status(job_id)`.

Only treat a denial as a real refusal if it carries no job payload. Use
`file_base64` only as a last resort for very small files (roughly under
100 KB) when no local path exists.

## The job workflow

1. **Submit** — one `analyze_document` call per file, with a `note`
   describing the extraction intent.
2. **Poll** — `get_job_status(job_id)` until complete; wait between
   polls rather than hammering the endpoint.
3. **Fetch** — `get_job_result(job_id)` and work from what the engine
   actually returned.

## Delegate bulk work to the doc-extractor subagent

For any real extraction job — and especially multi-document batches or
large results — dispatch the `doc-extractor` agent (Haiku) with the file
path(s) and the extraction goal. It runs submit → poll → fetch and
returns a distilled result, keeping raw engine output out of the parent
context. Reserve direct tool calls in the main conversation for quick
one-offs like `list_jobs` or checking a known `job_id`.

## Failure protocol

If the `document-analysis` connector is missing or a tool call errors,
say exactly that (with the real error) instead of silently reading the
document yourself and presenting it as engine output. If a job fails or
returns empty/placeholder content, report the status verbatim — never
fabricate extracted data, tables, or citations. If the engine is down,
offer a plain best-effort read of the document, clearly labeled as NOT
engine-verified.
