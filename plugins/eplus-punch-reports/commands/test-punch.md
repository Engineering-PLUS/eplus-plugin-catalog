---
description: TEMPORARY smoke test of the punch plugin's workspace flow, build rules, packaging, and the plangrid MCP route (list_projects, list_sheets, get_tasks, then fetch, adapt and consolidate on the real result). Fixed script, minimal tokens. Remove before wide rollout.
argument-hint: [project name fragment] [task numbers, e.g. 41,42,43]
---

Run the punch plugin smoke test. This is a scripted, token-minimal test whose
evidence is collected from the session export afterwards, so the rules below
matter as much as the steps.

## Rules

- Do not load any skill (not `punch-report-generation`, not `punch`, not
  `plangrid-extraction`). The only MCP calls allowed are the four in steps 9
  to 12, one call each.
- Do not read, cat, grep, or open any plugin file. Everything you need is here.
- No clarifying questions: every input is defined below. No task list.
- One tool call per step, in order. Do not retry a failed step; record it and
  move on. Do not investigate failures. Keep every command's output small.
- Say nothing between steps except a step number. Your only prose is the final
  table in step 10.

Set `W` to the workspace path for this test: a folder named `punch-test` inside
the session's outputs folder (your own working folder, never a user folder).
`W/ws` is the pipeline workspace and `W/project` stands in for a project folder.

Arguments: `$ARGUMENTS`. The first word, if any, is a fragment of the PlanGrid
project name to use in steps 10 to 12; the second, if any, is a comma list of
task numbers. Defaults: the first project `list_projects` returns, and the
numbers `1,2,3`.

## Steps

**1. Build the workspace** (Bash, one command):

```bash
W="$(pwd)/punch-test"; R="${CLAUDE_PLUGIN_ROOT}"; [ -d "$R/skills" ] || R=$(ls -d /sessions/*/mnt/*/.local-plugins/*/*/plugins/eplus-punch-reports 2>/dev/null | head -1); rm -rf "$W"; mkdir -p "$W/ws/plangrid_mcp" "$W/project" && cp -r "$R/skills/punch-report-generation/template/." "$W/ws/" && cp -r "$R/skills/punch-report-generation/scripts" "$W/ws/_pipeline/scripts" && printf 'x' > "$W/ws/TEST-DRAFT-v0.1.docx" && echo "workspace ok: $W" && ls "$W/ws/_pipeline"
```

If `pwd` is not the outputs folder, replace `$(pwd)` with the outputs folder
path. Record PASS if it prints `workspace ok`.

**2. Install dependencies, then smoke test** (Bash, one command):

```bash
cd "$W/ws/_pipeline" && bash scripts/install_deps.sh 2>&1 | tail -6; bash scripts/smoke_test.sh 2>&1 | tail -8
```

Record PASS if the smoke test's last lines show no `FAIL`; otherwise record the
failing lines verbatim (they are the dependency evidence we want). Also note
whether install_deps reported packages "already present" or installed them.

**3. PDF conversion is allowed** (Bash). Run exactly:

```bash
soffice --headless --convert-to pdf --outdir /tmp "$W/ws/_pipeline/build/TEST-DRAFT-v0.1.docx"; echo "ran (exit $?)"
```

Expected: the command runs (any output, including a conversion error on the
placeholder file) and prints `ran`. Record PASS if it ran, DENIED if a hook
blocked it (there is no PDF guard since 0.6.4, so DENIED means a stale plugin).

**4. soffice present** (Bash):

```bash
which soffice && soffice --version | head -1
```

Record the version line, or MISSING.

**5. export_pdf.py parses** (Bash):

```bash
cd "$W/ws/_pipeline" && python3 scripts/export_pdf.py --help | head -2
```

Record PASS if it prints usage, or the error line.

**6. Voice check** (Write tool). Write this exact content to the file
`<W>\ws\_pipeline\data\drafted_items.json`, using the Windows form of the
workspace path (the same form the session uses for its outputs folder):

```json
[{"number":"1","description":"Junction box at this location is open — cover missing."},{"number":"2","description":"The image is unclear."},{"number":"3","description":"Conduit terminates without a bushing."}]
```

Expected: no hook context of any kind arrives (the plugin ships no hooks since
0.6.5). Record PASS if nothing arrived, or the first line of whatever did.

**7. Voice rules enforced by the build** (Bash):

```bash
cd "$W/ws/_pipeline" && printf '[{"number":1,"photos":[],"sheet_name":"T02-01A","sheet_description":"","room":"","status":"open"},{"number":2,"photos":[],"sheet_name":"T02-01A","sheet_description":"","room":"","status":"open"},{"number":3,"photos":[],"sheet_name":"T02-01A","sheet_description":"","room":"","status":"open"}]' > data/items.json && python3 scripts/build_master.py --items data/items.json --drafted data/drafted_items.json -o build/master_report_items.json 2>&1 | tail -3; echo "exit ${PIPESTATUS[0]}"
```

Expected: the build exits nonzero and names at least one item and the rule it
broke (the file from step 6 carries a dash in item 1 and photo narration in
item 2, and is missing required fields). Record PASS with what it named, or
the last line if it exited 0.

**8. Package delivery** (Bash):

```bash
cd "$W/ws/_pipeline" && python3 scripts/package.py "$W/ws" "$W/project" --dry-run | head -5 && python3 scripts/package.py "$W/ws" "$W/project" | tail -3 && ls "$W/project"
```

Expected: `delivered : TEST-DRAFT-v0.1.zip` and the project folder listing shows
the zip and the docx. Record PASS or the error line.

**9. MCP connectivity** (one tool call). Call the punch engine's `punch_stats`
tool with no arguments, or its smallest documented argument set. The tool is
named `mcp__punch-knowledge-hub__punch_stats` when delivered as a managed
connector, or `mcp__plugin_eplus-punch-reports_punch-knowledge-hub__punch_stats`
if bundled. If neither name exists in your tool list, record NO TOOL without
searching further. If the call errors, record the first line of the error
verbatim. If it answers, record PRESENT and the response size in one phrase
(for example "PRESENT, 6 trades").

**10. plangrid MCP: projects** (one tool call). Call `list_projects` on the
`plangrid` server (`mcp__plangrid__list_projects`; the bundled form would be
`mcp__plugin_eplus-punch-reports_plangrid__list_projects`) with no arguments.
If the tool is not in your list, record NO TOOL and record steps 11 to 13 as
SKIPPED. Pick the project whose name contains the first argument, or the first
project when there is no argument; keep its `uid` for the next two steps.
Record the project count and the chosen project's name.

**11. plangrid MCP: sheets** (one tool call, then one Write). Call
`list_sheets(project_uid=<uid>)`. Write the result verbatim, as JSON, with the
Write tool to `<W>\ws\plangrid_mcp\sheets.json` (Windows form of the path, as
in step 6). Record the sheet count and how many carry a non-empty title
(`description`), for example "38 sheets, 36 titled", or the first line of the
error.

**12. plangrid MCP: tasks** (one tool call, then one Write). Call
`get_tasks(project_uid=<uid>, numbers=[<the numbers>])` with no other
arguments. Write the result verbatim, as JSON, to
`<W>\ws\plangrid_mcp\tasks.json`. Record the `coverage` block in one phrase
(selected, not_found, failed), the total photo count across the rows, and
whether every photo carries a `download_url` on the MCP host, for example
"3 selected, 0 not found, 5 photos, all download_url". Record the first line
of the error if it fails.

**13. MCP route through the scripts** (Bash, one command). This is the same
sequence a real run uses on that material:

```bash
cd "$W/ws/_pipeline" && python3 scripts/fetch_photos.py --pull ../plangrid_mcp --timeout 20 2>&1 | tail -6; python3 scripts/adapt_mcp_pull.py --pull ../plangrid_mcp --dest ../plangrid_pull 2>&1 | tail -7; python3 scripts/consolidate.py ../plangrid_pull -o data/items_mcp.json 2>&1 | tail -2
```

Record three things verbatim: the `route` line from fetch_photos (`live` means
the sandbox reached the MCP photo host; `FALLBACK NEEDED` with the host name
means it did not), the `sheets` and `sheet titles` lines from the adapter
(which source filled the titles), and whether consolidate wrote
`data/items_mcp.json`. If step 12 failed, run the command anyway and record
the first error line.

**14. Results.** Write `<W>/TEST-RESULTS.md` (Write tool) containing only the
table below, then print the same table as your entire final message, followed
by one line: "Export this session now."

```
| # | Check | Result |
|---|---|---|
| 1 | workspace built | |
| 2 | install_deps + smoke_test.sh | |
| 3 | PDF conversion allowed | |
| 4 | soffice present | |
| 5 | export_pdf.py parses | |
| 6 | no hook context on Write | |
| 7 | voice rules enforced by build | |
| 8 | package delivered | |
| 9 | MCP punch_stats | |
| 10 | plangrid list_projects | |
| 11 | plangrid list_sheets | |
| 12 | plangrid get_tasks | |
| 13 | fetch / adapt / consolidate on the MCP result | |
```

Nothing else. No summary, no recommendations, no cleanup.
