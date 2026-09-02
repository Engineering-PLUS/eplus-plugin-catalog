---
description: TEMPORARY smoke test of the punch plugin's hooks, workspace flow, and packaging. Fixed script, minimal tokens, no real data. Remove before wide rollout.
argument-hint: (no arguments)
---

Run the punch plugin smoke test. This is a scripted, token-minimal test whose
evidence is collected from the session export afterwards, so the rules below
matter as much as the steps.

## Rules

- Do not load any skill (not `punch-report-generation`, not `punch`, not
  `plangrid-extraction`). Do not call any MCP tool.
- Do not read, cat, grep, or open any plugin file. Everything you need is here.
- No clarifying questions: every input is defined below. No task list.
- One tool call per step, in order. Do not retry a failed step; record it and
  move on. Do not investigate failures. Keep every command's output small.
- Say nothing between steps except a step number. Your only prose is the final
  table in step 9.

Set `W` to the workspace path for this test: a folder named `punch-test` inside
the session's outputs folder (your own working folder, never a user folder).
`W/ws` is the pipeline workspace and `W/project` stands in for a project folder.

## Steps

**1. Build the workspace** (Bash, one command):

```bash
W="$(pwd)/punch-test"; R="${CLAUDE_PLUGIN_ROOT}"; [ -d "$R/skills" ] || R=$(ls -d /sessions/*/mnt/*/.local-plugins/*/*/plugins/eplus-punch-reports 2>/dev/null | head -1); rm -rf "$W"; mkdir -p "$W/ws" "$W/project" && cp -r "$R/skills/punch-report-generation/template/." "$W/ws/" && cp -r "$R/skills/punch-report-generation/scripts" "$W/ws/_pipeline/scripts" && printf 'x' > "$W/ws/TEST-DRAFT-v0.1.docx" && echo "workspace ok: $W" && ls "$W/ws/_pipeline"
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

**3. PDF guard via Bash** (Bash). Run exactly:

```bash
soffice --headless --convert-to pdf "$W/ws/_pipeline/build/TEST-DRAFT-v0.1.docx"
```

Expected: the tool call is **denied before it runs** with a message that starts
"The punch report pipeline outputs .docx only". Record DENIED if so. If the
command actually executed (for example "soffice: command not found"), record
NOT DENIED.

**4. PDF guard via PowerShell** (PowerShell tool, if you have one; otherwise
record SKIPPED). Run exactly:

```powershell
soffice --headless --convert-to pdf "$env:TEMP\_pipeline\TEST-DRAFT-v0.1.docx"
```

Same expectation and recording as step 3.

**5. Unrelated conversion must NOT be denied** (Bash). The path must not
contain `_pipeline` or `-DRAFT-v`, so it lives outside the workspace:

```bash
soffice --headless --convert-to pdf /tmp/memo.docx; echo "ran (exit $?)"
```

Expected: the command runs (any output, including "not found") and prints
`ran`. Record PASS if it ran, FAIL if it was denied.

**6. Voice check** (Write tool). Write this exact content to the file
`<W>\ws\_pipeline\data\drafted_items.json`, using the Windows form of the
workspace path (the same form the session uses for its outputs folder):

```json
[{"number":"1","description":"Junction box at this location is open — cover missing."},{"number":"2","description":"The image is unclear."},{"number":"3","description":"Conduit terminates without a bushing."}]
```

Expected: immediately after the write you receive hook context beginning
"[punch-report] Voice check on drafted_items.json found 2 issue(s)". Record
PASS with the count you saw, or NO CONTEXT if nothing arrived.

**7. Render reminder** (Bash):

```bash
cd "$W/ws/_pipeline" && node --check scripts/gen_report.js && echo parsed
```

Expected: hook context beginning "[punch-report] The report was just
rendered." Record PASS or NO CONTEXT.

**8. Package delivery** (Bash):

```bash
cd "$W/ws/_pipeline" && python3 scripts/package.py "$W/ws" "$W/project" --dry-run | head -5 && python3 scripts/package.py "$W/ws" "$W/project" | tail -3 && ls "$W/project"
```

Expected: `delivered : TEST-DRAFT-v0.1.zip` and the project folder listing shows
the zip and the docx. Record PASS or the error line.

**9. Results.** Write `<W>/TEST-RESULTS.md` (Write tool) containing only the
table below, then print the same table as your entire final message, followed
by one line: "Export this session now."

```
| # | Check | Result |
|---|---|---|
| 1 | workspace built | |
| 2 | install_deps + smoke_test.sh | |
| 3 | PDF guard, Bash | |
| 4 | PDF guard, PowerShell | |
| 5 | unrelated conversion allowed | |
| 6 | voice check context | |
| 7 | render reminder context | |
| 8 | package delivered | |
```

Nothing else. No summary, no recommendations, no cleanup.
